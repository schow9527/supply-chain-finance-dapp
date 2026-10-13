"""Deterministic business projections derived from persisted chain events."""

from __future__ import annotations

from decimal import Decimal

from eth_utils import keccak

from backend.extensions import db
from backend.models import (
    ChainEvent, Enterprise, FinancingRequest, Holding, Invoice, Quote, Receivable,
)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
RECEIVABLE_STATUS = {0: "NONE", 1: "ACTIVE", 2: "REPAID", 3: "OVERDUE"}
REQUEST_STATUS = {0: "NONE", 1: "OPEN", 2: "FUNDED", 3: "CANCELLED"}
QUOTE_STATUS = {0: "NONE", 1: "ACTIVE", 2: "ACCEPTED", 3: "WITHDRAWN"}
ROLE_HASHES = {
    "0x" + bytes(32).hex(): "ADMIN",
    **{"0x" + keccak(text=role).hex(): role
       for role in ("SUPPLIER", "CORE_ENTERPRISE", "FUNDER", "AUDITOR")},
}


class ProjectionError(RuntimeError):
    pass


def _int(args, key):
    return int(args[key])


def _address(args, key):
    return args[key].lower()


def _receivable(chain_id, receivable_id):
    item = Receivable.query.filter_by(chain_id=chain_id, receivable_id=receivable_id).first()
    if item is None:
        raise ProjectionError(f"RECEIVABLE_NOT_FOUND:{receivable_id}")
    return item


def _holding(chain_id, receivable_id, holder, create=False):
    holder = holder.lower()
    item = Holding.query.filter_by(
        chain_id=chain_id, receivable_id=receivable_id, holder_address=holder
    ).first()
    if item is None and create:
        item = Holding(chain_id=chain_id, receivable_id=receivable_id,
                       holder_address=holder, balance=0)
        db.session.add(item)
        db.session.flush()
    return item


def _transfer(chain_id, receivable_id, from_address, to_address, amount):
    amount = int(amount)
    if amount < 0:
        raise ProjectionError("NEGATIVE_TRANSFER")
    from_address = from_address.lower()
    to_address = to_address.lower()
    if from_address != ZERO_ADDRESS:
        source = _holding(chain_id, receivable_id, from_address)
        source_balance = int(source.balance) if source else 0
        if source_balance < amount:
            raise ProjectionError("INSUFFICIENT_PROJECTED_BALANCE")
        source.balance = source_balance - amount
    if to_address != ZERO_ADDRESS:
        target = _holding(chain_id, receivable_id, to_address, create=True)
        target.balance = int(target.balance) + amount


