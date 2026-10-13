"""Opt-in destructive integration checks for an explicitly dedicated test database."""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from backend.app import create_app
from backend.config import normalize_database_url
from backend.extensions import db
from backend.models import ChainEvent, Invoice, SyncState
from backend.sync.engine import EventSynchronizer
from backend.sync.projections import rebuild_projections
from backend.tests.conftest import FakeRoleService
from backend.tests.test_projections import BUYER, FUNDER, POOL, SUPPLIER, _event
from backend.tests.test_sync import FakeProvider, _paused

pytestmark = pytest.mark.postgres


def _safe_url():
    raw = os.getenv("POSTGRES_TEST_URL")
    if not raw:
        pytest.skip("POSTGRES_TEST_URL is not configured; real PostgreSQL validation skipped")
    uri = normalize_database_url(raw)
    url = make_url(uri)
    if url.get_backend_name() != "postgresql" or "_test" not in (url.database or "").lower():
        pytest.fail("POSTGRES_TEST_URL must target a PostgreSQL database containing _test")
    local = {"localhost", "127.0.0.1", "::1"}
    if url.host not in local and os.getenv("POSTGRES_TEST_ALLOWED_HOST") != url.host:
        pytest.fail("remote test host requires exact POSTGRES_TEST_ALLOWED_HOST authorization")
    return uri


def test_real_postgres_migrations_types_transactions_worker_and_projections(tmp_path):
    uri = _safe_url()
    app = create_app({
        "TESTING": True, "ENV_NAME": "testing", "SQLALCHEMY_DATABASE_URI": uri,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"), "ROLE_SERVICE": FakeRoleService(),
    })
    runner = app.test_cli_runner()
    # The safety guard above is mandatory before these destructive migration checks.
    runner.invoke(args=["db", "downgrade", "base"])
    first = runner.invoke(args=["db", "upgrade"])
    assert first.exit_code == 0, first.output
    assert runner.invoke(args=["db", "check"]).exit_code == 0
    assert runner.invoke(args=["db", "downgrade", "base"]).exit_code == 0
    assert runner.invoke(args=["db", "upgrade"]).exit_code == 0
    assert runner.invoke(args=["db", "check"]).exit_code == 0

    with app.app_context():
        inspector = inspect(db.engine)
        chain_uniques = {item["name"] for item in inspector.get_unique_constraints("chain_events")}
        holding_uniques = {item["name"] for item in inspector.get_unique_constraints("holdings")}
        sync_uniques = {item["name"] for item in inspector.get_unique_constraints("sync_state")}
        assert "uq_chain_events_chain_log" in chain_uniques
        assert "uq_holdings_holding_identity" in holding_uniques
        assert "uq_sync_state_chain_contract" in sync_uniques
        huge = 2**256 - 1
        invoice = Invoice(
            chain_id=11155111, invoice_no="PG-BIG", supplier_address=SUPPLIER,
            buyer_address=BUYER, amount=huge, due_date=2_000_000_000,
            file_hash="0x" + "a" * 64, status="FILE_UPLOADED",
        )
        event = ChainEvent(
            chain_id=11155111, block_number=1, block_hash="0x" + "1" * 64,
            transaction_index=0, tx_hash="0x" + "9" * 64, log_index=0,
            contract_address=POOL, contract_name="Test", event_name="TestEvent",
            event_args={"large": str(huge), "nested": {"ok": True}}, participants=[SUPPLIER],
            block_timestamp=datetime.now(timezone.utc), processed_at=datetime.now(timezone.utc),
        )
        db.session.add_all([invoice, event])
        db.session.commit()
        assert int(Invoice.query.filter_by(invoice_no="PG-BIG").one().amount) == huge
        saved = ChainEvent.query.filter_by(event_name="TestEvent").one()
        assert saved.event_args["nested"]["ok"] is True
        assert saved.block_timestamp.tzinfo is not None

        db.session.add(ChainEvent(
            chain_id=event.chain_id, block_number=2, block_hash="0x" + "2" * 64,
            transaction_index=0, tx_hash=event.tx_hash, log_index=event.log_index,
            contract_address=POOL, contract_name="Test", event_name="Duplicate",
            event_args={}, participants=[], block_timestamp=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        before = Invoice.query.count()
        db.session.add(Invoice(
            chain_id=11155111, invoice_no="ROLLBACK", supplier_address=SUPPLIER,
            buyer_address=BUYER, amount=1, due_date=2_000_000_000,
            file_hash="0x" + "b" * 64, status="FILE_UPLOADED",
        ))
        db.session.flush()
        db.session.rollback()
        assert Invoice.query.count() == before

        provider = FakeProvider(latest=10)
        sync = EventSynchronizer(app, provider, projector=lambda _event: (_ for _ in ()).throw(RuntimeError("rollback")))
        app.config.update(
            SYNC_START_BLOCK=10, EVENT_SYNC_BATCH_SIZE=10, BLOCK_CONFIRMATIONS=0
        )
        provider.eth.logs = [_paused(sync)]
        with pytest.raises(RuntimeError, match="rollback"):
            sync.run_once()
        assert SyncState.query.count() == 0

        draft = Invoice(
            chain_id=11155111, invoice_no="PG-E2E", supplier_address=SUPPLIER,
            buyer_address=BUYER, amount=100, due_date=2_000_000_000,
            file_hash="0x" + "e" * 64, storage_key="pg.pdf", status="FILE_UPLOADED",
        )
        db.session.add(draft)
        db.session.flush()
        sequence = [
            ("InvoiceSubmitted", {"invoiceId": "7", "supplier": SUPPLIER, "buyer": BUYER,
             "invoiceNo": "PG-E2E", "amount": "100", "dueDate": "2000000000", "fileHash": "0x" + "e" * 64}),
            ("InvoiceConfirmed", {"invoiceId": "7", "buyer": BUYER}),
            ("FinancingRequested", {"requestId": "1", "receivableId": "7", "supplier": SUPPLIER, "amount": "100"}),
            ("QuoteSubmitted", {"quoteId": "2", "requestId": "1", "funder": FUNDER, "discountBps": "500", "payout": "95"}),
            ("FinancingFunded", {"requestId": "1", "quoteId": "2", "receivableId": "7",
             "supplier": SUPPLIER, "funder": FUNDER, "amount": "100", "payout": "95"}),
        ]
        for number, (name, args) in enumerate(sequence, 20):
            _event(name, args, number)
        db.session.commit()
        rebuild_projections()
        assert Invoice.query.filter_by(invoice_no="PG-E2E").one().status == "CONFIRMED"

    client = app.test_client()
    with client.session_transaction() as session:
        session["wallet_address"] = SUPPLIER
    app.config["ROLE_SERVICE"].roles[SUPPLIER] = "SUPPLIER"
    assert client.get("/api/invoices?status=CONFIRMED").status_code == 200
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
