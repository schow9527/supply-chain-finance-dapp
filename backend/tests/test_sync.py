from types import SimpleNamespace

import pytest
from eth_abi import encode

from backend.config import ZERO_ADDRESS
from backend.extensions import db
from backend.models import ChainEvent, SyncState
from backend.sync.engine import ChainReorgDetected, EventSynchronizer, SyncStartupError
from backend.sync.registry import hex_value

ACCOUNT = "0x1111111111111111111111111111111111111111"


class FakeEth:
    def __init__(self, chain_id=11155111, latest=12, logs=None):
        self.chain_id = chain_id
        self.block_number = latest
        self.logs = logs or []
        self.calls = []
        self.missing_code = None
        self.hash_overrides = {}

    def get_code(self, address):
        missing = self.missing_code and address.lower() == self.missing_code.lower()
        return b"" if missing else b"\x60\x00"

    def get_logs(self, params):
        self.calls.append((params["fromBlock"], params["toBlock"]))
        return [log for log in self.logs
                if params["fromBlock"] <= log["blockNumber"] <= params["toBlock"]]

    def get_block(self, number):
        block_hash = self.hash_overrides.get(number, number.to_bytes(32, "big"))
        return {"hash": block_hash, "timestamp": 1_700_000_000 + number}


class FakeProvider:
    def __init__(self, **kwargs):
        self.eth = FakeEth(**kwargs)


def _sync(app, provider=None, projector=None, sleep=None):
    app.config.update(
        SYNC_START_BLOCK=10,
        SYNC_BATCH_SIZE=500,
        BLOCK_CONFIRMATIONS=0,
    )
    kwargs = {"projector": projector or (lambda _event: None)}
    if sleep is not None:
        kwargs["sleep"] = sleep
    return EventSynchronizer(app, provider or FakeProvider(), **kwargs)


def _event_log(sync, contract, event_name, values, *, block=10, tx=0, index=0):
    address = sync.app.config["CONTRACT_ADDRESSES"][contract].lower()
    topic, definition = next(
        (topic, definition)
        for (event_address, topic), definition in sync.registry.events_by_topic.items()
        if event_address == address and definition.name == event_name
    )
    indexed = [item for item in definition.abi["inputs"] if item["indexed"]]
    plain = [item for item in definition.abi["inputs"] if not item["indexed"]]
    topics = [bytes.fromhex(topic[2:])]
    topics.extend(encode([item["type"]], [values[item["name"]]]) for item in indexed)
    data = encode([item["type"] for item in plain], [values[item["name"]] for item in plain])
    return {
        "address": address,
        "topics": topics,
        "data": data,
        "blockNumber": block,
        "blockHash": block.to_bytes(32, "big"),
        "transactionIndex": tx,
        "transactionHash": (tx + 1).to_bytes(32, "big"),
        "logIndex": index,
    }


def _paused(sync, **position):
    return _event_log(sync, "RoleManager", "Paused", {"account": ACCOUNT}, **position)


def test_worker_startup_validates_chain_and_contract_code(app):
    sync = _sync(app)
    assert sync.validate_startup() is True
    bad_chain = _sync(app, FakeProvider(chain_id=1))
    with pytest.raises(SyncStartupError, match="CHAIN_ID_MISMATCH"):
        bad_chain.validate_startup()
    missing = FakeProvider()
    missing.eth.missing_code = sync.registry.addresses[0]
    with pytest.raises(SyncStartupError, match="CONTRACT_CODE_MISSING"):
        _sync(app, missing).validate_startup()


def test_empty_range_does_not_fetch_logs(app):
    provider = FakeProvider(latest=8)
    assert _sync(app, provider).run_once() == 0
    assert provider.eth.calls == []


def test_single_event_is_decoded_and_saved(app):
    provider = FakeProvider(latest=10)
    sync = _sync(app, provider)
    provider.eth.logs = [_paused(sync)]
    assert sync.run_once() == 1
    event = ChainEvent.query.one()
    assert event.event_name == "Paused"
    assert event.event_args == {"account": ACCOUNT}


