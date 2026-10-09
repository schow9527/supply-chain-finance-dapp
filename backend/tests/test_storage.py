import io
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from backend.storage import LocalStorage, S3Storage, StorageError, invoice_object_key


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
