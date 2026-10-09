"""Small validation helpers shared by API routes."""

from __future__ import annotations

import re

from eth_utils import is_address

CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_wallet(value) -> str | None:
    if not isinstance(value, str) or not is_address(value):
        return None
    return value.lower()


def clean_text(value, *, minimum: int = 1, maximum: int = 200) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum or CONTROL_CHARS.search(cleaned):
        return None
    return cleaned
