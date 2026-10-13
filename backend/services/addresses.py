"""Canonical Ethereum address handling at Web3 and persistence boundaries."""

from __future__ import annotations

from web3 import Web3

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class ContractAddressError(ValueError):
    """A named contract address is empty, malformed, truncated, or zero."""


def validate_contract_address(value: str, contract_name: str) -> str:
    if not isinstance(value, str) or not value or not Web3.is_address(value):
        raise ContractAddressError(f"{contract_name}: INVALID_CONTRACT_ADDRESS")
    if value.lower() == ZERO_ADDRESS:
        raise ContractAddressError(f"{contract_name}: ZERO_CONTRACT_ADDRESS")
    return value


def rpc_checksum_address(value: str, contract_name: str) -> str:
    """Validate first, then return the only representation passed into Web3 RPC APIs."""
    return Web3.to_checksum_address(validate_contract_address(value, contract_name))


def canonical_address(value: str, contract_name: str) -> str:
    """Lowercase form used for database/event/equality comparisons."""
    return rpc_checksum_address(value, contract_name).lower()


def masked_address(value: str) -> str:
    return f"{value[:6]}...{value[-4:]}"
