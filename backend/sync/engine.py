"""Idempotent, globally ordered blockchain event synchronization."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from eth_utils import is_address
from flask import current_app

from backend.config import ZERO_ADDRESS
from backend.extensions import db
from backend.models import ChainEvent, SyncState, utcnow
from backend.sync.registry import ContractRegistry, hex_value

logger = logging.getLogger(__name__)
CURSOR_NAME = "__all_contracts__"


class SyncError(RuntimeError):
    pass


class SyncStartupError(SyncError):
    pass


class ChainReorgDetected(SyncError):
    pass


def create_web3_provider(uri: str):
    try:
        from web3 import Web3

        provider = Web3(Web3.HTTPProvider(uri, request_kwargs={"timeout": 10}))
        if not provider.is_connected():
            raise SyncStartupError("RPC_UNAVAILABLE")
        return provider
    except SyncStartupError:
        raise
    except Exception as exc:
        raise SyncStartupError("RPC_UNAVAILABLE") from exc


def _field(value, *names):
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    raise KeyError(names[0])


class EventSynchronizer:
    def __init__(self, app, provider=None, projector=None, sleep=time.sleep):
        self.app = app
        addresses = app.config["CONTRACT_ADDRESSES"]
        self.registry = ContractRegistry(addresses)
        self.provider = provider or app.config.get("SYNC_PROVIDER")
        self.projector = projector or (lambda _event: None)
        self.sleep = sleep

    def _provider(self):
        if self.provider is None:
            self.provider = create_web3_provider(self.app.config.get("WEB3_PROVIDER_URI", ""))
        return self.provider

    def validate_startup(self):
        provider = self._provider()
        if int(provider.eth.chain_id) != int(self.app.config["CHAIN_ID"]):
            raise SyncStartupError("CHAIN_ID_MISMATCH")
        for address in self.registry.addresses:
            if not is_address(address):
                raise SyncStartupError("INVALID_CONTRACT_ADDRESS")
            code = provider.eth.get_code(address)
            if not code or hex_value(code) in {"0x", "0x0", "0x00"}:
                raise SyncStartupError("CONTRACT_CODE_MISSING")
        return True

    def _cursor(self):
        cursor = SyncState.query.filter_by(
            chain_id=self.app.config["CHAIN_ID"], contract_address=ZERO_ADDRESS
        ).first()
        if cursor is None:
            cursor = SyncState(
                chain_id=self.app.config["CHAIN_ID"],
                contract_address=ZERO_ADDRESS,
                contract_name=CURSOR_NAME,
                last_synced_block=int(self.app.config["SYNC_START_BLOCK"]) - 1,
                status="healthy",
            )
            db.session.add(cursor)
            db.session.flush()
        return cursor

    def _check_reorg(self, cursor):
        if cursor.last_synced_block_hash is None:
            return
        block = self._provider().eth.get_block(cursor.last_synced_block)
        actual = hex_value(_field(block, "hash"))
        if actual != cursor.last_synced_block_hash.lower():
            cursor.status = "degraded"
            cursor.last_error = "CHAIN_REORG_DETECTED"
            db.session.commit()
            raise ChainReorgDetected("CHAIN_REORG_DETECTED")

    def run_once(self):
        provider = self._provider()
        cursor = self._cursor()
        self._check_reorg(cursor)
        latest = int(provider.eth.block_number)
        cursor.latest_chain_block = latest
        safe_head = latest - int(self.app.config["BLOCK_CONFIRMATIONS"])
        next_block = cursor.last_synced_block + 1
        if next_block > safe_head:
            cursor.status = "healthy"
            cursor.last_error = None
            db.session.commit()
            return 0
        total = 0
        batch_size = int(self.app.config["SYNC_BATCH_SIZE"])
        while next_block <= safe_head:
            to_block = min(next_block + batch_size - 1, safe_head)
            total += self._sync_batch(next_block, to_block, latest)
            next_block = to_block + 1
        return total

    def _sync_batch(self, from_block: int, to_block: int, latest: int):
        started = time.monotonic()
        provider = self._provider()
        try:
            logs = provider.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": self.registry.addresses,
            })
            logs = sorted(logs, key=lambda log: (
                int(_field(log, "blockNumber", "block_number")),
                int(_field(log, "transactionIndex", "transaction_index")),
                int(_field(log, "logIndex", "log_index")),
            ))
            count = 0
            block_cache = {}
            for raw in logs:
                decoded = self.registry.decode_log(raw)
                if decoded is None:
                    logger.warning(
                        "unknown_event_topic chain_id=%s block=%s",
                        self.app.config["CHAIN_ID"],
                        _field(raw, "blockNumber", "block_number"),
                    )
                    continue
                tx_hash = hex_value(_field(raw, "transactionHash", "transaction_hash"))
                log_index = int(_field(raw, "logIndex", "log_index"))
                exists = ChainEvent.query.filter_by(
                    chain_id=self.app.config["CHAIN_ID"],
                    tx_hash=tx_hash,
                    log_index=log_index,
                ).first()
                if exists:
                    continue
                block_number = int(_field(raw, "blockNumber", "block_number"))
                if block_number not in block_cache:
                    block_cache[block_number] = provider.eth.get_block(block_number)
                block = block_cache[block_number]
                timestamp = datetime.fromtimestamp(
                    int(_field(block, "timestamp")), tz=timezone.utc
                )
                event = ChainEvent(
                    chain_id=self.app.config["CHAIN_ID"],
                    block_number=block_number,
                    block_hash=hex_value(_field(raw, "blockHash", "block_hash")),
                    transaction_index=int(_field(raw, "transactionIndex", "transaction_index")),
                    tx_hash=tx_hash,
                    log_index=log_index,
                    contract_address=str(raw["address"]).lower(),
                    contract_name=decoded["contract_name"],
                    event_name=decoded["event_name"],
                    event_args=decoded["event_args"],
                    block_timestamp=timestamp,
                    processed_at=utcnow(),
                )
                db.session.add(event)
                db.session.flush()
                self.projector(event)
                count += 1
            cursor = self._cursor()
            end_block = provider.eth.get_block(to_block)
            cursor.last_synced_block = to_block
            cursor.last_synced_block_hash = hex_value(_field(end_block, "hash"))
            cursor.latest_chain_block = latest
            cursor.status = "healthy"
            cursor.last_error = None
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        logger.info(
            "event_sync chain_id=%s from_block=%s to_block=%s event_count=%s duration=%.3f last_synced_block=%s",
            self.app.config["CHAIN_ID"], from_block, to_block, count,
            time.monotonic() - started, to_block,
        )
        return count

    def run_forever(self, stop_event: threading.Event | None = None, max_cycles=None):
        stop_event = stop_event or threading.Event()
        self.validate_startup()
        delay = 1
        cycles = 0
        while not stop_event.is_set():
            try:
                self.run_once()
                delay = 1
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    return
                stop_event.wait(float(self.app.config["SYNC_POLL_INTERVAL"]))
            except ChainReorgDetected:
                raise
            except Exception:
                logger.exception("event_sync_failed chain_id=%s", self.app.config["CHAIN_ID"])
                self.sleep(delay)
                delay = min(delay * 2, 60)