def project_event(event: ChainEvent):
    args = event.event_args
    name = event.event_name
    chain_id = event.chain_id
    if name == "RoleGranted":
        item = Enterprise.query.filter_by(wallet_address=_address(args, "account")).first()
        if item:
            item.chain_role = ROLE_HASHES.get(args["role"].lower())
            item.revoked_at = None
            if item.chain_role in {"SUPPLIER", "CORE_ENTERPRISE", "FUNDER"}:
                item.status = "APPROVED"
                item.approval_tx_hash = event.tx_hash
    elif name == "RoleRevoked":
        item = Enterprise.query.filter_by(wallet_address=_address(args, "account")).first()
        if item:
            item.chain_role = None
            item.revoked_at = event.block_timestamp
    elif name == "InvoiceSubmitted":
        invoice_id = _int(args, "invoiceId")
        supplier = _address(args, "supplier")
        buyer = _address(args, "buyer")
        amount = _int(args, "amount")
        due_date = _int(args, "dueDate")
        file_hash = args["fileHash"].lower()
        candidates = Invoice.query.filter_by(
            chain_id=chain_id, onchain_id=None, supplier_address=supplier,
            buyer_address=buyer, invoice_no=args["invoiceNo"], due_date=due_date,
            file_hash=file_hash,
        ).all()
        candidates = [item for item in candidates if int(item.amount) == amount]
        if len(candidates) > 1:
            raise ProjectionError("INVOICE_DRAFT_AMBIGUOUS")
        if candidates:
            item = candidates[0]
            item.status = "PENDING"
        else:
            item = Invoice(
                chain_id=chain_id, invoice_no=args["invoiceNo"],
                supplier_address=supplier, buyer_address=buyer, amount=amount,
                due_date=due_date, file_hash=file_hash, status="FILE_MISSING",
                created_at=event.block_timestamp, updated_at=event.block_timestamp,
            )
            db.session.add(item)
        item.onchain_id = invoice_id
        item.submit_tx_hash = event.tx_hash
        item.submit_block_number = event.block_number
    elif name == "InvoiceConfirmed":
        item = Invoice.query.filter_by(chain_id=chain_id, onchain_id=_int(args, "invoiceId")).first()
        if item is None:
            raise ProjectionError("INVOICE_NOT_FOUND")
        item.status = "CONFIRMED"
        item.confirmed_tx_hash = event.tx_hash
        item.confirmed_at = event.block_timestamp
    elif name == "InvoiceRejected":
        item = Invoice.query.filter_by(chain_id=chain_id, onchain_id=_int(args, "invoiceId")).first()
        if item is None:
            raise ProjectionError("INVOICE_NOT_FOUND")
        item.status = "REJECTED"
        item.reject_reason = args["reason"]
        item.rejected_tx_hash = event.tx_hash
    elif name == "ReceivableMinted":
        rid = _int(args, "id")
        item = Receivable.query.filter_by(chain_id=chain_id, receivable_id=rid).first()
        if item is None:
            item = Receivable(chain_id=chain_id, receivable_id=rid)
            db.session.add(item)
        item.supplier_address = _address(args, "supplier")
        item.buyer_address = _address(args, "buyer")
        item.face_value = _int(args, "faceValue")
        item.due_date = _int(args, "dueDate")
        item.status = "ACTIVE"
        item.frozen = False
        item.minted_tx_hash = event.tx_hash
    elif name in {"TransferSingle", "TransferBatch"}:
        ids = args["ids"] if name == "TransferBatch" else [args["id"]]
        values = args["values"] if name == "TransferBatch" else [args["value"]]
        if len(ids) != len(values):
            raise ProjectionError("TRANSFER_BATCH_LENGTH_MISMATCH")
        for rid, value in zip(ids, values, strict=True):
            _transfer(chain_id, int(rid), args["from"], args["to"], int(value))
    elif name in {"ReceivableFrozen", "ReceivableUnfrozen"}:
        item = _receivable(chain_id, _int(args, "id"))
        item.frozen = name == "ReceivableFrozen"
        item.freeze_reason = args["reason"]
        item.frozen_by = _address(args, "auditor")
    elif name == "ReceivableStatusChanged":
        item = _receivable(chain_id, _int(args, "id"))
        status = _int(args, "status")
        if status not in RECEIVABLE_STATUS:
            raise ProjectionError("UNKNOWN_RECEIVABLE_STATUS")
        item.status = RECEIVABLE_STATUS[status]
    elif name == "FinancingRequested":
        request_id = _int(args, "requestId")
        item = FinancingRequest.query.filter_by(onchain_request_id=request_id).first()
        if item is None:
            item = FinancingRequest(onchain_request_id=request_id,
                                    created_at=event.block_timestamp,
                                    updated_at=event.block_timestamp)
            db.session.add(item)
        item.receivable_id = _int(args, "receivableId")
        item.supplier_address = _address(args, "supplier")
        item.amount = _int(args, "amount")
        item.status = "OPEN"
        item.request_tx_hash = event.tx_hash
    elif name == "QuoteSubmitted":
        quote_id = _int(args, "quoteId")
        item = Quote.query.filter_by(onchain_quote_id=quote_id).first()
        if item is None:
            item = Quote(onchain_quote_id=quote_id, created_at=event.block_timestamp,
                         updated_at=event.block_timestamp)
            db.session.add(item)
        item.onchain_request_id = _int(args, "requestId")
        item.financier_address = _address(args, "funder")
        item.discount_rate_bps = _int(args, "discountBps")
        item.payout = _int(args, "payout")
        item.status = "ACTIVE"
        item.submit_tx_hash = event.tx_hash
    elif name == "QuoteWithdrawn":
        item = Quote.query.filter_by(onchain_quote_id=_int(args, "quoteId")).first()
        if item is None:
            raise ProjectionError("QUOTE_NOT_FOUND")
        item.status = "WITHDRAWN"
    elif name == "FinancingFunded":
        item = FinancingRequest.query.filter_by(onchain_request_id=_int(args, "requestId")).first()
        quote = Quote.query.filter_by(onchain_quote_id=_int(args, "quoteId")).first()
        if item is None or quote is None:
            raise ProjectionError("FINANCING_NOT_FOUND")
        item.status = "FUNDED"
        item.accepted_quote_id = _int(args, "quoteId")
        item.funder_address = _address(args, "funder")
        item.payout = _int(args, "payout")
        item.funded_tx_hash = event.tx_hash
        quote.status = "ACCEPTED"
    elif name == "FinancingCancelled":
        item = FinancingRequest.query.filter_by(onchain_request_id=_int(args, "requestId")).first()
        if item is None:
            raise ProjectionError("FINANCING_NOT_FOUND")
        item.status = "CANCELLED"
    elif name == "Repaid":
        item = _receivable(chain_id, _int(args, "receivableId"))
        item.status = "REPAID"
        item.repayment_amount = _int(args, "amount")
        item.repayment_tx_hash = event.tx_hash
        item.repaid_at = event.block_timestamp
    elif name == "MarkedOverdue":
        _receivable(chain_id, _int(args, "receivableId")).status = "OVERDUE"
    # ReceivableTransferred, Redeemed and stablecoin events are audit-only.


def rebuild_projections():
    Holding.query.delete()
    Quote.query.delete()
    FinancingRequest.query.delete()
    Receivable.query.delete()
    Invoice.query.filter(Invoice.storage_key.is_(None)).delete(synchronize_session=False)
    for item in Invoice.query.filter(Invoice.storage_key.is_not(None)):
        item.onchain_id = None
        item.status = "FILE_UPLOADED"
        item.submit_tx_hash = None
        item.submit_block_number = None
        item.confirmed_tx_hash = None
        item.confirmed_at = None
        item.rejected_tx_hash = None
        item.reject_reason = None
    for item in Enterprise.query:
        item.chain_role = None
        item.revoked_at = None
        if item.status == "APPROVED":
            item.status = "PENDING"
    db.session.flush()
    for event in ChainEvent.query.order_by(
        ChainEvent.block_number, ChainEvent.transaction_index, ChainEvent.log_index
    ):
        project_event(event)
    db.session.commit()
