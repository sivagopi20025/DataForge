from __future__ import annotations

import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path

from fastapi.responses import FileResponse, RedirectResponse, Response

from backend.app.core.config import Settings, get_settings
from backend.app.models import GeneratedFile


@dataclass(frozen=True)
class StoredObject:
    storage_backend: str
    object_key: str
    file_path: str
    size_bytes: int
    content_type: str


class StorageService:
    storage_backend: str

    def save_generated_file(self, source_path: Path, *, object_key: str) -> StoredObject:
        raise NotImplementedError

    def download_response(self, generated_file: GeneratedFile) -> Response:
        raise NotImplementedError

    def delete_generated_file(self, generated_file: GeneratedFile) -> int:
        raise NotImplementedError


class LocalStorageService(StorageService):
    storage_backend = "local"

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()

    def save_generated_file(self, source_path: Path, *, object_key: str) -> StoredObject:
        safe_key = self._safe_object_key(object_key)
        source = source_path.resolve()
        destination = (self.output_dir / safe_key).resolve()
        if not destination.is_relative_to(self.output_dir):
            raise ValueError(f"Generated file path is outside the configured output directory: {source_path.name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination:
            if not source.is_file():
                raise ValueError(f"Generated file is not available: {source_path.name}")
            shutil.copy2(source, destination)
        if not destination.is_file():
            raise ValueError(f"Generated file is not available: {source_path.name}")
        return StoredObject(
            storage_backend=self.storage_backend,
            object_key=safe_key,
            file_path=str(destination),
            size_bytes=destination.stat().st_size,
            content_type=content_type_for_path(destination),
        )

    def download_response(self, generated_file: GeneratedFile) -> FileResponse:
        path = self.resolve_path(generated_file)
        return FileResponse(
            path=path,
            filename=generated_file.file_name,
            media_type=generated_file.content_type or "application/octet-stream",
        )

    def resolve_path(self, generated_file: GeneratedFile) -> Path:
        object_key = generated_file.object_key or _legacy_local_object_key(generated_file.file_path, self.output_dir)
        safe_key = self._safe_object_key(object_key)
        path = (self.output_dir / safe_key).resolve()
        if not path.is_relative_to(self.output_dir):
            raise ValueError(f"Generated file path is outside the configured output directory: {generated_file.file_name}")
        if not path.exists() or not path.is_file():
            raise ValueError(f"Generated file is no longer available: {generated_file.file_name}")
        return path

    def delete_generated_file(self, generated_file: GeneratedFile) -> int:
        object_key = generated_file.object_key or _legacy_local_object_key(generated_file.file_path, self.output_dir)
        safe_key = self._safe_object_key(object_key)
        path = (self.output_dir / safe_key).resolve()
        if not path.is_relative_to(self.output_dir):
            raise ValueError(f"Generated file path is outside the configured output directory: {generated_file.file_name}")
        if not path.exists() or not path.is_file():
            return 0
        size = path.stat().st_size
        path.unlink()
        _remove_empty_parents(path.parent, stop_at=self.output_dir)
        return size

    @staticmethod
    def _safe_object_key(object_key: str) -> str:
        normalized = Path(object_key)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"Unsafe object key: {object_key}")
        return normalized.as_posix()


class S3CompatibleStorageService(StorageService):
    storage_backend = "s3"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.object_storage_bucket:
            raise ValueError("OBJECT_STORAGE_BUCKET is required for S3-compatible storage")
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError("S3-compatible storage requires optional dependency: boto3") from error
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint_url,
            region_name=settings.object_storage_region,
            aws_access_key_id=settings.object_storage_access_key_id,
            aws_secret_access_key=settings.object_storage_secret_access_key,
        )

    def save_generated_file(self, source_path: Path, *, object_key: str) -> StoredObject:
        source = source_path.resolve()
        if not source.is_file():
            raise ValueError(f"Generated file is not available: {source_path.name}")
        content_type = content_type_for_path(source)
        self.client.upload_file(
            str(source),
            self.settings.object_storage_bucket,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )
        public_url = f"{self.settings.object_storage_base_url.rstrip('/')}/{object_key}" if self.settings.object_storage_base_url else object_key
        return StoredObject(
            storage_backend=self.storage_backend,
            object_key=object_key,
            file_path=public_url,
            size_bytes=source.stat().st_size,
            content_type=content_type,
        )

    def download_response(self, generated_file: GeneratedFile) -> RedirectResponse:
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.object_storage_bucket, "Key": generated_file.object_key},
            ExpiresIn=self.settings.object_storage_presign_seconds,
        )
        return RedirectResponse(url=url)

    def delete_generated_file(self, generated_file: GeneratedFile) -> int:
        self.client.delete_object(
            Bucket=self.settings.object_storage_bucket,
            Key=generated_file.object_key,
        )
        return int(generated_file.size_bytes or 0)


def get_storage_service(settings: Settings | None = None) -> StorageService:
    active_settings = settings or get_settings()
    backend = active_settings.storage_backend.lower().replace("_", "-")
    if backend == "local":
        return LocalStorageService(active_settings.output_dir)
    if backend in {"s3", "s3-compatible", "supabase", "supabase-compatible"}:
        return S3CompatibleStorageService(active_settings)
    raise ValueError(f"Unsupported storage backend: {active_settings.storage_backend}")


def content_type_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _legacy_local_object_key(file_path: str, output_dir: Path) -> str:
    path = Path(file_path).resolve()
    root = output_dir.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Generated file path is outside the configured output directory: {path.name}")
    return path.relative_to(root).as_posix()


def _remove_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path.resolve()
    stop = stop_at.resolve()
    while current != stop and current.is_relative_to(stop):
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
