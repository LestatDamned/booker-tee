import asyncio
from pathlib import Path

import pytest

from app.features.imports.parsers.extractors.limits import StatementExtractionLimits
from app.features.imports.parsers.sidecar.client import StatementParserSidecarClient
from app.features.imports.parsers.sidecar.protocol import (
    MAX_HEADER_BYTES,
    ParserInvalidResultError,
    encode_json,
    read_frame,
    write_frame,
)


def client(socket_path: Path) -> StatementParserSidecarClient:
    return StatementParserSidecarClient(
        socket_path,
        limits=StatementExtractionLimits(),
        input_max_bytes=1024,
        response_max_bytes=4096,
        wall_timeout_seconds=2,
        cpu_seconds=1,
        memory_bytes=64 * 1024 * 1024,
    )


async def test_client_validates_success_and_invalid_schema(tmp_path: Path) -> None:
    socket_path = tmp_path / "parser.sock"
    responses: list[dict[str, object]] = [
        {
            "ok": True,
            "result": {"text_by_page": ["ok"], "tables_by_page": [], "metadata": {}},
        },
        {"ok": True, "result": {"text_by_page": "not-a-list"}},
    ]

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await read_frame(reader, maximum=MAX_HEADER_BYTES)
        await reader.readexactly(4)
        await write_frame(writer, encode_json(responses.pop(0), maximum=4096))
        writer.close()

    server = await asyncio.start_unix_server(handler, path=socket_path)
    source = tmp_path / "input.pdf"
    source.write_bytes(b"test")
    async with server:
        extracted = await client(socket_path).extract(source)
        assert extracted.text_by_page == ["ok"]
        with pytest.raises(ParserInvalidResultError, match="invalid_result"):
            await client(socket_path).extract(source)
