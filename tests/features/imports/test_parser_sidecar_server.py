import asyncio
import signal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook

from app.features.imports.parsers.extractors.limits import StatementExtractionLimits
from app.features.imports.parsers.sidecar.client import StatementParserSidecarClient
from app.features.imports.parsers.sidecar.protocol import (
    MAX_HEADER_BYTES,
    MAX_INPUT_BYTES,
    PROTOCOL_VERSION,
    RESOURCE_LIMIT_EXIT_CODE,
    ParserResourceLimitError,
    ParserTimeoutError,
    ParserUnavailableError,
    decode_json,
    encode_json,
    read_frame,
    write_frame,
)
from app.features.imports.parsers.sidecar.server import ParserSidecarServer


def client(
    socket_path: Path,
    *,
    limits: StatementExtractionLimits | None = None,
    input_max_bytes: int = 1024 * 1024,
    response_max_bytes: int = 1024 * 1024,
    wall_timeout_seconds: int = 10,
    memory_bytes: int = 256 * 1024 * 1024,
) -> StatementParserSidecarClient:
    return StatementParserSidecarClient(
        socket_path,
        limits=limits or StatementExtractionLimits(),
        input_max_bytes=input_max_bytes,
        response_max_bytes=response_max_bytes,
        wall_timeout_seconds=wall_timeout_seconds,
        cpu_seconds=5,
        memory_bytes=memory_bytes,
    )


async def test_server_ping_busy_and_xlsx_success(tmp_path: Path) -> None:
    socket_path = tmp_path / "parser.sock"
    sidecar = ParserSidecarServer(socket_path)
    server = await asyncio.start_unix_server(sidecar._handle, path=socket_path)
    workbook_data = BytesIO()
    workbook = Workbook()
    workbook.active.append(["Date", "Amount"])
    workbook.active.append(["2026-08-26", "10"])
    workbook.save(workbook_data)
    workbook.close()
    source = tmp_path / "statement.xlsx"
    source.write_bytes(workbook_data.getvalue())

    async with server:
        await client(socket_path).ping()
        extracted = await client(socket_path).extract(source)
        assert extracted.metadata["source_format"] == "xlsx"

        await sidecar.job_lock.acquire()
        try:
            reader, writer = await asyncio.open_unix_connection(socket_path)
            await write_frame(
                writer,
                encode_json(
                    {
                        "version": PROTOCOL_VERSION,
                        "command": "EXTRACT",
                    },
                    maximum=MAX_HEADER_BYTES,
                ),
            )
            assert decode_json(await read_frame(reader, maximum=MAX_HEADER_BYTES)) == {
                "ok": False,
                "error": "busy",
            }
            writer.close()
            await writer.wait_closed()
        finally:
            sidecar.job_lock.release()


async def test_client_cancellation_kills_active_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = asyncio.StreamReader()
            self.returncode: int | None = None
            self.killed = asyncio.Event()

        def kill(self) -> None:
            self.returncode = -9
            self.stdout.feed_eof()
            self.killed.set()

        async def wait(self) -> int:
            if self.returncode is None:
                await self.killed.wait()
            return self.returncode or 0

    process = FakeProcess()
    process_started = asyncio.Event()

    async def create_process(*_args: object, **_kwargs: object) -> FakeProcess:
        process_started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    socket_path = tmp_path / "parser.sock"
    sidecar = ParserSidecarServer(socket_path)
    server = await asyncio.start_unix_server(sidecar._handle, path=socket_path)
    source = tmp_path / "statement.pdf"
    source.write_bytes(b"%PDF-1.4")

    async with server:
        extraction = asyncio.create_task(client(socket_path).extract(source))
        await asyncio.wait_for(process_started.wait(), timeout=1)
        extraction.cancel()
        with pytest.raises(asyncio.CancelledError):
            await extraction
        await asyncio.wait_for(process.killed.wait(), timeout=1)


async def test_sidecar_extracts_pdf_successfully(tmp_path: Path) -> None:
    socket_path = tmp_path / "parser.sock"
    server = await asyncio.start_unix_server(
        ParserSidecarServer(socket_path)._handle,
        path=socket_path,
    )

    async with server:
        extracted = await client(socket_path).extract(Path("tests/fixtures/expobank_statement.pdf"))

    assert extracted.metadata["source_format"] == "pdf"
    assert extracted.text_by_page


@pytest.mark.parametrize(
    ("source_name", "limits"),
    [
        pytest.param(
            "tests/fixtures/expobank_statement.pdf",
            StatementExtractionLimits(pdf_max_characters=1),
            id="pdf",
        ),
        pytest.param(
            "tests/fixtures/alfa_bank_card_statement.xlsx",
            StatementExtractionLimits(xlsx_max_cells=1),
            id="xlsx",
        ),
    ],
)
async def test_sidecar_maps_real_extractor_limits_to_resource_limit(
    tmp_path: Path,
    source_name: str,
    limits: StatementExtractionLimits,
) -> None:
    socket_path = tmp_path / "parser.sock"
    server = await asyncio.start_unix_server(
        ParserSidecarServer(socket_path)._handle,
        path=socket_path,
    )

    async with server:
        with pytest.raises(ParserResourceLimitError):
            await client(socket_path, limits=limits).extract(Path(source_name))


