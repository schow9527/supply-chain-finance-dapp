from datetime import datetime, timezone

import pytest

from backend.extensions import db
from backend.models import (
    ChainEvent, Enterprise, FinancingRequest, Holding, Invoice, Quote, Receivable,
)
from backend.sync.projections import ProjectionError, project_event, rebuild_projections

SUPPLIER = "0x1111111111111111111111111111111111111111"
BUYER = "0x2222222222222222222222222222222222222222"
FUNDER = "0x3333333333333333333333333333333333333333"
POOL = "0xa978e8eb77bfa67c5638a874ede258260810c678"
ZERO = "0x0000000000000000000000000000000000000000"


def _event(name, args, number=1, contract="Test"):
    event = ChainEvent(
        chain_id=11155111, block_number=number, block_hash="0x" + f"{number:064x}",
        transaction_index=0, tx_hash="0x" + f"{number:064x}", log_index=0,
        contract_address=POOL, contract_name=contract, event_name=name,
        event_args=args, participants=[],
        block_timestamp=datetime.fromtimestamp(1_700_000_000 + number, timezone.utc),
        processed_at=datetime.now(timezone.utc),
    )
    db.session.add(event)
    db.session.flush()
    project_event(event)
    return event


def _mint_metadata(number=1):
    return _event("ReceivableMinted", {"id": "7", "supplier": SUPPLIER,
                  "buyer": BUYER, "faceValue": "100", "dueDate": "2000000000"}, number)


def _transfer(from_address, to_address, value="100", number=2):
    return _event("TransferSingle", {"operator": POOL, "from": from_address,
                  "to": to_address, "id": "7", "value": value}, number)


def _balance(holder):
    item = Holding.query.filter_by(receivable_id=7, holder_address=holder).first()
    return int(item.balance) if item else 0


def test_invoice_submitted_matches_draft(app):
    draft = Invoice(chain_id=11155111, invoice_no="INV-1", supplier_address=SUPPLIER,
                    buyer_address=BUYER, amount=100, due_date=2_000_000_000,
                    file_hash="0x" + "a" * 64, storage_key="stored.pdf",
                    original_filename="invoice.pdf", status="FILE_UPLOADED")
    db.session.add(draft)
    db.session.flush()
    _event("InvoiceSubmitted", {"invoiceId": "7", "supplier": SUPPLIER,
           "buyer": BUYER, "invoiceNo": "INV-1", "amount": "100",
           "dueDate": "2000000000", "fileHash": "0x" + "a" * 64})
    assert draft.status == "PENDING"
    assert int(draft.onchain_id) == 7


def test_invoice_submitted_without_draft_marks_file_missing(app):
    _event("InvoiceSubmitted", {"invoiceId": "8", "supplier": SUPPLIER,
           "buyer": BUYER, "invoiceNo": "CHAIN-ONLY", "amount": "50",
           "dueDate": "2000000000", "fileHash": "0x" + "b" * 64})
    item = Invoice.query.one()
    assert item.status == "FILE_MISSING"
    assert item.storage_key is None


def test_ambiguous_invoice_drafts_fail(app):
    for suffix in ("a", "b"):
        db.session.add(Invoice(chain_id=11155111, invoice_no="DUP", supplier_address=SUPPLIER,
                       buyer_address=BUYER, amount=1, due_date=2_000_000_000,
                       file_hash="0x" + "c" * 64, storage_key=f"{suffix}.pdf",
                       status="FILE_UPLOADED"))
    db.session.flush()
    with pytest.raises(ProjectionError, match="INVOICE_DRAFT_AMBIGUOUS"):
        _event("InvoiceSubmitted", {"invoiceId": "1", "supplier": SUPPLIER,
               "buyer": BUYER, "invoiceNo": "DUP", "amount": "1",
               "dueDate": "2000000000", "fileHash": "0x" + "c" * 64})


def test_invoice_confirmed_and_rejected(app):
    item = Invoice(chain_id=11155111, onchain_id=1, invoice_no="I", supplier_address=SUPPLIER,
                   buyer_address=BUYER, amount=1, due_date=2_000_000_000,
                   file_hash="0x" + "d" * 64, status="PENDING")
    db.session.add(item)
    db.session.flush()
    _event("InvoiceConfirmed", {"invoiceId": "1", "buyer": BUYER}, 1)
    assert item.status == "CONFIRMED"
    _event("InvoiceRejected", {"invoiceId": "1", "buyer": BUYER, "reason": "bad"}, 2)
    assert item.status == "REJECTED" and item.reject_reason == "bad"


