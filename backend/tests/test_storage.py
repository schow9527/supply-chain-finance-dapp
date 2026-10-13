import io
import os
import stat
from types import SimpleNamespace
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from sqlalchemy.exc import OperationalError

from backend.storage import (
    LocalStorage, RenderDiskStorage, S3Storage, StorageError, invoice_object_key,
)


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.healthy = True
        self.fail_put = False

    def put_object(self, Bucket, Key, Body, ContentType):
        if self.fail_put:
            raise ClientError({"Error": {"Code": "ServiceUnavailable"}}, "PutObject")
        self.objects[(Bucket, Key)] = Body.read()

    def get_object(self, Bucket, Key):
        try:
            return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}
        except KeyError as exc:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject") from exc

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)

    def head_bucket(self, Bucket):
        if not self.healthy:
            raise ClientError({"Error": {"Code": "503"}}, "HeadBucket")


def _s3(client=None):
    return S3Storage(bucket="private-test", region="us-east-1",
                     access_key_id="test", secret_access_key="test",
                     key_prefix="prefix", client=client or FakeS3Client())


def test_local_storage_round_trip_health_and_delete(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.save("invoices/1/a/file.pdf", io.BytesIO(b"pdf"))
    assert storage.exists("invoices/1/a/file.pdf")
    assert storage.read("invoices/1/a/file.pdf") == b"pdf"
    assert storage.health_check()
    storage.delete("invoices/1/a/file.pdf")
    assert not storage.exists("invoices/1/a/file.pdf")


@pytest.mark.parametrize("key", ["../secret", "/absolute", "a\\b.pdf"])
def test_storage_rejects_path_traversal(tmp_path, key):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).save(key, io.BytesIO(b"x"))


def test_invoice_keys_are_unique_and_ignore_original_names():
    first = invoice_object_key(11155111, "0x" + "a" * 40)
    second = invoice_object_key(11155111, "0x" + "a" * 40)
    assert first != second
    assert first.startswith("invoices/11155111/0x" + "a" * 40 + "/")
    assert first.endswith(".pdf")


def test_s3_storage_upload_download_exists_delete_and_health():
    client = FakeS3Client()
    storage = _s3(client)
    storage.save("invoices/1/a/file.pdf", io.BytesIO(b"pdf"))
    assert storage.exists("invoices/1/a/file.pdf")
    assert storage.read("invoices/1/a/file.pdf") == b"pdf"
    assert storage.health_check()
    storage.delete("invoices/1/a/file.pdf")
    assert not storage.exists("invoices/1/a/file.pdf")


def test_s3_storage_maps_upload_failure_and_missing_object():
    client = FakeS3Client()
    client.fail_put = True
    storage = _s3(client)
    with pytest.raises(StorageError, match="STORAGE_UNAVAILABLE"):
        storage.save("invoices/1/a/file.pdf", io.BytesIO(b"pdf"))
    with pytest.raises(FileNotFoundError):
        storage.open("invoices/1/a/missing.pdf")
    client.healthy = False
    assert storage.health_check() is False


def test_invoice_upload_storage_failure_is_stable(client, app):
    from backend.tests.test_invoices import _login, _roles, _upload

    class FailingStorage:
        def save(self, _key, _stream):
            raise StorageError("STORAGE_UNAVAILABLE")

    app.config["STORAGE_SERVICE"] = FailingStorage()
    _login(client)
    _roles(app)
    response = _upload(client)
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "STORAGE_UNAVAILABLE"


def test_render_disk_atomic_round_trip_and_permissions(tmp_path, monkeypatch):
    storage = RenderDiskStorage(tmp_path, tmp_path, min_free_bytes=1)
    replacements = []
    original_replace = os.replace

    def tracked_replace(source, target):
        replacements.append((Path(source), Path(target)))
        return original_replace(source, target)

    monkeypatch.setattr("backend.storage.os.replace", tracked_replace)
    key = "invoices/11155111/supplier/file.pdf"
    storage.save(key, io.BytesIO(b"pdf"))
    assert storage.read(key) == b"pdf"
    assert len(replacements) == 1
    assert replacements[0][0].parent == replacements[0][1].parent
    if os.name != "nt":
        assert stat.S_IMODE((tmp_path / key).stat().st_mode) == 0o600


