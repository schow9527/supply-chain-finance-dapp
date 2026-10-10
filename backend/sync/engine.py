"""Idempotent, globally ordered blockchain event synchronization."""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timezone

from eth_utils import is_address
from flask import current_app
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

from backend.config import ZERO_ADDRESS
from backend.extensions import db
from backend.models import ChainEvent, SyncState, utcnow
from backend.services.addresses import ContractAddressError, rpc_checksum_address
from backend.sync.registry import ContractRegistry, hex_value
from backend.sync.projections import project_event

logger = logging.getLogger(__name__)
CURSOR_NAME = "__all_contracts__"
RPC_MAX_ATTEMPTS = 4
RPC_RETRY_BASE_SECONDS = 0.5
RPC_RETRY_MAX_SECONDS = 4.0
RPC_RETRY_JITTER_SECONDS = 0.25


class SyncError(RuntimeError):
    pass


class SyncStartupError(SyncError):
    def __init__(self, code: str, *, check_id: str, detail: str):
        super().__init__(code)
        self.code = code
        self.check_id = check_id
        self.detail = detail


class ChainReorgDetected(SyncError):
    pass


class SyncRpcError(SyncError):
    def __init__(self, code: str, *, http_status: int | None, category: str,
                 detail: str = "request_failed"):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.category = category
        self.detail = detail