def test_mint_and_business_transfer_do_not_double_count(app):
    _mint_metadata()
    assert Holding.query.count() == 0
    _transfer(ZERO, SUPPLIER)
    assert _balance(SUPPLIER) == 100
    _event("ReceivableTransferred", {"id": "7", "from": SUPPLIER,
           "to": FUNDER, "amount": "40"}, 3)
    assert _balance(SUPPLIER) == 100


def test_transfer_escrow_funding_cancel_and_burn(app):
    _mint_metadata()
    _transfer(ZERO, SUPPLIER, "200", 2)
    _transfer(SUPPLIER, POOL, "100", 3)
    assert (_balance(SUPPLIER), _balance(POOL)) == (100, 100)
    _transfer(POOL, FUNDER, "60", 4)
    assert (_balance(POOL), _balance(FUNDER)) == (40, 60)
    _transfer(POOL, SUPPLIER, "40", 5)
    assert (_balance(SUPPLIER), _balance(POOL)) == (140, 0)
    _transfer(FUNDER, ZERO, "60", 6)
    assert _balance(FUNDER) == 0


def test_transfer_batch_and_invalid_balance(app):
    _mint_metadata()
    _event("TransferBatch", {"operator": POOL, "from": ZERO, "to": SUPPLIER,
           "ids": ["7", "8"], "values": ["10", "20"]}, 2)
    assert _balance(SUPPLIER) == 10
    with pytest.raises(ProjectionError, match="INSUFFICIENT"):
        _transfer(SUPPLIER, FUNDER, "11", 3)
    with pytest.raises(ProjectionError, match="LENGTH_MISMATCH"):
        _event("TransferBatch", {"operator": POOL, "from": ZERO, "to": SUPPLIER,
               "ids": ["7"], "values": ["1", "2"]}, 4)


def test_receivable_freeze_status_repay_and_overdue(app):
    item = _mint_metadata()
    receivable = Receivable.query.one()
    _event("ReceivableFrozen", {"id": "7", "auditor": FUNDER, "reason": "review"}, 2)
    assert receivable.frozen is True
    _event("ReceivableUnfrozen", {"id": "7", "auditor": FUNDER, "reason": "clear"}, 3)
    assert receivable.frozen is False
    _event("MarkedOverdue", {"receivableId": "7", "buyer": BUYER, "funder": FUNDER}, 4)
    assert receivable.status == "OVERDUE"
    _event("Repaid", {"receivableId": "7", "buyer": BUYER, "amount": "100"}, 5)
    _event("ReceivableStatusChanged", {"id": "7", "status": "2"}, 6)
    assert receivable.status == "REPAID" and int(receivable.repayment_amount) == 100


def test_financing_and_quote_lifecycle(app):
    _event("FinancingRequested", {"requestId": "1", "receivableId": "7",
           "supplier": SUPPLIER, "amount": "100"}, 1)
    _event("QuoteSubmitted", {"quoteId": "2", "requestId": "1", "funder": FUNDER,
           "discountBps": "500", "payout": "95"}, 2)
    request = FinancingRequest.query.one()
    quote = Quote.query.one()
    assert request.status == "OPEN" and quote.status == "ACTIVE"
    _event("FinancingFunded", {"requestId": "1", "quoteId": "2", "receivableId": "7",
           "supplier": SUPPLIER, "funder": FUNDER, "amount": "100", "payout": "95"}, 3)
    assert request.status == "FUNDED" and quote.status == "ACCEPTED"
    quote.status = "ACTIVE"
    _event("QuoteWithdrawn", {"quoteId": "2", "requestId": "1", "funder": FUNDER}, 4)
    assert quote.status == "WITHDRAWN"
    request.status = "OPEN"
    _event("FinancingCancelled", {"requestId": "1", "receivableId": "7",
           "supplier": SUPPLIER}, 5)
    assert request.status == "CANCELLED"


