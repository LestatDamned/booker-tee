import asyncio
import json
import struct
from enum import StrEnum

PROTOCOL_VERSION = 1
RESOURCE_LIMIT_EXIT_CODE = 75
MAX_HEADER_BYTES = 16 * 1024
MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
FRAME_SIZE = 4


class ParserErrorCode(StrEnum):
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    UNAVAILABLE = "unavailable"
    INVALID_RESULT = "invalid_result"


class ParserSidecarError(RuntimeError):
    code = ParserErrorCode.UNAVAILABLE


class ParserTimeoutError(ParserSidecarError):
    code = ParserErrorCode.TIMEOUT


class ParserResourceLimitError(ParserSidecarError):
    code = ParserErrorCode.RESOURCE_LIMIT


class ParserUnavailableError(ParserSidecarError):
    code = ParserErrorCode.UNAVAILABLE


class ParserInvalidResultError(ParserSidecarError):
    code = ParserErrorCode.INVALID_RESULT


async def read_frame(reader: asyncio.StreamReader, *, maximum: int) -> bytes:
    try:
        size = struct.unpack("!I", await reader.readexactly(FRAME_SIZE))[0]
        if size > maximum:
            raise ParserInvalidResultError("frame_too_large")
        return await reader.readexactly(size)
    except (asyncio.IncompleteReadError, struct.error) as error:
        raise ParserUnavailableError("connection_closed") from error


async def write_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    writer.write(struct.pack("!I", len(payload)))
    writer.write(payload)
    await writer.drain()


def encode_json(payload: dict[str, object], *, maximum: int) -> bytes:
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    if len(encoded) > maximum:
        raise ParserInvalidResultError("json_too_large")
    return encoded


def decode_json(payload: bytes) -> dict[str, object]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ParserInvalidResultError("invalid_json") from error
    if not isinstance(decoded, dict):
        raise ParserInvalidResultError("invalid_envelope")
    return decoded