class _RpcRangeLimit(Exception):
    def __init__(self, http_status: int | None):
        self.http_status = http_status


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _response_text(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    body = getattr(response, "text", "") if response is not None else ""
    return f"{body} {exc}".lower()


def _is_range_limit(exc: Exception) -> bool:
    status = _http_status(exc)
    if status not in {None, 400}:
        return False
    message = _response_text(exc)
    explicit = (
        "block range", "block-range", "range too wide", "range is too wide",
        "max block", "maximum block", "up to a 10 block", "10 block range",
        "query returned more", "too many results", "response size", "-32005",
    )
    return any(token in message for token in explicit)


def _retry_category(exc: Exception) -> str | None:
    status = _http_status(exc)
    if status == 408 or isinstance(exc, RequestsTimeout):
        return "timeout"
    if status == 429:
        return "rate_limited"
    if status is not None and 500 <= status <= 599:
        return "server_error"
    if isinstance(exc, RequestsConnectionError):
        return "network_error"
    return None


def safe_sync_error(exc: Exception) -> dict[str, object]:
    """Return stable fields only; never include exception messages or URLs."""
    if isinstance(exc, SyncRpcError):
        return {
            "code": exc.code,
            "http_status": exc.http_status if exc.http_status is not None else "none",
            "category": exc.category,
            "detail": exc.detail,
        }
    if isinstance(exc, SyncStartupError):
        return {
            "code": exc.code,
            "http_status": "none",
            "category": "startup",
            "detail": f"check={exc.check_id} reason={exc.detail}",
        }
    status = _http_status(exc)
    if status is not None:
        return {
            "code": "RPC_HTTP_ERROR",
            "http_status": status,
            "category": _retry_category(exc) or "client_error",
            "detail": "request_failed",
        }
    return {
        "code": "SYNC_FAILED",
        "http_status": "none",
        "category": type(exc).__name__,
        "detail": "operation_failed",
    }


def create_web3_provider(uri: str):
    if not uri:
        raise SyncStartupError(
            "RPC_UNAVAILABLE", check_id="CHAIN_ID", detail="provider_not_configured"
        )
    try:
        from web3 import Web3

        # Do not call Web3.is_connected(): it probes web3_clientVersion, while
        # production preflight and the worker only require Ethereum RPC methods.
        return Web3(Web3.HTTPProvider(uri, request_kwargs={"timeout": 10}))
    except SyncStartupError:
        raise
    except Exception as exc:
        raise SyncStartupError(
            "RPC_UNAVAILABLE", check_id="CHAIN_ID", detail="provider_initialization_failed"
        ) from exc


def _startup_error_for_check(check) -> SyncStartupError:
    check_id = check.name
    if check_id == "DATABASE":
        return SyncStartupError(
            "DATABASE_UNAVAILABLE", check_id=check_id, detail="connection_failed"
        )
    if check_id == "MIGRATIONS":
        return SyncStartupError(
            "MIGRATION_REQUIRED", check_id=check_id,
            detail="revision_or_schema_mismatch",
        )
    if check_id == "SYNC_STATE":
        return SyncStartupError(
            "SYNC_STATE_INVALID", check_id=check_id, detail="invalid_cursor_state"
        )
    if check_id in {"CONTRACT_CONFIG", "SYNC_START_BLOCK"}:
        return SyncStartupError(
            "CONTRACT_CONFIG_INVALID", check_id=check_id,
            detail="deployment_configuration_mismatch",
        )
    if check_id in {"CHAIN_ID", "CONTRACTS", "CONTRACT_LINKS"}:
        rpc_failure = any(token in check.detail for token in (
            "RPC", "unavailable", "VIEW_ERROR", "LINK_ERROR",
        ))
        return SyncStartupError(
            "RPC_UNAVAILABLE" if rpc_failure else "CONTRACT_CONFIG_INVALID",
            check_id=check_id,
            detail="rpc_request_failed" if rpc_failure else "contract_validation_failed",
        )
    return SyncStartupError(
        "CONFIG_INVALID", check_id=check_id, detail="worker_configuration_invalid"
    )


def _field(value, *names):
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    raise KeyError(names[0])


class EventSynchronizer:
    def __init__(self, app, provider=None, projector=None, sleep=time.sleep,
                 jitter=None):
        self.app = app
        addresses = app.config["CONTRACT_ADDRESSES"]
        self.registry = ContractRegistry(addresses)
        self.provider = provider or app.config.get("SYNC_PROVIDER")
        if self.provider is not None:
            self.registry.codec = getattr(self.provider, "codec", None)
        self.projector = projector or project_event
        self.sleep = sleep
        self.jitter = jitter or (
            lambda: random.uniform(0, RPC_RETRY_JITTER_SECONDS)
        )

    def _provider(self):
        if self.provider is None:
            self.provider = create_web3_provider(self.app.config.get("WEB3_PROVIDER_URI", ""))
            self.registry.codec = getattr(self.provider, "codec", None)
        return self.provider

    def validate_startup(self):
        configured_role = (self.app.config.get("PROCESS_ROLE") or
                           self.app.config.get("PROCESS_TYPE", "web")).lower()
        if configured_role != "worker":
            raise SyncStartupError(
                "CONFIG_INVALID", check_id="PROCESS_ROLE", detail="worker_role_required"
            )
        if self.app.config.get("EVENT_SYNC_ENABLED") is not True:
            raise SyncStartupError(
                "CONFIG_INVALID", check_id="EVENT_SYNC_ENABLED", detail="disabled"
            )
        try:
            batch_size = int(self.app.config.get("EVENT_SYNC_BATCH_SIZE", 0))
        except (TypeError, ValueError):
            batch_size = 0
        if batch_size <= 0:
            raise SyncStartupError(
                "CONFIG_INVALID", check_id="EVENT_SYNC_BATCH_SIZE",
                detail="must_be_positive",
            )

        provider = self._provider()

        if self.app.config.get("ENV_NAME") == "production":
            from backend.preflight import collect_preflight

            checks = collect_preflight(self.app, role="worker", web3=provider)
            failure = next(
                (check for check in checks if check.critical and not check.passed), None
            )
            if failure is not None:
                raise _startup_error_for_check(failure)
            return True

        try:
            chain_id = int(provider.eth.chain_id)
        except Exception as exc:
            raise SyncStartupError(
                "RPC_UNAVAILABLE", check_id="CHAIN_ID", detail="rpc_request_failed"
            ) from exc
        if chain_id != int(self.app.config["CHAIN_ID"]):
            raise SyncStartupError(
                "CONTRACT_CONFIG_INVALID", check_id="CHAIN_ID",
                detail="chain_id_mismatch",
            )
        for name, raw_address in self.app.config["CONTRACT_ADDRESSES"].items():
            try:
                address = rpc_checksum_address(raw_address, name)
            except ContractAddressError as exc:
                raise SyncStartupError(
                    "CONTRACT_CONFIG_INVALID", check_id=f"CONTRACT_ADDRESS_{name}",
                    detail="invalid_contract_address",
                ) from exc
            try:
                code = provider.eth.get_code(address)
            except Exception as exc:
                raise SyncStartupError(
                    "RPC_UNAVAILABLE", check_id=f"CONTRACT_CODE_{name}",
                    detail="rpc_request_failed",
                ) from exc
            if not code or hex_value(code) in {"0x", "0x0", "0x00"}:
                raise SyncStartupError(
                    "CONTRACT_CONFIG_INVALID", check_id=f"CONTRACT_CODE_{name}",
                    detail="bytecode_missing",
                )
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
        batch_size = int(self.app.config["EVENT_SYNC_BATCH_SIZE"])
        if batch_size <= 0:
            raise SyncStartupError(
                "CONFIG_INVALID", check_id="EVENT_SYNC_BATCH_SIZE",
                detail="must_be_positive",
            )
        while next_block <= safe_head:
            to_block = min(next_block + batch_size - 1, safe_head)
            total += self._sync_batch(next_block, to_block, latest)
            next_block = to_block + 1
        return total

    def _sync_batch(self, from_block: int, to_block: int, latest: int):
        started = time.monotonic()
        provider = self._provider()
        try:
            logs = self._get_logs(provider, from_block, to_block)
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
                    participants=sorted({
                        value.lower() for value in decoded["event_args"].values()
                        if isinstance(value, str) and len(value) == 42
                        and value.startswith("0x") and is_address(value)
                    }),
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

    def _get_logs(self, provider, from_block: int, to_block: int):
        """Fetch every block, shrinking ranges when a provider caps result sizes."""
        addresses = [
            rpc_checksum_address(address, name)
            for name, address in self.app.config["CONTRACT_ADDRESSES"].items()
        ]
        try:
            return self._request_logs(provider, {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": addresses,
            })
        except _RpcRangeLimit as exc:
            if from_block >= to_block:
                raise SyncRpcError(
                    "RPC_RANGE_LIMIT", http_status=exc.http_status,
                    category="range_limit", detail="single_block_rejected",
                ) from None
            middle = (from_block + to_block) // 2
            return (self._get_logs(provider, from_block, middle)
                    + self._get_logs(provider, middle + 1, to_block))

    def _request_logs(self, provider, params):
        for attempt in range(RPC_MAX_ATTEMPTS):
            try:
                return provider.eth.get_logs(params)
            except Exception as exc:
                status = _http_status(exc)
                if _is_range_limit(exc):
                    raise _RpcRangeLimit(status) from None
                category = _retry_category(exc)
                if category is None:
                    raise SyncRpcError(
                        "RPC_HTTP_ERROR" if status is not None else "RPC_REQUEST_FAILED",
                        http_status=status,
                        category="client_error" if status is not None else "rpc_error",
                    ) from None
                if attempt + 1 >= RPC_MAX_ATTEMPTS:
                    raise SyncRpcError(
                        "RPC_RETRY_EXHAUSTED", http_status=status,
                        category=category, detail="retry_limit_reached",
                    ) from None
                delay = min(
                    RPC_RETRY_BASE_SECONDS * (2 ** attempt), RPC_RETRY_MAX_SECONDS
                ) + max(0.0, float(self.jitter()))
                self.sleep(delay)

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
            except Exception as exc:
                safe = safe_sync_error(exc)
                logger.error(
                    "event_sync_failed chain_id=%s code=%s http_status=%s "
                    "category=%s detail=%s",
                    self.app.config["CHAIN_ID"], safe["code"],
                    safe["http_status"], safe["category"], safe["detail"],
                )
                self.sleep(delay)
                delay = min(delay * 2, 60)