def test_role_grant_and_revoke_preserve_enterprise(app):
    enterprise = Enterprise(wallet_address=SUPPLIER, enterprise_name="Acme",
                            role_applied="SUPPLIER", contact_person="Alice")
    db.session.add(enterprise)
    db.session.flush()
    from backend.sync.projections import ROLE_HASHES
    role_hash = next(key for key, value in ROLE_HASHES.items() if value == "SUPPLIER")
    _event("RoleGranted", {"role": role_hash, "account": SUPPLIER, "sender": BUYER}, 1)
    assert enterprise.chain_role == "SUPPLIER" and enterprise.status == "APPROVED"
    _event("RoleRevoked", {"role": role_hash, "account": SUPPLIER, "sender": BUYER}, 2)
    assert enterprise.chain_role is None and enterprise.revoked_at is not None


def test_end_to_end_projection_and_rebuild_are_identical(app):
    draft = Invoice(chain_id=11155111, invoice_no="E2E", supplier_address=SUPPLIER,
                    buyer_address=BUYER, amount=100, due_date=2_000_000_000,
                    file_hash="0x" + "e" * 64, storage_key="e2e.pdf",
                    original_filename="e2e.pdf", status="FILE_UPLOADED")
    db.session.add(draft)
    db.session.flush()
    sequence = [
        ("InvoiceSubmitted", {"invoiceId": "7", "supplier": SUPPLIER, "buyer": BUYER,
         "invoiceNo": "E2E", "amount": "100", "dueDate": "2000000000", "fileHash": "0x" + "e" * 64}),
        ("InvoiceConfirmed", {"invoiceId": "7", "buyer": BUYER}),
        ("ReceivableMinted", {"id": "7", "supplier": SUPPLIER, "buyer": BUYER,
         "faceValue": "100", "dueDate": "2000000000"}),
        ("TransferSingle", {"operator": POOL, "from": ZERO, "to": SUPPLIER, "id": "7", "value": "100"}),
        ("FinancingRequested", {"requestId": "1", "receivableId": "7", "supplier": SUPPLIER, "amount": "100"}),
        ("TransferSingle", {"operator": POOL, "from": SUPPLIER, "to": POOL, "id": "7", "value": "100"}),
        ("QuoteSubmitted", {"quoteId": "2", "requestId": "1", "funder": FUNDER, "discountBps": "500", "payout": "95"}),
        ("FinancingFunded", {"requestId": "1", "quoteId": "2", "receivableId": "7", "supplier": SUPPLIER, "funder": FUNDER, "amount": "100", "payout": "95"}),
        ("TransferSingle", {"operator": POOL, "from": POOL, "to": FUNDER, "id": "7", "value": "100"}),
        ("Repaid", {"receivableId": "7", "buyer": BUYER, "amount": "100"}),
        ("ReceivableStatusChanged", {"id": "7", "status": "2"}),
        ("Redeemed", {"receivableId": "7", "holder": FUNDER, "amount": "100"}),
        ("TransferSingle", {"operator": POOL, "from": FUNDER, "to": ZERO, "id": "7", "value": "100"}),
    ]
    for number, (name, args) in enumerate(sequence, 1):
        _event(name, args, number)
    db.session.commit()
    assert draft.status == "CONFIRMED"
    assert FinancingRequest.query.one().status == "FUNDED"
    assert Quote.query.one().status == "ACCEPTED"
    assert Receivable.query.one().status == "REPAID"
    assert _balance(FUNDER) == 0
    before = (Invoice.query.count(), Receivable.query.count(), FinancingRequest.query.count(),
              Quote.query.count(), [(row.holder_address, int(row.balance)) for row in Holding.query.order_by(Holding.id)])
    rebuild_projections()
    after = (Invoice.query.count(), Receivable.query.count(), FinancingRequest.query.count(),
             Quote.query.count(), [(row.holder_address, int(row.balance)) for row in Holding.query.order_by(Holding.id)])
    assert after == before


def test_rebuild_cli_requires_confirmation(app):
    runner = app.test_cli_runner()
    denied = runner.invoke(args=["rebuild-projections"])
    assert denied.exit_code != 0
    allowed = runner.invoke(args=["rebuild-projections", "--confirm"])
    assert allowed.exit_code == 0
    assert "projections_rebuilt=true" in allowed.output
