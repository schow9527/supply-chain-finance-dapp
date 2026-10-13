from datetime import timedelta
import os

from eth_keys import keys
from eth_utils import keccak

from backend.extensions import db
from backend.models import AuthNonce, utcnow


class LocalAccount:
    def __init__(self):
        self.key = keys.PrivateKey(os.urandom(32))
        self.address = self.key.public_key.to_checksum_address()

    def sign(self, message):
        prefix = f"\x19Ethereum Signed Message:\n{len(message.encode())}".encode()
        raw = bytearray(self.key.sign_msg_hash(keccak(prefix + message.encode())).to_bytes())
        raw[64] += 27
        return "0x" + bytes(raw).hex()


def _challenge(client, account):
    response = client.post("/api/auth/nonce", json={"wallet_address": account.address})
    assert response.status_code == 200
    return response.get_json()


def _verify(client, account, message):
    signature = account.sign(message)
    return client.post(
        "/api/auth/verify",
        json={"wallet_address": account.address, "signature": signature},
    )


def test_nonce_is_generated_and_only_hash_is_stored(client, app):
    account = LocalAccount()
    payload = _challenge(client, account)
    assert account.address.lower() in payload["message"]
    assert "Chain ID: 11155111" in payload["message"]
    assert "does not send a blockchain transaction or cost Gas" in payload["message"]
    with app.app_context():
        nonce = AuthNonce.query.one()
        assert len(nonce.nonce_hash) == 64
        assert nonce.nonce_hash not in payload["message"]


def test_correct_signature_creates_session(client):
    account = LocalAccount()
    payload = _challenge(client, account)
    response = _verify(client, account, payload["message"])
    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True


def test_invalid_signature_is_rejected(client):
    account = LocalAccount()
    _challenge(client, account)
    response = client.post(
        "/api/auth/verify",
        json={"wallet_address": account.address, "signature": "0xdeadbeef"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_SIGNATURE"


def test_signature_address_mismatch_is_rejected(client):
    account = LocalAccount()
    other = LocalAccount()
    payload = _challenge(client, account)
    signature = other.sign(payload["message"])
    response = client.post(
        "/api/auth/verify",
        json={"wallet_address": account.address, "signature": signature},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ADDRESS_MISMATCH"


def test_expired_nonce_is_rejected(client, app):
    account = LocalAccount()
    payload = _challenge(client, account)
    with app.app_context():
        nonce = AuthNonce.query.one()
        nonce.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    response = _verify(client, account, payload["message"])
    assert response.get_json()["error"]["code"] == "NONCE_EXPIRED"


def test_nonce_cannot_be_replayed(client):
    account = LocalAccount()
    payload = _challenge(client, account)
    assert _verify(client, account, payload["message"]).status_code == 200
    response = _verify(client, account, payload["message"])
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "NONCE_ALREADY_USED"


def test_logout_clears_session(client, app):
    account = LocalAccount()
    payload = _challenge(client, account)
    _verify(client, account, payload["message"])
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


def test_protected_api_requires_authentication(client):
    response = client.post("/api/enterprises", json={})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"
