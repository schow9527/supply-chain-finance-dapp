"""Read APIs backed exclusively by synchronized database projections."""

from __future__ import annotations

import re
import time
import json
from collections import OrderedDict

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import or_

from backend.auth import require_auth
from backend.errors import api_error
from backend.extensions import db
from backend.models import (
    ChainEvent, Enterprise, FinancingRequest, Holding, Invoice, Quote, Receivable,
)
from backend.services.blockchain import RpcUnavailable, get_role_service
from backend.services.validation import normalize_wallet

queries_bp = Blueprint("queries", __name__, url_prefix="/api")
GLOBAL_ROLES = {"ADMIN", "AUDITOR"}


def _role():
    try:
        return get_role_service().get_role(g.wallet_address), None
    except RpcUnavailable:
        return None, api_error("RPC_UNAVAILABLE", "On-chain role verification is unavailable.", 503)


def _page():
    try:
        page = max(1, int(request.args.get("page", 1)))
        size = min(100, max(1, int(request.args.get("page_size", 50))))
    except ValueError:
        page, size = 1, 50
    return page, size


def _paged_query(query, serializer):
    page, size = _page()
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return jsonify({"items": [serializer(item) for item in items], "page": page,
                    "page_size": size, "total": total})


def _paged_items(items):
    page, size = _page()
    start = (page - 1) * size
    return jsonify({"items": items[start:start + size], "page": page,
                    "page_size": size, "total": len(items)})


def _invoice_json(item):
    data = item.to_dict()
    data["file_url"] = f"/api/invoices/{item.id}/file" if item.storage_key else None
    receivable = None
    if item.onchain_id is not None:
        receivable = Receivable.query.filter_by(
            chain_id=item.chain_id, receivable_id=item.onchain_id
        ).first()
    data["repay_status"] = receivable.status if receivable else "UNPAID"
    data["is_overdue"] = item.due_date < int(time.time()) and data["repay_status"] != "REPAID"
    return data


@queries_bp.get("/invoices")
@require_auth
def list_invoices():
    role, error = _role()
    if error:
        return error
    query = Invoice.query
    requested_supplier = normalize_wallet(request.args.get("supplier")) if request.args.get("supplier") else None
    requested_buyer = normalize_wallet(request.args.get("buyer")) if request.args.get("buyer") else None
    requested_address = normalize_wallet(request.args.get("address")) if request.args.get("address") else None
    if role == "SUPPLIER":
        if any(value and value != g.wallet_address for value in (requested_supplier, requested_address)):
            return api_error("ADDRESS_MISMATCH", "Cannot query another supplier.", 403)
        if requested_buyer:
            return api_error("ROLE_REQUIRED", "Supplier queries cannot select another buyer.", 403)
        query = query.filter_by(supplier_address=g.wallet_address)
    elif role == "CORE_ENTERPRISE":
        if any(value and value != g.wallet_address for value in (requested_buyer, requested_address)):
            return api_error("ADDRESS_MISMATCH", "Cannot query another buyer.", 403)
        if requested_supplier:
            return api_error("ROLE_REQUIRED", "Buyer queries cannot select another supplier.", 403)
        query = query.filter_by(buyer_address=g.wallet_address)
    elif role in GLOBAL_ROLES:
        if requested_supplier:
            query = query.filter_by(supplier_address=requested_supplier)
        if requested_buyer:
            query = query.filter_by(buyer_address=requested_buyer)
        if requested_address:
            query = query.filter(or_(Invoice.supplier_address == requested_address,
                                     Invoice.buyer_address == requested_address))
    else:
        return api_error("ROLE_REQUIRED", "Invoice access is not allowed for this role.", 403)
    if request.args.get("status"):
        query = query.filter_by(status=request.args["status"].upper())
    return _paged_query(query.order_by(Invoice.created_at.desc()), _invoice_json)


@queries_bp.get("/invoices/<int:invoice_id>")
@require_auth
def invoice_detail(invoice_id):
    item = db.session.get(Invoice, invoice_id)
    if item is None:
        return api_error("NOT_FOUND", "Invoice was not found.", 404)
    role, error = _role()
    if error:
        return error
    if role not in GLOBAL_ROLES and g.wallet_address not in {
        item.supplier_address, item.buyer_address
    }:
        return api_error("ROLE_REQUIRED", "Invoice access is not allowed.", 403)
    return jsonify(_invoice_json(item))


