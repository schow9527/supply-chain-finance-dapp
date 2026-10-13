from datetime import datetime, timezone

from backend.extensions import db
from backend.models import (
    ChainEvent, FinancingRequest, Holding, Invoice, Quote, Receivable,
)

SUPPLIER = "0x1111111111111111111111111111111111111111"
BUYER = "0x2222222222222222222222222222222222222222"
FUNDER = "0x3333333333333333333333333333333333333333"
ADMIN = "0x4444444444444444444444444444444444444444"
OTHER = "0x5555555555555555555555555555555555555555"


def _login(client, app, wallet, role):
    with client.session_transaction() as session:
        session["wallet_address"] = wallet
    app.config["ROLE_SERVICE"].roles[wallet] = role


def _invoice(status="PENDING", amount=2**80):
    item = Invoice(chain_id=11155111, onchain_id=7, invoice_no="INV-7",
                   supplier_address=SUPPLIER, buyer_address=BUYER, amount=amount,
                   due_date=2_000_000_000, file_hash="0x" + "a" * 64,
                   status=status, storage_key="stored.pdf")
    db.session.add(item)
    db.session.commit()
    return item.id


def _receivable():
    item = Receivable(chain_id=11155111, receivable_id=7,
                      supplier_address=SUPPLIER, buyer_address=BUYER,
                      face_value=2**80, due_date=2_000_000_000,
                      status="ACTIVE", frozen=False)
    db.session.add(item)
    db.session.add(Holding(chain_id=11155111, receivable_id=7,
                           holder_address=SUPPLIER, balance=2**80))
    db.session.commit()


def _financing():
    request_item = FinancingRequest(onchain_request_id=1, receivable_id=7,
                                    supplier_address=SUPPLIER, amount=2**80,
                                    status="OPEN")
    quote = Quote(onchain_quote_id=2, onchain_request_id=1,
                  financier_address=FUNDER, discount_rate_bps=500,
                  payout=100, status="ACTIVE")
    db.session.add_all([request_item, quote])
    db.session.commit()


def _chain_event(name, tx_hash, log_index, participants, args=None):
    event = ChainEvent(chain_id=11155111, block_number=10,
                       block_hash="0x" + "b" * 64, transaction_index=0,
                       tx_hash=tx_hash, log_index=log_index,
                       contract_address="0x" + "c" * 40,
                       contract_name="InvoiceRegistry", event_name=name,
                       event_args=args or {"supplier": SUPPLIER},
                       participants=participants,
                       block_timestamp=datetime.now(timezone.utc),
                       processed_at=datetime.now(timezone.utc))
    db.session.add(event)
    db.session.commit()


def test_query_apis_require_authentication(client):
    for path in ("/api/invoices", "/api/receivables", "/api/financing",
                 "/api/dashboard", "/api/transactions", "/api/events"):
        assert client.get(path).status_code == 401


def test_supplier_invoice_list_precision_filter_and_detail(client, app):
    with app.app_context():
        invoice_id = _invoice()
    _login(client, app, SUPPLIER, "SUPPLIER")
    response = client.get("/api/invoices?status=PENDING&page=1&page_size=1")
    payload = response.get_json()
    assert response.status_code == 200 and payload["total"] == 1
    assert payload["items"][0]["amount"] == str(2**80)
    assert client.get(f"/api/invoices/{invoice_id}").status_code == 200
    assert client.get("/api/invoices?status=REJECTED").get_json()["items"] == []


def test_invoice_query_blocks_impersonation_and_missing_resource(client, app):
    _login(client, app, SUPPLIER, "SUPPLIER")
    assert client.get(f"/api/invoices?supplier={OTHER}").status_code == 403
    assert client.get("/api/invoices/999").status_code == 404


def test_admin_and_auditor_can_query_global_invoices(client, app):
    with app.app_context():
        _invoice()
    _login(client, app, ADMIN, "ADMIN")
    assert client.get("/api/invoices").get_json()["total"] == 1
    _login(client, app, ADMIN, "AUDITOR")
    assert client.get("/api/invoices").status_code == 200


def test_receivables_are_holder_scoped(client, app):
    with app.app_context():
        _receivable()
    _login(client, app, SUPPLIER, "SUPPLIER")
    payload = client.get(f"/api/receivables?holder={SUPPLIER}").get_json()
    assert payload["items"][0]["balance"] == str(2**80)
    assert client.get(f"/api/receivables?holder={OTHER}").status_code == 403


