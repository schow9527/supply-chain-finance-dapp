"""ABI-driven contract/event registry and JSON-safe log decoding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eth_abi import decode
from eth_utils import keccak

BASE_DIR = Path(__file__).resolve().parents[2]
ABI_DIR = BASE_DIR / "contracts" / "abi"
CONTRACT_NAMES = (
    "RoleManager", "InvoiceRegistry", "ReceivableToken",
    "FinancingPool", "MockStablecoin",
)


def hex_value(value) -> str:
    if isinstance(value, str):
        return value.lower()
    rendered = value.hex() if hasattr(value, "hex") else bytes(value).hex()
    return (rendered if rendered.startswith("0x") else "0x" + rendered).lower()


def json_value(value, abi_type: str | None = None):
    if isinstance(value, bool) or value is None:
        return value
    if abi_type == "address":
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (bytes, bytearray)) or hasattr(value, "hex"):
        return hex_value(value)
    if isinstance(value, (list, tuple)):
        child_type = abi_type[:-2] if abi_type and abi_type.endswith("[]") else None
        return [json_value(item, child_type) for item in value]
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class EventDefinition:
    contract_name: str
    contract_address: str
    abi: dict

    @property
    def name(self):
        return self.abi["name"]


class ContractRegistry:
    def __init__(self, addresses: dict[str, str], abi_dir: Path = ABI_DIR):
        self.contracts = {}
        self.events_by_topic = {}
        for name in CONTRACT_NAMES:
            address = addresses[name].lower()
            abi = json.loads((abi_dir / f"{name}.json").read_text(encoding="utf-8"))
            self.contracts[address] = {"name": name, "address": address, "abi": abi}
            for item in abi:
                if item.get("type") != "event":
                    continue
                signature = f"{item['name']}({','.join(inp['type'] for inp in item['inputs'])})"
                topic = "0x" + keccak(text=signature).hex()
                self.events_by_topic[(address, topic.lower())] = EventDefinition(
                    name, address, item
                )

    @property
    def addresses(self):
        return list(self.contracts)

    def decode_log(self, log) -> dict | None:
        address = str(log["address"]).lower()
        topics = log.get("topics") or []
        if not topics:
            return None
        definition = self.events_by_topic.get((address, hex_value(topics[0])))
        if definition is None:
            return None
        indexed = [item for item in definition.abi["inputs"] if item.get("indexed")]
        plain = [item for item in definition.abi["inputs"] if not item.get("indexed")]
        args = {}
        for item, topic in zip(indexed, topics[1:], strict=True):
            abi_type = item["type"]
            if abi_type in {"string", "bytes"} or abi_type.endswith("[]"):
                value = hex_value(topic)
            else:
                value = decode([abi_type], bytes.fromhex(hex_value(topic)[2:]))[0]
            args[item["name"]] = json_value(value, abi_type)
        data = log.get("data", "0x")
        raw_data = bytes.fromhex(hex_value(data)[2:])
        values = decode([item["type"] for item in plain], raw_data) if plain else ()
        for item, value in zip(plain, values, strict=True):
            args[item["name"]] = json_value(value, item["type"])
        return {
            "contract_name": definition.contract_name,
            "event_name": definition.name,
            "event_args": args,
        }