def _receivable_json(holding, item):
    return {
        "receivable_id": str(int(item.receivable_id)),
        "balance": str(int(holding.balance)),
        "supplier_address": item.supplier_address,
        "buyer_address": item.buyer_address,
        "face_value": str(int(item.face_value)),
        "due_date": item.due_date,
        "status": item.status,
        "is_frozen": item.frozen,
        "freeze_reason": item.freeze_reason,
        "repay_status": item.status,
        "is_overdue": item.status == "OVERDUE",
    }


@queries_bp.get("/receivables")
@require_auth
def list_receivables():
    role, error = _role()
    if error:
        return error
    holder = normalize_wallet(request.args.get("holder")) if request.args.get("holder") else g.wallet_address
    if not holder:
        return api_error("INVALID_ADDRESS", "Holder address is invalid.", 422)
    if role not in GLOBAL_ROLES and holder != g.wallet_address:
        return api_error("ADDRESS_MISMATCH", "Cannot query another holder.", 403)
    query = db.session.query(Holding, Receivable).join(
        Receivable,
        (Holding.chain_id == Receivable.chain_id)
        & (Holding.receivable_id == Receivable.receivable_id),
    ).filter(Holding.holder_address == holder)
    rows = [row for row in query.all() if int(row[0].balance) > 0]
    return _paged_items([_receivable_json(holding, item) for holding, item in rows])


ACTION_NAMES = {
    "InvoiceSubmitted": "INVOICE_SUBMITTED", "InvoiceConfirmed": "INVOICE_CONFIRMED",
    "InvoiceRejected": "INVOICE_REJECTED", "ReceivableMinted": "RECEIVABLE_MINTED",
    "ReceivableTransferred": "RECEIVABLE_TRANSFERRED", "FinancingRequested": "FINANCING_REQUESTED",
    "QuoteSubmitted": "QUOTE_SUBMITTED", "FinancingFunded": "FINANCING_FUNDED",
    "FinancingCancelled": "FINANCING_CANCELLED", "Repaid": "REPAID",
    "Redeemed": "REDEEMED", "MarkedOverdue": "MARKED_OVERDUE",
    "ReceivableFrozen": "RECEIVABLE_FROZEN", "ReceivableUnfrozen": "RECEIVABLE_UNFROZEN",
}


def _event_action(event):
    if event.event_name in ACTION_NAMES:
        return ACTION_NAMES[event.event_name]
    if event.event_name in {"TransferSingle", "TransferBatch"}:
        if event.event_args.get("from") == "0x0000000000000000000000000000000000000000":
            return "RECEIVABLE_MINTED"
        if event.event_args.get("to") == "0x0000000000000000000000000000000000000000":
            return "REDEEMED"
        return "RECEIVABLE_TRANSFERRED"
    return re.sub(r"(?<!^)(?=[A-Z])", "_", event.event_name).upper()


def _history_json(event):
    args = event.event_args
    action = _event_action(event)
    operator = args.get("operator") or args.get("auditor") or args.get("buyer") or args.get("supplier")
    return {
        "action": action,
        "from_address": args.get("from"), "to_address": args.get("to"),
        "amount": args.get("amount") or args.get("value") or args.get("faceValue"),
        "tx_hash": event.tx_hash, "block_number": event.block_number,
        "timestamp": event.block_timestamp.isoformat(), "operator": operator,
        "title": action.replace("_", " ").title(), "desc": event.event_name,
        "time": event.block_timestamp.isoformat(),
    }


@queries_bp.get("/receivables/<int:receivable_id>/history")
@require_auth
def receivable_history(receivable_id):
    role, error = _role()
    if error:
        return error
    item = Receivable.query.filter_by(
        chain_id=current_app.config["CHAIN_ID"], receivable_id=receivable_id
    ).first()
    if item is None:
        return api_error("NOT_FOUND", "Receivable was not found.", 404)
    holding = Holding.query.filter_by(chain_id=item.chain_id, receivable_id=receivable_id,
                                      holder_address=g.wallet_address).first()
    if role not in GLOBAL_ROLES and g.wallet_address not in {
        item.supplier_address, item.buyer_address
    } and not holding:
        return api_error("ROLE_REQUIRED", "Receivable history access is not allowed.", 403)
    events = []
    for event in ChainEvent.query.order_by(
        ChainEvent.block_number, ChainEvent.transaction_index, ChainEvent.log_index
    ):
        ids = [event.event_args.get(key) for key in ("id", "receivableId")]
        batch_ids = event.event_args.get("ids", [])
        if str(receivable_id) in ids or str(receivable_id) in batch_ids:
            events.append(_history_json(event))
    return _paged_items(events)