@pytest.mark.parametrize("mount,upload", [
    ("relative", "relative"),
    ("relative", "C:/absolute"),
])
def test_render_disk_rejects_relative_paths(mount, upload):
    with pytest.raises(ValueError, match="absolute"):
        RenderDiskStorage(mount, upload)


def test_render_disk_rejects_upload_folder_outside_mount(tmp_path):
    mount = tmp_path / "mount"
    outside = tmp_path / "outside"
    mount.mkdir()
    outside.mkdir()
    with pytest.raises(ValueError, match="inside"):
        RenderDiskStorage(mount, outside)


def test_render_disk_rejects_missing_mount(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="does not exist"):
        RenderDiskStorage(missing, missing)


def test_render_disk_rejects_dotdot_and_symlink_escape(tmp_path, monkeypatch):
    mount = tmp_path / "mount"
    outside = tmp_path / "outside"
    mount.mkdir()
    outside.mkdir()
    storage = RenderDiskStorage(mount, mount)
    with pytest.raises(ValueError):
        storage.save("../escape.pdf", io.BytesIO(b"x"))
    link = mount / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        original_resolve = Path.resolve

        def simulate_symlink(path, strict=False):
            if "link" in path.parts:
                return outside / path.name
            return original_resolve(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", simulate_symlink)
    with pytest.raises(ValueError, match="invalid storage key"):
        storage.save("link/escape.pdf", io.BytesIO(b"x"))


def test_render_disk_health_checks_write_delete_and_space_without_business_deletion(
        tmp_path, monkeypatch):
    business = tmp_path / "invoices" / "kept.pdf"
    business.parent.mkdir()
    business.write_bytes(b"keep")
    storage = RenderDiskStorage(tmp_path, tmp_path, min_free_bytes=100)
    monkeypatch.setattr("backend.storage.shutil.disk_usage", lambda _path: SimpleNamespace(free=1000))
    details = storage.health_details()
    assert details == {"status": "ok", "free_space": "healthy"}
    assert business.read_bytes() == b"keep"
    assert not list(tmp_path.glob(".storage-health-*"))


def test_render_disk_health_rejects_low_space_and_unwritable_directory(tmp_path, monkeypatch):
    storage = RenderDiskStorage(tmp_path, tmp_path, min_free_bytes=100)
    monkeypatch.setattr("backend.storage.shutil.disk_usage", lambda _path: SimpleNamespace(free=50))
    assert storage.health_details() == {"status": "unavailable", "free_space": "low"}
    monkeypatch.setattr("backend.storage.os.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError()))
    assert storage.health_details() == {"status": "unavailable", "free_space": "unknown"}


def test_render_disk_invoice_download_auth_missing_and_unique_names(client, app, tmp_path):
    from backend.models import Invoice
    from backend.tests.test_invoices import OUTSIDER, SUPPLIER, _login, _roles, _upload

    storage = RenderDiskStorage(tmp_path, tmp_path, min_free_bytes=1)
    app.config["STORAGE_SERVICE"] = storage
    _login(client)
    _roles(app)
    first = _upload(client, filename="same.pdf", invoice_no="DISK-1")
    second = _upload(client, filename="same.pdf", invoice_no="DISK-2")
    assert first.status_code == second.status_code == 201
    with app.app_context():
        items = Invoice.query.order_by(Invoice.id).all()
        assert items[0].storage_key != items[1].storage_key
        first_id, first_key = items[0].id, items[0].storage_key
    _login(client, OUTSIDER)
    assert client.get(f"/api/invoices/{first_id}/file").status_code == 403
    storage.delete(first_key)
    _login(client, SUPPLIER)
    missing = client.get(f"/api/invoices/{first_id}/file")
    assert missing.status_code == 404
    assert missing.get_json()["error"]["code"] == "FILE_NOT_FOUND"


def test_render_disk_database_failure_removes_file(client, app, tmp_path, monkeypatch):
    from backend.extensions import db
    from backend.tests.test_invoices import _login, _roles, _upload

    storage = RenderDiskStorage(tmp_path, tmp_path, min_free_bytes=1)
    app.config["STORAGE_SERVICE"] = storage
    _login(client)
    _roles(app)

    def fail_commit():
        raise OperationalError("insert", {}, RuntimeError("test failure"))

    monkeypatch.setattr(db.session, "commit", fail_commit)
    response = _upload(client, invoice_no="DISK-ROLLBACK")
    assert response.status_code == 500
    assert list(tmp_path.rglob("*.pdf")) == []
