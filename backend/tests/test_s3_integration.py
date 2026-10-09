"""Opt-in smoke test that touches only one uniquely named object in a test bucket."""

import io
import os
import uuid

import pytest

from backend.storage import S3Storage

pytestmark = pytest.mark.s3


def test_real_s3_private_object_round_trip():
    required = {
        name: os.getenv(name) for name in (
            "S3_TEST_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_REGION"
        )
    }
    if not all(required.values()):
        pytest.skip("explicit S3 test bucket configuration is absent; real S3 validation skipped")
    storage = S3Storage(
        bucket=required["S3_TEST_BUCKET"], region=required["S3_REGION"],
        endpoint_url=os.getenv("S3_ENDPOINT_URL", ""),
        access_key_id=required["S3_ACCESS_KEY_ID"],
        secret_access_key=required["S3_SECRET_ACCESS_KEY"],
        key_prefix=os.getenv("S3_TEST_KEY_PREFIX", "codex-tests"),
    )
    key = f"invoices/11155111/integration/{uuid.uuid4().hex}.pdf"
    try:
        storage.save(key, io.BytesIO(b"%PDF-real-s3-smoke"))
        assert storage.exists(key)
        assert storage.read(key) == b"%PDF-real-s3-smoke"
    finally:
        # Never list or clear a bucket: delete only the unique object created here.
        storage.delete(key)
