import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path, PurePath
from re import sub
from uuid import UUID
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile

from app.features.imports.documents.errors import UploadTooLargeError, UploadValidationError
from app.shared.schemas import ApplicationModel

SUPPORTED_STORAGE_EXTENSIONS = frozenset({".pdf", ".xlsx"})
XLSX_REQUIRED_MEMBERS = frozenset({"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"})


class StoredUpload(ApplicationModel):
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
        while chunk := upload_file.file.read(1024 * 1024):
            size += len(chunk)
            if max_bytes is not None and size > max_bytes:
                upload_file.file.seek(0)
                raise UploadTooLargeError("Файл превышает допустимый размер.")
            digest.update(chunk)
        upload_file.file.seek(0)
        return digest.hexdigest(), size

    async def delete_stored_upload(self, stored_upload: StoredUpload) -> None:
        await self.delete_storage_key(stored_upload.storage_key)

    async def delete_storage_key(self, storage_key: str) -> None:
        root_dir, stored_path = resolve_storage_path(self.root_dir, storage_key)
        stored_path.unlink(missing_ok=True)
        remove_empty_upload_directories(stored_path.parent, root_dir)

    def storage_key_exists(self, storage_key: str) -> bool:
        _, stored_path = resolve_storage_path(self.root_dir, storage_key)
        return stored_path.is_file()

    def find_orphan_storage_keys(
        self,
        referenced_keys: set[str],
        *,
        older_than: datetime,
        limit: int,
    ) -> list[str]:
        if limit < 1:
            return []
        if not self.root_dir.exists():
            return []
        root_dir = self.root_dir.resolve()
        orphan_keys: list[str] = []
        for workspace_dir in root_dir.iterdir():
            if workspace_dir.is_symlink() or not workspace_dir.is_dir():
                continue
            for document_dir in workspace_dir.iterdir():
                if document_dir.is_symlink() or not document_dir.is_dir():
                    continue
                for source_file in document_dir.iterdir():
                    if source_file.is_symlink() or not source_file.is_file():
                        continue
                    storage_key = source_file.relative_to(root_dir).as_posix()
                    if (
                        storage_key not in referenced_keys
                        and source_file.stat().st_mtime <= older_than.timestamp()
                    ):
                        orphan_keys.append(storage_key)
                        if len(orphan_keys) == limit:
                            return orphan_keys
        return orphan_keys

    async def _save(
        self,
        upload_file: UploadFile,
        *,
        workspace_id: UUID,
        document_id: UUID,
        max_bytes: int | None = None,
    ) -> StoredUpload:
        extension = Path(upload_file.filename or "").suffix.casefold()
        if extension not in SUPPORTED_STORAGE_EXTENSIONS:
            raise UploadValidationError("Неподдерживаемый формат файла.")

        storage_key = f"{workspace_id}/{document_id}/source{extension}"
        root_dir, target_path = prepare_upload_path(self.root_dir, storage_key)

        digest = sha256()
        size = 0
        created = False
        try:
            descriptor = os.open(
                target_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            created = True
            with os.fdopen(descriptor, "wb") as target_file:
                while chunk := upload_file.file.read(1024 * 1024):
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise UploadTooLargeError("Файл превышает допустимый размер.")
                    digest.update(chunk)
                    target_file.write(chunk)
            target_path.chmod(0o600)
            validate_stored_statement(target_path, extension)
        except FileExistsError as error:
            upload_file.file.seek(0)
            raise UploadValidationError("Файл с таким storage key уже существует.") from error
        except Exception:
            if created:
                target_path.unlink(missing_ok=True)
                remove_empty_upload_directories(target_path.parent, root_dir)
            upload_file.file.seek(0)
            raise

        upload_file.file.seek(0)
        return StoredUpload(
            storage_key=storage_key,
            path=target_path,
            sha256_hash=digest.hexdigest(),
            file_size_bytes=size,
        )


def prepare_upload_path(root_dir: Path, storage_key: str) -> tuple[Path, Path]:
    root_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    root_dir.chmod(0o700)
    resolved_root = root_dir.resolve()
    target_path = (resolved_root / storage_key).resolve()
    ensure_path_within_root(target_path, resolved_root)

    workspace_dir = target_path.parent.parent
    document_dir = target_path.parent
    workspace_dir.mkdir(exist_ok=True, mode=0o700)
    workspace_dir.chmod(0o700)
    document_dir.mkdir(exist_ok=True, mode=0o700)
    document_dir.chmod(0o700)
    return resolved_root, target_path


def resolve_storage_path(root_dir: Path, storage_key: str) -> tuple[Path, Path]:
    root_dir = root_dir.resolve()
    relative_path = Path(storage_key)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise UploadValidationError("Некорректный storage path.")

    candidate = root_dir / relative_path
    current = root_dir
    for part in relative_path.parts:
        current /= part
        if current.is_symlink():
            raise UploadValidationError("Некорректный storage path.")
    resolved_path = candidate.resolve()
    ensure_path_within_root(resolved_path, root_dir)
    return root_dir, resolved_path


def ensure_path_within_root(path: Path, root_dir: Path) -> None:
    if not path.is_relative_to(root_dir):
        raise UploadValidationError("Некорректный storage path.")


def validate_stored_statement(file_path: Path, extension: str) -> None:
    if extension == ".pdf":
        with file_path.open("rb") as source_file:
            signature = source_file.read(5)
        if signature != b"%PDF-":
            raise UploadValidationError("Содержимое файла не соответствует формату PDF.")
        return

    try:
        with ZipFile(file_path) as archive:
            if not XLSX_REQUIRED_MEMBERS.issubset(archive.namelist()):
                raise UploadValidationError("Содержимое файла не соответствует формату XLSX.")
    except BadZipFile as error:
        raise UploadValidationError("Содержимое файла не соответствует формату XLSX.") from error


def remove_empty_upload_directories(directory: Path, root_dir: Path) -> None:
    while directory != root_dir and directory.is_relative_to(root_dir):
        try:
            directory.rmdir()
        except OSError:
            return
        directory = directory.parent


def sanitize_upload_filename(filename: str) -> str:
    name = PurePath(filename).name.strip() or "statement"
    return sub(r"[^A-Za-z0-9._-]+", "_", name) or "statement"
