import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from app.features.imports.parsers.extractors.limits import StatementExtractionLimits
from app.features.imports.parsers.extractors.resolver import SUPPORTED_STATEMENT_EXTENSIONS
from app.features.imports.parsers.sidecar.protocol import (
    MAX_HEADER_BYTES,
    MAX_INPUT_BYTES,
    MAX_RESPONSE_BYTES,
    PROTOCOL_VERSION,
    RESOURCE_LIMIT_EXIT_CODE,
    ParserInvalidResultError,
    decode_json,
    encode_json,
    read_frame,
    write_frame,
)


class ParserSidecarServer:
    def __init__(self, socket_path: Path) -> None:
        self.socket_path = socket_path
        self.job_lock = asyncio.Lock()

    async def serve(self) -> None:
        self.socket_path.parent.mkdir(mode=0o770, parents=True, exist_ok=True)
        self.socket_path.unlink(missing_ok=True)
        server = await asyncio.start_unix_server(self._handle, path=self.socket_path)
        self.socket_path.chmod(0o660)
        async with server:
            await server.serve_forever()

    async def _handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            header = decode_json(await read_frame(reader, maximum=MAX_HEADER_BYTES))
            if header.get("version") != PROTOCOL_VERSION:
                raise ParserInvalidResultError("invalid_version")
            if header.get("command") == "PING":
                await self._respond(writer, {"ok": True, "result": "PONG"})
                return
            if self.job_lock.locked():
                await self._respond(writer, {"ok": False, "error": "busy"})
                return
            async with self.job_lock:
                await self._extract(reader, writer, header)
        except (ParserInvalidResultError, ValueError, TypeError, KeyError):
            await self._respond(writer, {"ok": False, "error": "invalid_result"})
        except (ConnectionError, OSError, asyncio.IncompleteReadError):
            return
        finally:
            writer.close()
            await writer.wait_closed()

    async def _extract(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        header: dict[str, object],
    ) -> None:
        extension = header["extension"]
        byte_count = header["byte_count"]
        response_max = min(_required_positive_int(header, "response_max_bytes"), MAX_RESPONSE_BYTES)
        wall_timeout = min(_required_positive_int(header, "wall_timeout_seconds"), 60)
        cpu_seconds = min(_required_positive_int(header, "cpu_seconds"), wall_timeout)
        memory_bytes = min(_required_positive_int(header, "memory_bytes"), 512 * 1024 * 1024)
        limits = StatementExtractionLimits.model_validate(header["limits"])
        if not isinstance(extension, str) or extension not in SUPPORTED_STATEMENT_EXTENSIONS:
            raise ParserInvalidResultError("invalid_extension")
        if not isinstance(byte_count, int) or byte_count < 1 or byte_count > MAX_INPUT_BYTES:
            await self._respond(writer, {"ok": False, "error": "resource_limit"})
            return

        job_path: Path | None = None
        process: asyncio.subprocess.Process | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+b", prefix="statement-", suffix=extension, delete=False
            ) as job:
                os.chmod(job.name, 0o600)
                job_path = Path(job.name)
                remaining = byte_count
                while remaining:
                    chunk = await reader.read(min(64 * 1024, remaining))
                    if not chunk:
                        raise ConnectionError("upload disconnected")
                    job.write(chunk)
                    remaining -= len(chunk)
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-m",
                "app.features.imports.parsers.sidecar.worker",
                str(job_path),
                str(extension),
                json.dumps(limits.model_dump(mode="json"), separators=(",", ":")),
                str(memory_bytes),
                str(cpu_seconds),
                str(response_max),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            assert process.stdout is not None
            output_task = asyncio.create_task(_read_bounded_stdout(process.stdout, response_max))
            disconnect_task = asyncio.create_task(reader.read(1))
            done, pending = await asyncio.wait(
                {output_task, disconnect_task},
                timeout=wall_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                process.kill()
                await process.wait()
                output_task.cancel()
                disconnect_task.cancel()
                await asyncio.gather(output_task, disconnect_task, return_exceptions=True)
                await self._respond(writer, {"ok": False, "error": "timeout"})
                return
            if disconnect_task in done:
                process.kill()
                await process.wait()
                output_task.cancel()
                await asyncio.gather(output_task, return_exceptions=True)
                return
            disconnect_task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            try:
                payload = output_task.result()
            except ParserInvalidResultError:
                process.kill()
                await process.wait()
                await self._respond(writer, {"ok": False, "error": "resource_limit"})
                return
            await process.wait()
            if process.returncode != 0:
                await self._respond(
                    writer,
                    {
                        "ok": False,
                        "error": "resource_limit"
                        if process.returncode == RESOURCE_LIMIT_EXIT_CODE
                        or process.returncode is not None
                        and process.returncode < 0
                        else "invalid_result",
                    },
                )
                return
            result = decode_json(payload)
            await self._respond(writer, {"ok": True, "result": result})
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            raise
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            if job_path is not None:
                job_path.unlink(missing_ok=True)

    @staticmethod
    async def _respond(writer: asyncio.StreamWriter, envelope: dict[str, object]) -> None:
        await write_frame(
            writer,
            encode_json(envelope, maximum=MAX_RESPONSE_BYTES),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(ParserSidecarServer(args.socket).serve())


def _required_positive_int(header: dict[str, object], key: str) -> int:
    value = header[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ParserInvalidResultError(f"invalid_{key}")
    return value


async def _read_bounded_stdout(reader: asyncio.StreamReader, maximum: int) -> bytes:
    output = bytearray()
    while chunk := await reader.read(min(64 * 1024, maximum + 1 - len(output))):
        output.extend(chunk)
        if len(output) > maximum:
            raise ParserInvalidResultError("response_too_large")
    return bytes(output)


if __name__ == "__main__":
    main()
