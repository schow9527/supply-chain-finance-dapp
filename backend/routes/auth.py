"""Wallet-signature authentication using short-lived Flask sessions."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from eth_keys import keys
from eth_utils import keccak
from flask import Blueprint, current_app, g, jsonify, request, session

from backend.auth import require_auth
from backend.errors import api_error
from backend.extensions import db
from backend.models import AuthNonce, Enterprise, utcnow
from backend.services.blockchain import RpcUnavailable, get_role_service
from backend.services.validation import normalize_wallet

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


def _recover_eip191(message: str, signature: str) -> str:
    """Recover an address, preferring eth-account with a compatible fallback."""
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct

        return Account.recover_message(encode_defunct(text=message), signature=signature)
    except (ImportError, OSError):
        raw = bytes.fromhex(signature.removeprefix("0x"))
        if len(raw) != 65:
            raise ValueError("Invalid Ethereum signature length")
        if raw[64] >= 27:
            raw = raw[:64] + bytes([raw[64] - 27])
        prefix = f"\x19Ethereum Signed Message:\n{len(message.encode())}".encode()
        public_key = keys.Signature(raw).recover_public_key_from_msg_hash(
            keccak(prefix + message.encode())
        )
        return public_key.to_checksum_address()


@auth_bp.post("/auth/nonce")
def issue_nonce():
    payload = request.get_json(silent=True) or {}
    wallet = normalize_wallet(payload.get("wallet_address"))
    if not wallet:
        return api_error("INVALID_ADDRESS", "A valid wallet address is required.", 400)

    now = utcnow()
    expires = now + timedelta(seconds=current_app.config["NONCE_TTL_SECONDS"])
    nonce = secrets.token_urlsafe(32)
    nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
    AuthNonce.query.filter_by(wallet_address=wallet, consumed_at=None).update(
        {"consumed_at": now}, synchronize_session=False
    )
    db.session.add(
        AuthNonce(
            wallet_address=wallet,
            nonce_hash=nonce_hash,
            issued_at=now,
            expires_at=expires,
        )
    )
    db.session.commit()

    message = (
        "Supply Chain Finance DApp wallet authentication\n"
        f"Wallet: {wallet}\n"
        f"Chain ID: {current_app.config['CHAIN_ID']}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {now.isoformat()}\n"
        f"Expiration Time: {expires.isoformat()}\n"
        "This signature does not send a blockchain transaction or cost Gas."
    )
    session["auth_challenge"] = {
        "wallet_address": wallet,
        "nonce_hash": nonce_hash,
        "message": message,
    }
    return jsonify(
        {"wallet_address": wallet, "message": message, "expires_at": expires.isoformat()}
    )


@auth_bp.post("/auth/verify")
def verify_signature():
    payload = request.get_json(silent=True) or {}
    wallet = normalize_wallet(payload.get("wallet_address"))
    signature = payload.get("signature")
    challenge = session.get("auth_challenge") or {}
    if not wallet or not isinstance(signature, str) or not challenge:
        return api_error("INVALID_SIGNATURE", "The signature challenge is invalid.", 401)
    if wallet != challenge.get("wallet_address"):
        return api_error("ADDRESS_MISMATCH", "Wallet address does not match the challenge.", 403)

    nonce = AuthNonce.query.filter_by(nonce_hash=challenge.get("nonce_hash")).first()
    if not nonce:
        return api_error("INVALID_SIGNATURE", "The signature challenge is invalid.", 401)
    if nonce.is_consumed:
        return api_error("NONCE_ALREADY_USED", "This nonce has already been used.", 409)
    if nonce.is_expired:
        return api_error("NONCE_EXPIRED", "This nonce has expired.", 401)
    try:
        recovered = _recover_eip191(challenge["message"], signature).lower()
    except Exception:
        return api_error("INVALID_SIGNATURE", "The wallet signature is invalid.", 401)
    if recovered != wallet:
        return api_error("ADDRESS_MISMATCH", "Signature was produced by another wallet.", 403)

    nonce.consumed_at = utcnow()
    db.session.commit()
    session["wallet_address"] = wallet
    session.permanent = True
    return jsonify({"wallet_address": wallet, "authenticated": True})


@auth_bp.post("/auth/logout")
def logout():
    session.clear()
    return "", 204


@auth_bp.get("/me")
@require_auth
def me():
    enterprise = Enterprise.query.filter_by(wallet_address=g.wallet_address).first()
    try:
        role = get_role_service().get_role(g.wallet_address)
    except RpcUnavailable:
        return api_error("RPC_UNAVAILABLE", "On-chain role lookup is unavailable.", 503)
    return jsonify(
        {
            "wallet_address": g.wallet_address,
            "role": role,
            "enterprise_name": enterprise.enterprise_name if enterprise else "",
            "status": enterprise.status if enterprise else None,
            "reject_reason": enterprise.reject_reason if enterprise else None,
        }
    )