def test_multi_contract_logs_are_globally_sorted(app):
    seen = []
    provider = FakeProvider(latest=10)
    sync = _sync(app, provider, projector=lambda event: seen.append(event.event_name))
    invoice = _event_log(sync, "InvoiceRegistry", "InvoiceConfirmed",
                         {"invoiceId": 7, "buyer": ACCOUNT}, block=10, tx=1, index=2)
    paused = _paused(sync, block=10, tx=0, index=3)
    provider.eth.logs = [invoice, paused]
    assert sync.run_once() == 2
    assert seen == ["Paused", "InvoiceConfirmed"]


def test_block_ranges_are_split_into_batches(app):
    provider = FakeProvider(latest=14)
    sync = _sync(app, provider)
    app.config["SYNC_BATCH_SIZE"] = 2
    sync.run_once()
    assert provider.eth.calls == [(10, 11), (12, 13), (14, 14)]


def test_provider_result_limit_shrinks_without_skipping_blocks(app):
    provider = FakeProvider(latest=13)
    original = provider.eth.get_logs

    def limited(params):
        if params["toBlock"] - params["fromBlock"] >= 2:
            provider.eth.calls.append((params["fromBlock"], params["toBlock"]))
            raise ValueError("query returned more than provider limit")
        return original(params)

    provider.eth.get_logs = limited
    sync = _sync(app, provider)
    sync.run_once()
    assert provider.eth.calls == [(10, 13), (10, 11), (12, 13)]
    assert SyncState.query.one().last_synced_block == 13


def test_restart_uses_saved_cursor(app):
    provider = FakeProvider(latest=11)
    first = _sync(app, provider)
    first.run_once()
    provider.eth.block_number = 13
    second = _sync(app, provider)
    second.run_once()
    assert provider.eth.calls[-1] == (12, 13)


def test_duplicate_log_is_not_projected_twice(app):
    calls = []
    provider = FakeProvider(latest=10)
    sync = _sync(app, provider, projector=lambda event: calls.append(event.tx_hash))
    provider.eth.logs = [_paused(sync)]
    sync._sync_batch(10, 10, 10)
    sync._sync_batch(10, 10, 10)
    assert ChainEvent.query.count() == 1
    assert len(calls) == 1


def test_batch_failure_rolls_back_events_and_cursor(app):
    provider = FakeProvider(latest=10)
    sync = _sync(app, provider, projector=lambda _event: (_ for _ in ()).throw(RuntimeError("bad projection")))
    provider.eth.logs = [_paused(sync)]
    with pytest.raises(RuntimeError, match="bad projection"):
        sync.run_once()
    assert ChainEvent.query.count() == 0
    assert SyncState.query.count() == 0


def test_saved_block_hash_mismatch_stops_sync(app):
    provider = FakeProvider(latest=10)
    sync = _sync(app, provider)
    sync.run_once()
    provider.eth.block_number = 11
    provider.eth.hash_overrides[10] = b"x" * 32
    with pytest.raises(ChainReorgDetected, match="CHAIN_REORG_DETECTED"):
        sync.run_once()
    cursor = SyncState.query.filter_by(contract_address=ZERO_ADDRESS).one()
    assert cursor.status == "degraded"
    assert cursor.last_synced_block == 10


def test_unknown_topic_does_not_break_known_event(app):
    provider = FakeProvider(latest=10)
    sync = _sync(app, provider)
    unknown = _paused(sync, tx=0, index=0)
    unknown["topics"][0] = b"z" * 32
    provider.eth.logs = [unknown, _paused(sync, tx=1, index=1)]
    assert sync.run_once() == 1
    assert ChainEvent.query.count() == 1


def test_temporary_failure_retries_with_backoff(app, monkeypatch):
    sleeps = []
    sync = _sync(app, sleep=lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(sync, "validate_startup", lambda: True)
    attempts = iter([RuntimeError("offline"), None])

    def run_once():
        result = next(attempts)
        if result:
            raise result
        return 0

    monkeypatch.setattr(sync, "run_once", run_once)
    sync.run_forever(max_cycles=1)
    assert sleeps == [1]


def test_sync_cli_runs_once_and_reports_status(app):
    app.config.update(
        SYNC_PROVIDER=FakeProvider(latest=9),
        SYNC_START_BLOCK=10,
        BLOCK_CONFIRMATIONS=0,
    )
    runner = app.test_cli_runner()
    once = runner.invoke(args=["sync-events", "--once"])
    assert once.exit_code == 0, once.output
    assert "synced_events=0" in once.output
    status = runner.invoke(args=["sync-status"])
    assert status.exit_code == 0
    assert "status=healthy" in status.output