def _quote_json(item):
    return {"id": item.id, "quote_id": str(int(item.onchain_quote_id)),
            "onchain_quote_id": str(int(item.onchain_quote_id)),
            "financier_address": item.financier_address,
            "discount_rate_bps": item.discount_rate_bps,
            "payout": str(int(item.payout)), "status": item.status}


def _financing_json(item):
    status = "PENDING_QUOTE" if item.status == "OPEN" else item.status
    quotes = Quote.query.filter_by(onchain_request_id=item.onchain_request_id).all()
    return {"id": item.id, "request_id": str(int(item.onchain_request_id)),
            "onchain_request_id": str(int(item.onchain_request_id)),
            "receivable_id": str(int(item.receivable_id)),
            "supplier_address": item.supplier_address,
            "amount": str(int(item.amount)), "status": status,
            "accepted_quote_id": str(int(item.accepted_quote_id)) if item.accepted_quote_id else None,
            "quotes": [_quote_json(quote) for quote in quotes]}


@queries_bp.get("/financing")
@require_auth
def list_financing():
    role, error = _role()
    if error:
        return error
    query = FinancingRequest.query
    requested_supplier = normalize_wallet(request.args.get("supplier")) if request.args.get("supplier") else None
    requested_funder = normalize_wallet(request.args.get("funder")) if request.args.get("funder") else None
    if role == "SUPPLIER":
        if requested_supplier and requested_supplier != g.wallet_address:
            return api_error("ADDRESS_MISMATCH", "Cannot query another supplier.", 403)
        if requested_funder:
            return api_error("ROLE_REQUIRED", "Supplier queries cannot select a funder.", 403)
        query = query.filter_by(supplier_address=g.wallet_address)
    elif role == "FUNDER":
        if requested_funder and requested_funder != g.wallet_address:
            return api_error("ADDRESS_MISMATCH", "Cannot query another funder.", 403)
        own_request_ids = [quote.onchain_request_id for quote in Quote.query.filter_by(
            financier_address=g.wallet_address
        )]
        query = query.filter(or_(FinancingRequest.status == "OPEN",
                                 FinancingRequest.funder_address == g.wallet_address,
                                 FinancingRequest.onchain_request_id.in_(own_request_ids)))
    elif role not in GLOBAL_ROLES:
        return api_error("ROLE_REQUIRED", "Financing access is not allowed.", 403)
    else:
        if requested_supplier:
            query = query.filter_by(supplier_address=requested_supplier)
        if requested_funder:
            request_ids = [quote.onchain_request_id for quote in Quote.query.filter_by(
                financier_address=requested_funder
            )]
            query = query.filter(FinancingRequest.onchain_request_id.in_(request_ids))
    status = request.args.get("status")
    if status:
        normalized = "OPEN" if status.upper() == "PENDING_QUOTE" else status.upper()
        query = query.filter_by(status=normalized)
    return _paged_query(query.order_by(FinancingRequest.created_at.desc()), _financing_json)


@queries_bp.get("/financing/<int:request_id>")
@require_auth
def financing_detail(request_id):
    item = FinancingRequest.query.filter_by(onchain_request_id=request_id).first()
    if item is None:
        return api_error("NOT_FOUND", "Financing request was not found.", 404)
    role, error = _role()
    if error:
        return error
    related_funder = Quote.query.filter_by(onchain_request_id=request_id,
                                           financier_address=g.wallet_address).first()
    if role not in GLOBAL_ROLES and not (
        role == "SUPPLIER" and item.supplier_address == g.wallet_address
    ) and not (role == "FUNDER" and (item.status == "OPEN" or related_funder)):
        return api_error("ROLE_REQUIRED", "Financing access is not allowed.", 403)
    return jsonify(_financing_json(item))


