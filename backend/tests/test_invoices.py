import io
import time
from pathlib import Path

from sqlalchemy.exc import OperationalError

from backend.extensions import db
from backend.models import Invoice

SUPPLIER = "0x1111111111111111111111111111111111111111"
BUYER = "0x2222222222222222222222222222222222222222"
OUTSIDER = "0x3333333333333333333333333333333333333333"
PDF = b"%PDF-1.7\nminimal test document\n%%EOF"


def _login(client, wallet=SUPPLIER):
    with client.session_transaction() as session:
        session["wallet_address"] = wallet


def _roles(app, supplier="SUPPLIER", buyer="CORE_ENTERPRISE"):
    service = app.config["ROLE_SERVICE"]
    service.roles[SUPPLIER] = supplier
    service.roles[BUYER] = buyer


def _upload(client, *, content=PDF, filename="invoice.pdf", mimetype="application/pdf",
            supplier=SUPPLIER, buyer=BUYER, amount="123456789", due=None,
            invoice_no="INV-001"):
    return client.post(
        "/api/invoices/file",
        data={
            "file": (io.BytesIO(content), filename, mimetype),
            "invoice_no": invoice_no,
            "supplier": supplier,
            "buyer": buyer,
            "amount": amount,
            "due_date": str(due or int(time.time()) + 3600),
        },
        content_type="multipart/form-data",
    )


def test_valid_pdf_upload(client, app):
    _login(client)
    _roles(app)
    response = _upload(client)
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["file_hash"].startswith("0x") and len(payload["file_hash"]) == 66
    with app.app_context():
        item = db.session.get(Invoice, payload["invoice_id"])
        assert Path(app.config["UPLOAD_FOLDER"], item.storage_key).is_file()


def test_fake_pdf_extension_is_rejected(client, app):
    _login(client)
    _roles(app)
    response = _upload(client, content=b"not a pdf")
    assert response.get_json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_wrong_pdf_mime_is_rejected(client, app):
    _login(client)
    _roles(app)
    response = _upload(client, mimetype="text/plain")
    assert response.get_json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_oversized_file_is_rejected(client, app):
    _login(client)
    _roles(app)
    app.config["MAX_CONTENT_LENGTH"] = 100
    response = _upload(client, content=b"%PDF-" + b"x" * 200)
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "FILE_TOO_LARGE"


def test_path_traversal_filename_is_sanitized(client, app):
    _login(client)
    _roles(app)
    assert _upload(client, filename="../../secret.pdf").status_code == 201
    with app.app_context():
        item = Invoice.query.one()
        assert item.original_filename == "secret.pdf"
        assert ".." not in item.storage_key


def test_supplier_must_match_session(client, app):
    _login(client, OUTSIDER)
    _roles(app)
    response = _upload(client)
    assert response.get_json()["error"]["code"] == "ADDRESS_MISMATCH"


def test_supplier_role_is_required(client, app):
    _login(client)
    _roles(app, supplier="NONE")
    response = _upload(client)
    assert response.get_json()["error"]["code"] == "ROLE_REQUIRED"


def test_buyer_role_is_required(client, app):
    _login(client)
    _roles(app, buyer="NONE")
    response = _upload(client)
    assert response.get_json()["error"]["code"] == "ROLE_REQUIRED"


def test_amount_must_be_positive_integer(client, app):
    _login(client)
    _roles(app)
    for value in ("1.5", "0", "-1"):
        response = _upload(client, amount=value, invoice_no="INV-" + value)
        assert response.get_json()["error"]["code"] == "INVALID_AMOUNT"


def test_due_date_must_be_in_future(client, app):
    _login(client)
    _roles(app)
    response = _upload(client, due=int(time.time()) - 1)
    assert response.get_json()["error"]["code"] == "INVALID_DUE_DATE"


def test_duplicate_invoice_upload_is_rejected(client, app):
    _login(client)
    _roles(app)
    assert _upload(client).status_code == 201
    response = _upload(client)
    assert response.get_json()["error"]["code"] == "INVOICE_ALREADY_UPLOADED"


def test_unauthorized_download_is_rejected(client, app):
    _login(client)
    _roles(app)
    invoice_id = _upload(client).get_json()["invoice_id"]
    _login(client, OUTSIDER)
    response = client.get(f"/api/invoices/{invoice_id}/file")
    assert response.status_code == 403


def test_missing_invoice_file_returns_stable_error(client, app):
    _login(client)
    _roles(app)
    invoice_id = _upload(client).get_json()["invoice_id"]
    with app.app_context():
        item = db.session.get(Invoice, invoice_id)
        Path(app.config["UPLOAD_FOLDER"], item.storage_key).unlink()
    response = client.get(f"/api/invoices/{invoice_id}/file")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "FILE_NOT_FOUND"


def test_large_amount_round_trips_as_string(client, app):
    _login(client)
    _roles(app)
    amount = str(2**256 - 1)
    assert _upload(client, amount=amount).status_code == 201
    with app.app_context():
        assert Invoice.query.one().to_dict()["amount"] == amount


def test_database_failure_removes_new_file(client, app, monkeypatch):
    _login(client)
    _roles(app)
    upload_dir = Path(app.config["UPLOAD_FOLDER"])

    def fail_commit():
        raise OperationalError("insert", {}, RuntimeError("test failure"))

    monkeypatch.setattr(db.session, "commit", fail_commit)
    response = _upload(client)
    assert response.status_code == 500
    assert list(upload_dir.rglob("*.pdf")) == []


def test_supplier_can_download_pdf(client, app):
    _login(client)
    _roles(app)
    invoice_id = _upload(client).get_json()["invoice_id"]
    response = client.get(f"/api/invoices/{invoice_id}/file")
    assert response.status_code == 200
    assert response.data == PDF
    assert response.headers["X-Content-Type-Options"] == "nosniff"
