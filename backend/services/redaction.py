"""Secret-safe rendering for operational errors and diagnostics."""

from __future__ import annotations

import re


_AUTHORIZATION = re.compile(
    r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+|basic\s+)?[^\s,;]+"
)
_NAMED_SECRET = re.compile(
    r"(?i)\b(WEB3_PROVIDER_URI|DATABASE_URL)\s*[:=]\s*([^\s,;]+)"
)
_DATABASE_URL = re.compile(r"(?i)\b(?:postgres(?:ql)?(?:\+psycopg)?|sqlite)://[^\s,;]+")
_HTTP_URL = re.compile(r"(?i)\bhttps?://[^\s,;]+")


def redact_secrets(value: object) -> str:
    """Remove connection strings, endpoint URLs, API keys, and auth headers."""
    text = str(value)
    text = _AUTHORIZATION.sub(r"\1<redacted>", text)
    text = _NAMED_SECRET.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _DATABASE_URL.sub("<redacted-database-url>", text)
    return _HTTP_URL.sub("<redacted-url>", text)
