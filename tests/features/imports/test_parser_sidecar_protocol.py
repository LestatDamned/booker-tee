import asyncio
import struct

import pytest

from app.features.imports.parsers.sidecar.protocol import (
    ParserInvalidResultError,
    ParserUnavailableError,
    read_frame,
)


async def test_protocol_rejects_oversized_and_truncated_frames() -> None:
    oversized = asyncio.StreamReader()
    oversized.feed_data(struct.pack("!I", 5))
    oversized.feed_eof()
    with pytest.raises(ParserInvalidResultError, match="frame_too_large"):
        await read_frame(oversized, maximum=4)

    truncated = asyncio.StreamReader()
    truncated.feed_data(struct.pack("!I", 4) + b"x")
    truncated.feed_eof()
    with pytest.raises(ParserUnavailableError, match="connection_closed"):
        await read_frame(truncated, maximum=4)
