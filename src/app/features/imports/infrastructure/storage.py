from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePath
from re import sub
from uuid import UUID

from fastapi import UploadFile


@dataclass(frozen=True)
class StoredUpload:
    storage_key: str
    path: Path
    sha256_hash: str
    file_size_bytes: int


class UploadStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    async def save_pdf(
        self,
        upload_file: UploadFile,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> StoredUpload:
        original_name = upload_file.filename or "statement.pdf"
        safe_name = sanitize_filename(original_name)
        storage_key = f"{workspace_id}/{document_id}/{safe_name}"
        target_path = self.root_dir / storage_key
        target_path.parent.mkdir(parents=True, exist_ok=True)

        digest = sha256()
        size = 0
        with target_path.open("wb") as target_file:
            while chunk := await upload_file.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
                target_file.write(chunk)

        await upload_file.seek(0)
        return StoredUpload(
            storage_key=storage_key,
            path=target_path,
            sha256_hash=digest.hexdigest(),
            file_size_bytes=size,
        )


def sanitize_filename(filename: str) -> str:
    name = PurePath(filename).name.strip() or "statement.pdf"
    name = sub(r"[^A-Za-z0-9._-]+", "_", name)
    if not name.lower().endswith(".pdf"):
        return f"{name}.pdf"
    return name