@queries_bp.get("/dashboard")
@require_auth
def dashboard():
    address = normalize_wallet(request.args.get("address")) if request.args.get("address") else g.wallet_address
    if address != g.wallet_address:
        return api_error("ADDRESS_MISMATCH", "Dashboard address must match the session.", 403)
    role, error = _role()
    if error:
        return error
    holdings = Holding.query.filter_by(holder_address=address).all()
    receivable_total = sum(int(item.balance) for item in holdings)
    supplier_invoices = Invoice.query.filter_by(supplier_address=address).all()
    buyer_invoices = Invoice.query.filter_by(buyer_address=address).all()
    supplier_requests = FinancingRequest.query.filter_by(supplier_address=address).all()
    funded = [item for item in supplier_requests if item.status == "FUNDED"]
    data = {
        "receivable_total": str(receivable_total),
        "pending_invoices_count": sum(item.status == "PENDING" for item in supplier_invoices),
        "financing_active_amount": str(sum(int(item.amount) for item in supplier_requests if item.status == "OPEN")),
        "funded_total_amount": str(sum(int(item.payout or 0) for item in funded)),
    }
    if role == "CORE_ENTERPRISE":
        data.update(payable_total=str(sum(int(item.amount) for item in buyer_invoices if item.status == "CONFIRMED")),
                    overdue_count=sum(item.due_date < int(time.time()) and item.status == "CONFIRMED" for item in buyer_invoices))
    elif role == "FUNDER":
        data.update(active_quotes_count=Quote.query.filter_by(financier_address=address, status="ACTIVE").count(),
                    overdue_count=sum(item.status == "OVERDUE" for item in Receivable.query))
    elif role == "AUDITOR":
        data.update(total_invoices=Invoice.query.count(),
                    total_face_value=str(sum(int(item.face_value) for item in Receivable.query)),
                    frozen_receivables=Receivable.query.filter_by(frozen=True).count())
    elif role == "ADMIN":
        data.update(pending_enterprises=Enterprise.query.filter_by(status="PENDING").count(),
                    registered_enterprises=Enterprise.query.filter_by(status="APPROVED").count(),
                    recent_events=ChainEvent.query.count())
    return jsonify(data)


@queries_bp.get("/transactions")
@require_auth
def transactions():
    address = normalize_wallet(request.args.get("address")) if request.args.get("address") else g.wallet_address
    if address != g.wallet_address:
        return api_error("ADDRESS_MISMATCH", "Transaction address must match the session.", 403)
    relevant = [event for event in ChainEvent.query.order_by(
        ChainEvent.block_number.desc(), ChainEvent.transaction_index.desc(), ChainEvent.log_index.desc()
    ).limit(500) if address in (event.participants or [])]
    grouped = OrderedDict()
    for event in relevant:
        grouped.setdefault(event.tx_hash, {
            "action": _event_action(event), "tx_hash": event.tx_hash,
            "block_number": event.block_number,
            "timestamp": event.block_timestamp.isoformat(),
            "contract_name": event.contract_name, "status": "CONFIRMED",
            "etherscan_url": f"https://sepolia.etherscan.io/tx/{event.tx_hash}",
        })
    return _paged_items(list(grouped.values()))


@queries_bp.get("/events")
@require_auth
def events():
    role, error = _role()
    if error:
        return error
    requested_address = normalize_wallet(request.args.get("address")) if request.args.get("address") else None
    if role not in GLOBAL_ROLES and requested_address and requested_address != g.wallet_address:
        return api_error("ADDRESS_MISMATCH", "Cannot inspect another address.", 403)
    visible_address = requested_address if role in GLOBAL_ROLES else g.wallet_address
    contract_filter = request.args.get("contract")
    name_filter = request.args.get("name") or request.args.get("type")
    from_filter = normalize_wallet(request.args.get("from")) if request.args.get("from") else None
    to_filter = normalize_wallet(request.args.get("to")) if request.args.get("to") else None
    rows = []
    for event in ChainEvent.query.order_by(ChainEvent.block_number.desc(), ChainEvent.log_index.desc()).limit(1000):
        if visible_address and visible_address not in (event.participants or []):
            continue
        if contract_filter and event.contract_name != contract_filter:
            continue
        if name_filter and event.event_name != name_filter:
            continue
        if from_filter and event.event_args.get("from") != from_filter:
            continue
        if to_filter and event.event_args.get("to") != to_filter:
            continue
        rows.append({"contract_name": event.contract_name, "event_name": event.event_name,
                     "block_number": event.block_number, "tx_hash": event.tx_hash,
                     "log_index": event.log_index, "event_args": event.event_args,
                     "event_args_json": json.dumps(event.event_args, ensure_ascii=False),
                     "timestamp": event.block_timestamp.isoformat(),
                     "etherscan_url": f"https://sepolia.etherscan.io/tx/{event.tx_hash}"})
    return _paged_items(rows)
