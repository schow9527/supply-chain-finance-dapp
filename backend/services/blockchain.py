"""Read-only RoleManager access and transaction receipt verification."""

from __future__ import annotations

import json
from pathlib import Path

from flask import current_app
from eth_utils import keccak

from backend.services.addresses import canonical_address, rpc_checksum_address

BASE_DIR = Path(__file__).resolve().parents[2]
ROLE_ABI_FILE = BASE_DIR / "contracts" / "abi" / "RoleManager.json"
ZERO_ROLE = "0x" + "0" * 64
CHAIN_ROLES = ("SUPPLIER", "CORE_ENTERPRISE", "FUNDER", "AUDITOR")


def _hex(value) -> str:
    rendered = value.hex() if hasattr(value, "hex") else str(value)
    return rendered if rendered.startswith("0x") else "0x" + rendered


class RpcUnavailable(RuntimeError):
    pass


class TxNotFoundError(ValueError):
    pass


class TxNotConfirmedError(ValueError):
    pass


class RoleGrantMismatchError(ValueError):
    pass


def role_hash(role: str) -> str:
    if role == "ADMIN":
        return ZERO_ROLE
    if role not in CHAIN_ROLES:
        raise ValueError("Unknown chain role")
    return "0x" + keccak(text=role).hex()


class RoleManagerService:
    def __init__(self, provider_uri: str, contract_address: str, confirmations: int = 1):
        self.provider_uri = provider_uri
        self.contract_address = contract_address
        self.confirmations = max(1, int(confirmations))
        self._abi = json.loads(ROLE_ABI_FILE.read_text(encoding="utf-8"))

    def _client_and_contract(self):
        if not self.provider_uri:
            raise RpcUnavailable("Sepolia RPC is not configured")
        try:
            from web3 import Web3

            web3 = Web3(Web3.HTTPProvider(self.provider_uri, request_kwargs={"timeout": 3}))
            if not web3.is_connected():
                raise RpcUnavailable("Sepolia RPC is unavailable")
            contract = web3.eth.contract(
                address=rpc_checksum_address(self.contract_address, "RoleManager"),
                abi=self._abi,
            )
            return web3, contract
        except RpcUnavailable:
            raise
        except Exception as exc:
            raise RpcUnavailable("Sepolia RPC is unavailable") from exc

    def get_role(self, wallet_address: str) -> str:
        web3, contract = self._client_and_contract()
        try:
            account = rpc_checksum_address(wallet_address, "Wallet")
            if not contract.functions.isRegistered(account).call():
                return "NONE"
            value = _hex(contract.functions.roleOf(account).call()).lower()
        except Exception as exc:
            raise RpcUnavailable("Unable to read the on-chain role") from exc
        if value == ZERO_ROLE:
            return "ADMIN"
        for role in CHAIN_ROLES:
            if value == role_hash(role).lower():
                return role
        return "NONE"

    def verify_role_grant(self, tx_hash: str, account: str, role: str) -> None:
        web3, contract = self._client_and_contract()
        try:
            receipt = web3.eth.get_transaction_receipt(tx_hash)
        except Exception as exc:
            if exc.__class__.__name__ == "TransactionNotFound":
                raise TxNotFoundError("Role grant transaction was not found") from exc
            raise RpcUnavailable("Unable to read the transaction receipt") from exc

        if int(receipt.get("status", 0)) != 1:
            raise RoleGrantMismatchError("Role grant transaction failed")
        target = receipt.get("to")
        if not target:
            try:
                target = web3.eth.get_transaction(tx_hash).get("to")
            except Exception as exc:
                if exc.__class__.__name__ == "TransactionNotFound":
                    raise TxNotFoundError("Role grant transaction was not found") from exc
                raise RpcUnavailable("Unable to read the transaction") from exc
        try:
            target_matches = (
                canonical_address(target, "TransactionTarget")
                == canonical_address(self.contract_address, "RoleManager")
            )
        except ValueError:
            target_matches = False
        if not target_matches:
            raise RoleGrantMismatchError("Transaction target is not RoleManager")

        try:
            latest = int(web3.eth.block_number)
        except Exception as exc:
            raise RpcUnavailable("Unable to read the latest block") from exc
        confirmations = latest - int(receipt["blockNumber"]) + 1
        if confirmations < self.confirmations:
            raise TxNotConfirmedError("Role grant transaction is awaiting confirmations")

        expected_account = account.lower()
        expected_role = role_hash(role).lower()
        try:
            events = contract.events.RoleGranted().process_receipt(receipt)
        except Exception as exc:
            raise RoleGrantMismatchError("RoleGranted event could not be decoded") from exc
        matched = any(
            str(event["args"]["account"]).lower() == expected_account
            and _hex(event["args"]["role"]).lower() == expected_role
            for event in events
        )
        if not matched:
            raise RoleGrantMismatchError("RoleGranted event does not match the application")


def get_role_service():
    injected = current_app.config.get("ROLE_SERVICE")
    if injected is not None:
        return injected
    return RoleManagerService(
        current_app.config.get("WEB3_PROVIDER_URI", ""),
        current_app.config["ROLE_MANAGER_ADDRESS"],
        current_app.config.get("BLOCK_CONFIRMATIONS", 1),
    )
