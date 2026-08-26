import argparse
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
from pydantic import ValidationError

from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.parsers.extractors.limits import StatementExtractionLimits
from app.features.imports.parsers.sidecar.protocol import (
    MAX_HEADER_BYTES,
    PROTOCOL_VERSION,
    ParserErrorCode,
    ParserInvalidResultError,
    ParserResourceLimitError,
    ParserSidecarError,
    ParserTimeoutError,
    ParserUnavailableError,
    decode_json,
    encode_json,
    read_frame,
    write_frame,
)

if TYPE_CHECKING:
    from app.core.settings import Settings


class StatementParserSidecarClient:
    def __init__(
        self,
        socket_path: Path,
        *,
        limits: StatementExtractionLimits,
        input_max_bytes: int,
        response_max_bytes: int,
        wall_timeout_seconds: int,
        cpu_seconds: int,
        memory_bytes: int,
    ) -> None:
        self.socket_path = socket_path
        self.limits = limits
        self.input_max_bytes = input_max_bytes
        self.response_max_bytes = response_max_bytes
        self.wall_timeout_seconds = wall_timeout_seconds
        self.cpu_seconds = cpu_seconds
        self.memory_bytes = memory_bytes

    @classmethod
    def from_settings(cls, settings: "Settings") -> "StatementParserSidecarClient | None":
        if settings.statement_parser_socket_path is None:
            return None
        return cls(
            settings.statement_parser_socket_path,
            limits=StatementExtractionLimits(
                pdf_max_pages=settings.statement_pdf_max_pages,
                pdf_max_characters=settings.statement_pdf_max_characters,
                pdf_max_tables=settings.statement_pdf_max_tables,
                pdf_max_cells=settings.statement_pdf_max_cells,
                xlsx_max_sheets=settings.statement_xlsx_max_sheets,
                xlsx_max_rows_per_sheet=settings.statement_xlsx_max_rows_per_sheet,
                xlsx_max_columns_per_sheet=settings.statement_xlsx_max_columns_per_sheet,
                xlsx_max_cells=settings.statement_xlsx_max_cells,
                xlsx_max_uncompressed_bytes=settings.statement_xlsx_max_uncompressed_bytes,
            ),
            input_max_bytes=settings.statement_upload_max_bytes,
            response_max_bytes=settings.statement_extraction_result_max_bytes,
            wall_timeout_seconds=settings.statement_parser_wall_timeout_seconds,
            cpu_seconds=settings.statement_parser_cpu_seconds,
            memory_bytes=settings.statement_parser_memory_bytes,
        )

    async def extract(self, file_path: Path) -> ExtractedStatement:
        try:
            return await asyncio.wait_for(
                self._extract(file_path),
                timeout=self.wall_timeout_seconds + 2,
            )
        except TimeoutError as error:
            raise ParserTimeoutError("timeout") from error
        except (ConnectionError, OSError) as error:
            raise ParserUnavailableError("unavailable") from error

    async def _extract(self, file_path: Path) -> ExtractedStatement:
        declared_size = (await anyio.Path(file_path).stat()).st_size
        if declared_size > self.input_max_bytes:
            raise ParserResourceLimitError("resource_limit")
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        try:
            header = {
                "version": PROTOCOL_VERSION,
                "command": "EXTRACT",
                "extension": file_path.suffix.casefold(),
                "byte_count": declared_size,
                "response_max_bytes": self.response_max_bytes,
                "wall_timeout_seconds": self.wall_timeout_seconds,
                "cpu_seconds": self.cpu_seconds,
                "memory_bytes": self.memory_bytes,
                "limits": self.limits.model_dump(mode="json"),
            }
            await write_frame(writer, encode_json(header, maximum=MAX_HEADER_BYTES))
            sent = 0
            async with await anyio.open_file(file_path, "rb") as source:
                while chunk := await source.read(64 * 1024):
                    sent += len(chunk)
                    if sent > self.input_max_bytes:
                        raise ParserResourceLimitError("resource_limit")
                    writer.write(chunk)
                    await writer.drain()
            if sent != declared_size:
                raise ParserInvalidResultError("input_size_changed")
            envelope = decode_json(await read_frame(reader, maximum=self.response_max_bytes))
        finally:
            writer.close()
            await writer.wait_closed()
        if envelope.get("ok") is not True:
            _raise_sidecar_error(envelope.get("error"))
        try:
            return ExtractedStatement.model_validate(envelope.get("result"))
        except ValidationError as error:
            raise ParserInvalidResultError("invalid_result") from error

    async def ping(self) -> None:
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            try:
                await write_frame(
                    writer,
                    encode_json(
                        {"version": PROTOCOL_VERSION, "command": "PING"},
                        maximum=MAX_HEADER_BYTES,
                    ),
                )
                envelope = decode_json(await read_frame(reader, maximum=MAX_HEADER_BYTES))
                if envelope != {"ok": True, "result": "PONG"}:
                    raise ParserUnavailableError("unavailable")
            finally:
                writer.close()
                await writer.wait_closed()
        except (ConnectionError, OSError) as error:
            raise ParserUnavailableError("unavailable") from error


def _raise_sidecar_error(value: object) -> None:
    code = value if isinstance(value, str) else ParserErrorCode.INVALID_RESULT
    error_type: type[ParserSidecarError] = {
        ParserErrorCode.TIMEOUT: ParserTimeoutError,
        ParserErrorCode.RESOURCE_LIMIT: ParserResourceLimitError,
        ParserErrorCode.UNAVAILABLE: ParserUnavailableError,
        ParserErrorCode.INVALID_RESULT: ParserInvalidResultError,
        "busy": ParserUnavailableError,
    }.get(code, ParserInvalidResultError)
    raise error_type(str(code))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    args = parser.parse_args()
    client = StatementParserSidecarClient(
        args.socket,
        limits=StatementExtractionLimits(),
        input_max_bytes=1,
        response_max_bytes=MAX_HEADER_BYTES,
        wall_timeout_seconds=3,
        cpu_seconds=1,
        memory_bytes=1,
    )
    asyncio.run(client.ping())


if __name__ == "__main__":
    main()
