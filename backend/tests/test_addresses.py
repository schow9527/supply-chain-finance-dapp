import json
import re
from pathlib import Path

import pytest
from web3 import Web3

from backend.config import CONTRACT_NAMES, DEPLOYMENT_FILE
from backend.services.addresses import (
    ContractAddressError,
    canonical_address,
    rpc_checksum_address,
)

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DEPLOYMENT = ROOT / "frontend" / "static" / "js" / "deployed_addresses.json"
FRONTEND_CONFIG = ROOT / "frontend" / "static" / "js" / "config.js"


def test_lowercase_and_checksum_addresses_are_safe_for_rpc():
    lowercase = "0x441c4300b1c6f900050a298d6960a5c0a7e43942"
    checksum = Web3.to_checksum_address(lowercase)

    assert rpc_checksum_address(lowercase, "RoleManager") == checksum
    assert rpc_checksum_address(checksum, "RoleManager") == checksum
    assert Web3.is_checksum_address(rpc_checksum_address(lowercase, "RoleManager"))
    assert canonical_address(checksum, "RoleManager") == lowercase


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", "INVALID_CONTRACT_ADDRESS"),
        ("0x1234", "INVALID_CONTRACT_ADDRESS"),
        ("not-an-address", "INVALID_CONTRACT_ADDRESS"),
        ("0x0000000000000000000000000000000000000000", "ZERO_CONTRACT_ADDRESS"),
    ],
)
def test_invalid_contract_addresses_are_named_and_rejected(value, code):
    with pytest.raises(ContractAddressError, match=f"InvoiceRegistry: {code}"):
        rpc_checksum_address(value, "InvoiceRegistry")


def test_manifest_frontend_backend_and_abis_are_consistent(app):
    manifest = json.loads(DEPLOYMENT_FILE.read_text(encoding="utf-8"))
    frontend = json.loads(FRONTEND_DEPLOYMENT.read_text(encoding="utf-8"))["contracts"]
    config_source = FRONTEND_CONFIG.read_text(encoding="utf-8")
    defaults_block = re.search(
        r"const DEFAULT_ADDRESSES\s*=\s*\{(?P<body>.*?)\};", config_source, re.DOTALL
    )
    assert defaults_block is not None
    defaults = dict(re.findall(r'(\w+)\s*:\s*"(0x[0-9a-fA-F]{40})"', defaults_block["body"]))

    for name in CONTRACT_NAMES:
        expected = canonical_address(manifest[name], name)
        assert canonical_address(frontend[name], name) == expected
        assert canonical_address(defaults[name], name) == expected
        assert canonical_address(app.config["CONTRACT_ADDRESSES"][name], name) == expected
        backend_abi = json.loads(
            (ROOT / "contracts" / "abi" / f"{name}.json").read_text(encoding="utf-8")
        )
        frontend_abi = json.loads(
            (ROOT / "frontend" / "static" / "js" / "abi" / f"{name}.json").read_text(
                encoding="utf-8"
            )
        )
        assert frontend_abi == backend_abi
