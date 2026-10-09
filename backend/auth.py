"""Session authentication and on-chain role authorization helpers."""

from __future__ import annotations

from functools import wraps

from flask import g, session

from backend.errors import api_error
from backend.services.blockchain import RpcUnavailable, get_role_service


def session_wallet() -> str | None:
    value = session.get("wallet_address")
    return value.lower() if isinstance(value, str) else None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        wallet = session_wallet()
        if not wallet:
            return api_error("AUTH_REQUIRED", "Wallet authentication is required.", 401)
        g.wallet_address = wallet
        return view(*args, **kwargs)

    return wrapped


def require_roles(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @require_auth
        def wrapped(*args, **kwargs):
            try:
                role = get_role_service().get_role(g.wallet_address)
            except RpcUnavailable:
                return api_error(
                    "RPC_UNAVAILABLE", "On-chain role verification is unavailable.", 503
                )
            if role not in allowed_roles:
                return api_error("ROLE_REQUIRED", "The required on-chain role is missing.", 403)
            g.chain_role = role
            return view(*args, **kwargs)

        return wrapped

    return decorator