def test_receivable_history_is_ordered_and_protected(client, app):
    with app.app_context():
        _receivable()
        _chain_event("ReceivableMinted", "0x" + "1" * 64, 0,
                     [SUPPLIER, BUYER], {"id": "7", "supplier": SUPPLIER})
        _chain_event("TransferSingle", "0x" + "2" * 64, 0,
                     [SUPPLIER, FUNDER], {"id": "7", "from": SUPPLIER,
                                         "to": FUNDER, "value": "10"})
    _login(client, app, SUPPLIER, "SUPPLIER")
    history = client.get("/api/receivables/7/history").get_json()["items"]
    assert [item["action"] for item in history] == ["RECEIVABLE_MINTED", "RECEIVABLE_TRANSFERRED"]
    _login(client, app, OTHER, "SUPPLIER")
    assert client.get("/api/receivables/7/history").status_code == 403


def test_financing_market_supplier_scope_and_detail(client, app):
    with app.app_context():
        _financing()
    _login(client, app, SUPPLIER, "SUPPLIER")
    data = client.get("/api/financing?status=PENDING_QUOTE").get_json()
    assert data["items"][0]["amount"] == str(2**80)
    assert data["items"][0]["quotes"][0]["status"] == "ACTIVE"
    assert client.get("/api/financing/1").status_code == 200
    assert client.get(f"/api/financing?supplier={OTHER}").status_code == 403
    _login(client, app, FUNDER, "FUNDER")
    assert client.get("/api/financing").get_json()["total"] == 1
    assert client.get(f"/api/financing?funder={OTHER}").status_code == 403
    _login(client, app, ADMIN, "ADMIN")
    assert client.get(f"/api/financing?funder={FUNDER}").get_json()["total"] == 1


def test_dashboard_uses_session_and_real_projection_data(client, app):
    with app.app_context():
        _receivable()
        _invoice()
        _financing()
    _login(client, app, SUPPLIER, "SUPPLIER")
    data = client.get(f"/api/dashboard?address={SUPPLIER}").get_json()
    assert data["receivable_total"] == str(2**80)
    assert data["pending_invoices_count"] == 1
    assert client.get(f"/api/dashboard?address={OTHER}").status_code == 403


def test_role_dashboards_return_projection_statistics(client, app):
    with app.app_context():
        _receivable()
        _invoice(status="CONFIRMED")
        _financing()
    _login(client, app, BUYER, "CORE_ENTERPRISE")
    assert "payable_total" in client.get("/api/dashboard").get_json()
    _login(client, app, FUNDER, "FUNDER")
    assert "active_quotes_count" in client.get("/api/dashboard").get_json()
    _login(client, app, ADMIN, "AUDITOR")
    assert "total_face_value" in client.get("/api/dashboard").get_json()
    _login(client, app, ADMIN, "ADMIN")
    assert "recent_events" in client.get("/api/dashboard").get_json()


def test_transactions_aggregate_multiple_logs_per_hash(client, app):
    tx_hash = "0x" + "9" * 64
    with app.app_context():
        _chain_event("InvoiceSubmitted", tx_hash, 0, [SUPPLIER])
        _chain_event("TransferSingle", tx_hash, 1, [SUPPLIER],
                     {"from": "0x" + "0" * 40, "to": SUPPLIER, "id": "7", "value": "1"})
    _login(client, app, SUPPLIER, "SUPPLIER")
    items = client.get(f"/api/transactions?address={SUPPLIER}").get_json()["items"]
    assert len(items) == 1 and items[0]["tx_hash"] == tx_hash
    assert client.get(f"/api/transactions?address={OTHER}").status_code == 403


def test_events_enforce_scope_aliases_and_pagination(client, app):
    with app.app_context():
        _chain_event("InvoiceSubmitted", "0x" + "8" * 64, 0, [SUPPLIER],
                     {"supplier": SUPPLIER, "buyer": BUYER})
    _login(client, app, SUPPLIER, "SUPPLIER")
    data = client.get("/api/events?name=InvoiceSubmitted&page_size=1000").get_json()
    assert data["page_size"] == 100
    assert len(data["items"]) == 1
    assert client.get(f"/api/events?address={OTHER}").status_code == 403
    _login(client, app, ADMIN, "ADMIN")
    assert client.get("/api/events").get_json()["total"] == 1
