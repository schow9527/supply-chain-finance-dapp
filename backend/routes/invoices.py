"""Authenticated invoice PDF upload and authorized download."""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from backend.auth import require_auth
from backend.errors import api_error
from backend.extensions import db
from backend.models import Invoice
from backend.services.blockchain import RpcUnavailable, get_role_service
from backend.services.validation import clean_text, normalize_wallet

invoices_bp = Blueprint("invoices", __name__, url_prefix="/api/invoices")


def _role_or_error(wallet: str, expected: str):
    try:
        role = get_role_service().get_role(wallet)
    except RpcUnavailable:
        return api_error("RPC_UNAVAILABLE", "On-chain role verification is unavailable.", 503)
    if role != expected:
        return api_error("ROLE_REQUIRED", f"Wallet must have the {expected} role.", 403)
    return None


@invoices_bp.post("/file")
@require_auth
def upload_invoice_file():
    if request.content_length and request.content_length > current_app.config["MAX_CONTENT_LENGTH"]:
        return api_error("FILE_TOO_LARGE", "The uploaded file is too large.", 413)
    supplier = normalize_wallet(request.form.get("supplier"))
    buyer = normalize_wallet(request.form.get("buyer"))
    if not supplier or not buyer:
        return api_error("INVALID_ADDRESS", "Supplier and buyer addresses must be valid.", 422)
    if supplier != g.wallet_address:
        return api_error("ADDRESS_MISMATCH", "Supplier must match the authenticated wallet.", 403)
    role_error = _role_or_error(supplier, "SUPPLIER")
    if role_error:
        return role_error
    role_error = _role_or_error(buyer, "CORE_ENTERPRISE")
    if role_error:
        return role_error

    invoice_no = clean_text(request.form.get("invoice_no"), maximum=100)
    amount_text = request.form.get("amount", "")
    due_text = request.form.get("due_date", "")
    if not invoice_no:
        return api_error("INVALID_INVOICE", "Invoice number is invalid.", 422)
    if not amount_text.isdigit() or int(amount_text) <= 0:
        return api_error("INVALID_AMOUNT", "Amount must be a positive integer.", 422)
    try:
        due_date = int(due_text)
    except (TypeError, ValueError):
        return api_error("INVALID_DUE_DATE", "Due date must be a future Unix timestamp.", 422)
    if due_date <= int(time.time()):
        return api_error("INVALID_DUE_DATE", "Due date must be in the future.", 422)

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return api_error("INVALID_FILE_TYPE", "A PDF file is required.", 422)
    original_name = secure_filename(upload.filename) or "invoice.pdf"
    if Path(original_name).suffix.lower() != ".pdf":
        return api_error("INVALID_FILE_TYPE", "Only PDF files are accepted.", 422)
    if upload.mimetype != "application/pdf":
        return api_error("INVALID_FILE_TYPE", "The uploaded MIME type is not PDF.", 422)
    header = upload.stream.read(5)
    if header != b"%PDF-":
        return api_error("INVALID_FILE_TYPE", "The uploaded file is not a valid PDF.", 422)
    upload.stream.seek(0)

    duplicate = Invoice.query.filter_by(
        chain_id=current_app.config["CHAIN_ID"],
        invoice_no=invoice_no,
        supplier_address=supplier,
        buyer_address=buyer,
    ).first()
    if duplicate and duplicate.status != "REJECTED":
        return api_error("INVOICE_ALREADY_UPLOADED", "This invoice is already uploaded.", 409)

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4().hex}.pdf"
    final_path = upload_dir / storage_key
    temp_path = upload_dir / f".tmp-{uuid.uuid4().hex}"
    digest = hashlib.sha256()
    total = 0
    try:
        with temp_path.open("xb") as target:
            while chunk := upload.stream.read(1024 * 1024):
                total += len(chunk)
                if total > current_app.config["MAX_CONTENT_LENGTH"]:
                    raise OverflowError
                digest.update(chunk)
                target.write(chunk)
        os.replace(temp_path, final_path)
    except OverflowError:
        temp_path.unlink(missing_ok=True)
        return api_error("FILE_TOO_LARGE", "The uploaded file is too large.", 413)
    except OSError:
        temp_path.unlink(missing_ok=True)
        return api_error("FILE_STORAGE_ERROR", "The PDF could not be stored.", 500)

    item = duplicate or Invoice()
    item.chain_id = current_app.config["CHAIN_ID"]
    item.invoice_no = invoice_no
    item.supplier_address = supplier
    item.buyer_address = buyer
    item.amount = int(amount_text)
    item.due_date = due_date
    item.file_hash = "0x" + digest.hexdigest()
    item.storage_key = storage_key
    item.original_filename = original_name
    item.status = "FILE_UPLOADED"
    item.reject_reason = None
    if item.id is None:
        db.session.add(item)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        final_path.unlink(missing_ok=True)
        return api_error("DATABASE_ERROR", "Invoice metadata could not be saved.", 500)
    return jsonify(
        {
            "invoice_id": item.id,
            "file_hash": item.file_hash,
            "file_url": f"/api/invoices/{item.id}/file",
            "status": item.status,
        }
    ), 201


@invoices_bp.get("/<int:invoice_id>/file")
@require_auth
def download_invoice_file(invoice_id: int):
    item = db.session.get(Invoice, invoice_id)
    if not item:
        return api_error("FILE_NOT_FOUND", "Invoice file was not found.", 404)
    if g.wallet_address not in {item.supplier_address, item.buyer_address}:
        try:
            role = get_role_service().get_role(g.wallet_address)
        except RpcUnavailable:
            return api_error("RPC_UNAVAILABLE", "On-chain role verification is unavailable.", 503)
        if role not in {"ADMIN", "AUDITOR"}:
            return api_error("ROLE_REQUIRED", "You may not download this invoice.", 403)
    path = Path(current_app.config["UPLOAD_FOLDER"]) / (item.storage_key or "")
    if not item.storage_key or not path.is_file():
        return api_error("FILE_NOT_FOUND", "Invoice file was not found.", 404)
    response = send_file(
        path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=item.original_filename or f"invoice-{item.id}.pdf",
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
