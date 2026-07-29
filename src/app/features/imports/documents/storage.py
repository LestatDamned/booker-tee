from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePath
from re import sub
from uuid import UUID

from fastapi import UploadFile

from app.features.imports.documents.errors import UploadTooLargeError


@dataclass(frozen=True)
class StoredUpload:
    storage_key: str
    path: Path
    sha256_hash: str
    file_size_bytes: int


class UploadStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    async def save_upload(
        self,
        upload_file: UploadFile,
        *,
        workspace_id: UUID,
        document_id: UUID,
        max_bytes: int | None = None,
    ) -> StoredUpload:
        return await self._save(
            upload_file,
            workspace_id=workspace_id,
            document_id=document_id,
            filename_sanitizer=sanitize_upload_filename,
            max_bytes=max_bytes,
        )

    async def inspect_upload(
        self,
        upload_file: UploadFile,
        *,
        max_bytes: int | None = None,
    ) -> tuple[str, int]:
        digest = sha256()
        size = 0
        while chunk := await upload_file.read(1024 * 1024):
            size += len(chunk)
            if max_bytes is not None and size > max_bytes:
                await upload_file.seek(0)
                raise UploadTooLargeError("Файл превышает допустимый размер.")
            digest.update(chunk)
        await upload_file.seek(0)
        return digest.hexdigest(), size

    async def delete_stored_upload(self, stored_upload: StoredUpload) -> None:
        stored_upload.path.unlink(missing_ok=True)
        try:
            stored_upload.path.parent.rmdir()
        except OSError:
            pass

    async def _save(
        self,
        upload_file: UploadFile,
        *,
        workspace_id: UUID,
        document_id: UUID,
        filename_sanitizer: Callable[[str], str],
        max_bytes: int | None = None,
    ) -> StoredUpload:
        original_name = upload_file.filename or "statement.pdf"
        safe_name = filename_sanitizer(original_name)
        storage_key = f"{workspace_id}/{document_id}/{safe_name}"
        target_path = self.root_dir / storage_key
        target_path.parent.mkdir(parents=True, exist_ok=True)

        digest = sha256()
        size = 0
        with target_path.open("wb") as target_file:
            while chunk := await upload_file.read(1024 * 1024):
                size += len(chunk)
                if max_bytes is not None and size > max_bytes:
                    target_file.close()
                    target_path.unlink(missing_ok=True)
                    await upload_file.seek(0)
                    raise UploadTooLargeError("Файл превышает допустимый размер.")
                digest.update(chunk)
                target_file.write(chunk)

        await upload_file.seek(0)
        return StoredUpload(
            storage_key=storage_key,
            path=target_path,
            sha256_hash=digest.hexdigest(),
            file_size_bytes=size,
        )


def sanitize_upload_filename(filename: str) -> str:
    name = PurePath(filename).name.strip() or "statement"
    return sub(r"[^A-Za-z0-9._-]+", "_", name) or "statement"
