"""Private local and S3-compatible object storage adapters."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from botocore.exceptions import ClientError
from flask import current_app


class StorageError(RuntimeError):
    """A stable storage-layer failure that does not expose provider details."""


def validate_key(key: str) -> str:
    path = PurePosixPath(key)
    if not key or key.startswith("/") or "\\" in key or ".." in path.parts:
        raise ValueError("invalid storage key")
    return str(path)


def invoice_object_key(chain_id: int, supplier: str) -> str:
    supplier = supplier.lower()
    if not supplier.startswith("0x") or len(supplier) != 42:
        raise ValueError("invalid supplier")
    return f"invoices/{int(chain_id)}/{supplier}/{uuid.uuid4().hex}.pdf"


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        candidate = (self.root / validate_key(key)).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return candidate

    def save(self, key: str, stream: BinaryIO) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".tmp-{uuid.uuid4().hex}")
        try:
            with temporary.open("xb") as output:
                while chunk := stream.read(1024 * 1024):
                    output.write(chunk)
            os.replace(temporary, target)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError("STORAGE_UNAVAILABLE") from exc

    def open(self, key: str) -> BinaryIO:
        try:
            return self._path(key).open("rb")
        except OSError as exc:
            raise FileNotFoundError(key) from exc

    def read(self, key: str) -> bytes:
        with self.open(key) as source:
            return source.read()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def health_check(self) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            return self.root.is_dir()
        except OSError:
            return False


class RenderDiskStorage:
    """Single-instance storage rooted in a mounted Render persistent disk."""

    def __init__(self, mount_path: str | Path, upload_folder: str | Path,
                 min_free_bytes: int = 100 * 1024 * 1024):
        raw_mount = Path(mount_path)
        raw_upload = Path(upload_folder)
        if not raw_mount.is_absolute() or not raw_upload.is_absolute():
            raise ValueError("Render disk paths must be absolute")
        if not raw_mount.exists() or not raw_mount.is_dir():
            raise ValueError("Render disk mount path does not exist")
        if not raw_upload.exists() or not raw_upload.is_dir():
            raise ValueError("UPLOAD_FOLDER does not exist")
        self.mount_path = raw_mount.resolve(strict=True)
        self.root = raw_upload.resolve(strict=True)
        if not self.root.is_relative_to(self.mount_path):
            raise ValueError("UPLOAD_FOLDER must be inside the Render disk mount")
        self.min_free_bytes = int(min_free_bytes)

    def _path(self, key: str) -> Path:
        candidate = (self.root / validate_key(key)).resolve(strict=False)
        if not candidate.is_relative_to(self.mount_path):
            raise ValueError("invalid storage key")
        return candidate

    def _ensure_parent(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = target.parent.resolve(strict=True)
        if not resolved_parent.is_relative_to(self.mount_path):
            raise ValueError("storage path escaped Render disk mount")

    def save(self, key: str, stream: BinaryIO) -> None:
        target = self._path(key)
        temporary = target.with_name(f".tmp-{uuid.uuid4().hex}")
        try:
            self._ensure_parent(target)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                while chunk := stream.read(1024 * 1024):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
            os.chmod(target, 0o600)
            self._fsync_directory(target.parent)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, ValueError):
                raise
            raise StorageError("STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def open(self, key: str) -> BinaryIO:
        try:
            return self._path(key).open("rb")
        except OSError as exc:
            raise FileNotFoundError(key) from exc

    def read(self, key: str) -> bytes:
        with self.open(key) as source:
            return source.read()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def health_details(self) -> dict:
        if not self.mount_path.is_dir() or not self.root.is_relative_to(self.mount_path):
            return {"status": "unavailable", "free_space": "unknown"}
        probe = self.root / f".storage-health-{uuid.uuid4().hex}"
        try:
            descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(b"ok")
                output.flush()
                os.fsync(output.fileno())
            probe.unlink()
            free = shutil.disk_usage(self.root).free
            if free < self.min_free_bytes:
                return {"status": "unavailable", "free_space": "low"}
            category = "healthy" if free >= self.min_free_bytes * 5 else "adequate"
            return {"status": "ok", "free_space": category}
        except Exception:
            probe.unlink(missing_ok=True)
            return {"status": "unavailable", "free_space": "unknown"}

    def health_check(self) -> bool:
        return self.health_details()["status"] == "ok"


class S3Storage:
    def __init__(self, *, bucket: str, region: str, access_key_id: str,
                 secret_access_key: str, endpoint_url: str = "", key_prefix: str = "",
                 client=None):
        if not bucket or not access_key_id or not secret_access_key:
            raise ValueError("S3 bucket and credentials are required")
        self.bucket = bucket
        self.key_prefix = key_prefix.strip("/")
        if client is None:
            import boto3
            client = boto3.client(
                "s3", region_name=region, endpoint_url=endpoint_url or None,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
        self.client = client

    def _key(self, key: str) -> str:
        key = validate_key(key)
        return f"{self.key_prefix}/{key}" if self.key_prefix else key

    def save(self, key: str, stream: BinaryIO) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=self._key(key), Body=stream,
                ContentType="application/pdf",
            )
        except Exception as exc:
            raise StorageError("STORAGE_UNAVAILABLE") from exc

    def open(self, key: str) -> BinaryIO:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=self._key(key))["Body"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise StorageError("STORAGE_UNAVAILABLE") from exc
        except Exception as exc:
            raise StorageError("STORAGE_UNAVAILABLE") from exc

    def read(self, key: str) -> bytes:
        stream = self.open(key)
        try:
            return stream.read()
        finally:
            stream.close()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}:
                return False
            raise StorageError("STORAGE_UNAVAILABLE") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(key))
        except Exception as exc:
            raise StorageError("STORAGE_UNAVAILABLE") from exc

    def health_check(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False


def get_storage():
    injected = current_app.config.get("STORAGE_SERVICE")
    if injected is not None:
        return injected
    cached = current_app.extensions.get("private_storage")
    if cached is not None:
        return cached
    backend = current_app.config.get("STORAGE_BACKEND")
    if backend == "s3":
        storage = S3Storage(
            bucket=current_app.config.get("S3_BUCKET", ""),
            region=current_app.config.get("S3_REGION", "us-east-1"),
            endpoint_url=current_app.config.get("S3_ENDPOINT_URL", ""),
            access_key_id=current_app.config.get("S3_ACCESS_KEY_ID", ""),
            secret_access_key=current_app.config.get("S3_SECRET_ACCESS_KEY", ""),
            key_prefix=current_app.config.get("S3_KEY_PREFIX", ""),
            client=current_app.config.get("S3_CLIENT"),
        )
    elif backend == "render_disk":
        storage = RenderDiskStorage(
            current_app.config.get("RENDER_DISK_MOUNT_PATH", ""),
            current_app.config.get("UPLOAD_FOLDER", ""),
            current_app.config.get("RENDER_DISK_MIN_FREE_BYTES", 100 * 1024 * 1024),
        )
    elif backend == "local":
        storage = LocalStorage(current_app.config["UPLOAD_FOLDER"])
    else:
        raise StorageError("STORAGE_DISABLED")
    current_app.extensions["private_storage"] = storage
    return storage
