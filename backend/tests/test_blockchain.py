from types import SimpleNamespace

import pytest

from backend.services.blockchain import (
    RoleGrantMismatchError,
    RoleManagerService,
    RpcUnavailable,
    TxNotConfirmedError,
    TxNotFoundError,
    role_hash,
)

ACCOUNT = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"
CONTRACT = "0x3333333333333333333333333333333333333333"
TX_HASH = "0x" + "a" * 64


class Call:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def call(self):
        if self.error:
            raise self.error
        return self.value


class Functions:
    def __init__(self, registered=True, role=None, error=None):
        self.registered = registered
        self.role = role or bytes(32)
        self.error = error

    def isRegistered(self, _account):
        return Call(self.registered, self.error)

    def roleOf(self, _account):
        return Call(self.role, self.error)


class RoleGrantedEvent:
    def __init__(self, events):
        self.events = events

    def __call__(self):
        return self

    def process_receipt(self, _receipt):
        return self.events


def _service(functions=None, events=None, receipt=None, latest=12):
    service = RoleManagerService("test://rpc", CONTRACT, confirmations=2)
    contract = SimpleNamespace(
        functions=functions or Functions(),
        events=SimpleNamespace(RoleGranted=RoleGrantedEvent(events or [])),
    )
    receipt = receipt or {"status": 1, "to": CONTRACT, "blockNumber": 11}
    eth = SimpleNamespace(
        get_transaction_receipt=lambda _tx: receipt,
        get_transaction=lambda _tx: {"to": CONTRACT},
        block_number=latest,
    )
    service._client_and_contract = lambda: (SimpleNamespace(eth=eth), contract)
    return service


def _event(account=ACCOUNT, role="SUPPLIER"):
    return {"args": {"account": account, "role": bytes.fromhex(role_hash(role)[2:])}}


def test_role_lookup_maps_unregistered_admin_and_supplier():
    assert _service(Functions(registered=False)).get_role(ACCOUNT) == "NONE"
    assert _service(Functions(role=bytes(32))).get_role(ACCOUNT) == "ADMIN"
    supplier = bytes.fromhex(role_hash("SUPPLIER")[2:])
    assert _service(Functions(role=supplier)).get_role(ACCOUNT) == "SUPPLIER"


def test_role_lookup_fails_closed_on_rpc_error():
    with pytest.raises(RpcUnavailable):
        _service(Functions(error=RuntimeError("offline"))).get_role(ACCOUNT)


def test_matching_role_grant_receipt_is_accepted():
    _service(events=[_event()]).verify_role_grant(TX_HASH, ACCOUNT, "SUPPLIER")


@pytest.mark.parametrize(
    "events",
    [[_event(account=OTHER)], [_event(role="FUNDER")], []],
)
def test_mismatched_role_grant_event_is_rejected(events):
    with pytest.raises(RoleGrantMismatchError):
        _service(events=events).verify_role_grant(TX_HASH, ACCOUNT, "SUPPLIER")


def test_wrong_contract_and_failed_receipt_are_rejected():
    with pytest.raises(RoleGrantMismatchError):
        _service(receipt={"status": 1, "to": OTHER, "blockNumber": 11}).verify_role_grant(
            TX_HASH, ACCOUNT, "SUPPLIER"
        )
    with pytest.raises(RoleGrantMismatchError):
        _service(receipt={"status": 0, "to": CONTRACT, "blockNumber": 11}).verify_role_grant(
            TX_HASH, ACCOUNT, "SUPPLIER"
        )


def test_unconfirmed_role_grant_is_rejected():
    with pytest.raises(TxNotConfirmedError):
        _service(events=[_event()], latest=11).verify_role_grant(TX_HASH, ACCOUNT, "SUPPLIER")


def test_missing_transaction_is_reported():
    service = _service()
    missing_type = type("TransactionNotFound", (Exception,), {})
    web3, contract = service._client_and_contract()
    web3.eth.get_transaction_receipt = lambda _tx: (_ for _ in ()).throw(missing_type())
    service._client_and_contract = lambda: (web3, contract)
    with pytest.raises(TxNotFoundError):
        service.verify_role_grant(TX_HASH, ACCOUNT, "SUPPLIER")


def test_service_rejects_missing_provider():
    with pytest.raises(RpcUnavailable):
        RoleManagerService("", CONTRACT)._client_and_contract()
