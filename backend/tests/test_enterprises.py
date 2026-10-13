from backend.extensions import db
from backend.models import Enterprise
from backend.services.blockchain import (
    RoleGrantMismatchError,
    RpcUnavailable,
    TxNotConfirmedError,
    TxNotFoundError,
)

USER = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"
TX_HASH = "0x" + "a" * 64


def _login(client, wallet=USER):
    with client.session_transaction() as session:
        session["wallet_address"] = wallet


def _payload(wallet=USER, role="SUPPLIER"):
    return {
        "wallet_address": wallet,
        "enterprise_name": "Acme Supply",
        "contact_person": "Alice",
        "role_applied": role,
    }


def _enterprise(app, status="PENDING"):
    with app.app_context():
        item = Enterprise(
            wallet_address=USER,
            enterprise_name="Acme",
            contact_person="Alice",
            role_applied="SUPPLIER",
            status=status,
        )
        db.session.add(item)
        db.session.commit()
        return item.id


def test_enterprise_application(client):
    _login(client)
    response = client.post("/api/enterprises", json=_payload(role="FINANCIER"))
    assert response.status_code == 201
    assert response.get_json()["status"] == "PENDING"


def test_enterprise_address_impersonation(client):
    _login(client)
    response = client.post("/api/enterprises", json=_payload(OTHER))
    assert response.get_json()["error"]["code"] == "ADDRESS_MISMATCH"


def test_duplicate_enterprise_application(client):
    _login(client)
    assert client.post("/api/enterprises", json=_payload()).status_code == 201
    response = client.post("/api/enterprises", json=_payload())
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "ENTERPRISE_ALREADY_EXISTS"


def test_invalid_enterprise_role(client):
    _login(client)
    response = client.post("/api/enterprises", json=_payload(role="ADMIN"))
    assert response.get_json()["error"]["code"] == "INVALID_ROLE"


def test_non_admin_cannot_list_or_review(client, app):
    item_id = _enterprise(app)
    _login(client)
    app.config["ROLE_SERVICE"].roles[USER] = "SUPPLIER"
    assert client.get("/api/enterprises").status_code == 403
    assert client.patch(f"/api/enterprises/{item_id}", json={"status": "REJECTED"}).status_code == 403


def test_rejection_requires_reason(client, app):
    item_id = _enterprise(app)
    _login(client)
    app.config["ROLE_SERVICE"].roles[USER] = "ADMIN"
    response = client.patch(f"/api/enterprises/{item_id}", json={"status": "REJECTED"})
    assert response.status_code == 422


def test_admin_can_reject_application(client, app):
    item_id = _enterprise(app)
    _login(client)
    app.config["ROLE_SERVICE"].roles[USER] = "ADMIN"
    response = client.patch(
        f"/api/enterprises/{item_id}",
        json={"status": "REJECTED", "reject_reason": "Documents missing"},
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "REJECTED"


def test_forged_transaction_hash_is_rejected(client, app):
    item_id = _enterprise(app)
    _login(client)
    service = app.config["ROLE_SERVICE"]
    service.roles[USER] = "ADMIN"
    service.verification_error = TxNotFoundError()
    response = client.patch(
        f"/api/enterprises/{item_id}", json={"status": "APPROVED", "tx_hash": TX_HASH}
    )
    assert response.get_json()["error"]["code"] == "TX_NOT_FOUND"


def test_mismatched_role_grant_is_rejected(client, app):
    item_id = _enterprise(app)
    _login(client)
    service = app.config["ROLE_SERVICE"]
    service.roles[USER] = "ADMIN"
    service.verification_error = RoleGrantMismatchError()
    response = client.patch(
        f"/api/enterprises/{item_id}", json={"status": "APPROVED", "tx_hash": TX_HASH}
    )
    assert response.get_json()["error"]["code"] == "ROLE_GRANT_MISMATCH"


def test_matching_role_grant_approves_application(client, app):
    item_id = _enterprise(app)
    _login(client)
    service = app.config["ROLE_SERVICE"]
    service.roles[USER] = "ADMIN"
    response = client.patch(
        f"/api/enterprises/{item_id}", json={"status": "APPROVED", "tx_hash": TX_HASH}
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "APPROVED"
    assert service.verified == [(TX_HASH, USER, "SUPPLIER")]


def test_unconfirmed_role_grant_returns_stable_error(client, app):
    item_id = _enterprise(app)
    _login(client)
    service = app.config["ROLE_SERVICE"]
    service.roles[USER] = "ADMIN"
    service.verification_error = TxNotConfirmedError()
    response = client.patch(
        f"/api/enterprises/{item_id}", json={"status": "APPROVED", "tx_hash": TX_HASH}
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "TX_NOT_CONFIRMED"


def test_rpc_failure_blocks_approval(client, app):
    item_id = _enterprise(app)
    _login(client)
    service = app.config["ROLE_SERVICE"]
    service.roles[USER] = "ADMIN"
    service.verification_error = RpcUnavailable()
    response = client.patch(
        f"/api/enterprises/{item_id}", json={"status": "APPROVED", "tx_hash": TX_HASH}
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "RPC_UNAVAILABLE"