async def test_sidecar_maps_worker_response_overflow_to_resource_limit(tmp_path: Path) -> None:
    socket_path = tmp_path / "parser.sock"
    server = await asyncio.start_unix_server(
        ParserSidecarServer(socket_path)._handle,
        path=socket_path,
    )

    async with server:
        with pytest.raises(ParserResourceLimitError):
            await client(socket_path, response_max_bytes=64).extract(
                Path("tests/fixtures/alfa_bank_card_statement.xlsx")
            )


async def test_sidecar_maps_real_worker_memory_exhaustion_to_resource_limit(
    tmp_path: Path,
) -> None:
    socket_path = tmp_path / "parser.sock"
    server = await asyncio.start_unix_server(
        ParserSidecarServer(socket_path)._handle,
        path=socket_path,
    )

    async with server:
        with pytest.raises(ParserResourceLimitError):
            await client(socket_path, memory_bytes=32 * 1024 * 1024).extract(
                Path("tests/fixtures/alfa_bank_card_statement.xlsx")
            )


@pytest.mark.parametrize("returncode", [RESOURCE_LIMIT_EXIT_CODE, -signal.SIGXCPU, -signal.SIGKILL])
async def test_sidecar_maps_memory_and_process_limit_exits_to_resource_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
) -> None:
    class LimitedProcess:
        def __init__(self) -> None:
            self.stdout = asyncio.StreamReader()
            self.stdout.feed_eof()
            self.returncode = returncode

        async def wait(self) -> int:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -signal.SIGKILL

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        lambda *_args, **_kwargs: _return(LimitedProcess()),
    )
    socket_path = tmp_path / "parser.sock"
    server = await asyncio.start_unix_server(
        ParserSidecarServer(socket_path)._handle,
        path=socket_path,
    )
    source = tmp_path / "statement.pdf"
    source.write_bytes(b"%PDF-1.4")

    async with server:
        with pytest.raises(ParserResourceLimitError):
            await client(socket_path).extract(source)


async def test_sidecar_enforces_real_wall_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HangingProcess:
        def __init__(self) -> None:
            self.stdout = asyncio.StreamReader()
            self.returncode: int | None = None
            self.killed = asyncio.Event()

        async def wait(self) -> int:
            await self.killed.wait()
            assert self.returncode is not None
            return self.returncode

        def kill(self) -> None:
            self.returncode = -signal.SIGKILL
            self.stdout.feed_eof()
            self.killed.set()

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        lambda *_args, **_kwargs: _return(HangingProcess()),
    )
    socket_path = tmp_path / "parser.sock"
    server = await asyncio.start_unix_server(
        ParserSidecarServer(socket_path)._handle,
        path=socket_path,
    )
    source = tmp_path / "statement.pdf"
    source.write_bytes(b"%PDF-1.4")

    async with server:
        with pytest.raises(ParserTimeoutError):
            await client(socket_path, wall_timeout_seconds=1).extract(source)


async def test_server_rejects_input_overflow_and_malformed_header(tmp_path: Path) -> None:
    socket_path = tmp_path / "parser.sock"
    server = await asyncio.start_unix_server(
        ParserSidecarServer(socket_path)._handle,
        path=socket_path,
    )

    async with server:
        cases: tuple[tuple[dict[str, object], str], ...] = (
            (
                {
                    "version": PROTOCOL_VERSION,
                    "command": "EXTRACT",
                    "extension": ".pdf",
                    "byte_count": MAX_INPUT_BYTES + 1,
                    "response_max_bytes": 1024,
                    "wall_timeout_seconds": 1,
                    "cpu_seconds": 1,
                    "memory_bytes": 1024,
                    "limits": StatementExtractionLimits().model_dump(mode="json"),
                },
                "resource_limit",
            ),
            ({"version": PROTOCOL_VERSION, "command": "EXTRACT"}, "invalid_result"),
        )
        for header, expected in cases:
            reader, writer = await asyncio.open_unix_connection(socket_path)
            await write_frame(writer, encode_json(header, maximum=MAX_HEADER_BYTES))
            response = decode_json(await read_frame(reader, maximum=MAX_HEADER_BYTES))
            assert response == {"ok": False, "error": expected}
            writer.close()
            await writer.wait_closed()


async def test_client_maps_sidecar_restart_to_unavailable(tmp_path: Path) -> None:
    with pytest.raises(ParserUnavailableError):
        await client(tmp_path / "missing.sock").extract(
            Path("tests/fixtures/expobank_statement.pdf")
        )


async def _return(value: Any) -> Any:
    return value
