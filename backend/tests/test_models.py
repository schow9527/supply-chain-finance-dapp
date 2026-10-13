from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import ChainEvent, Enterprise, Holding, Invoice

ADDRESS = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


def _expect_duplicate(first, second):
    db.session.add(first)
    db.session.commit()
    db.session.add(second)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_enterprise_wallet_is_normalized_and_unique(app):
    def enterprise(address):
        return Enterprise(wallet_address=address, enterprise_name="Acme",
                          role_applied="SUPPLIER", contact_person="Alice")
    _expect_duplicate(enterprise(ADDRESS.upper().replace("0X", "0x")), enterprise(ADDRESS))


def test_holding_composite_unique_constraint(app):
    _expect_duplicate(
        Holding(chain_id=11155111, receivable_id=1, holder_address=ADDRESS, balance=1),
        Holding(chain_id=11155111, receivable_id=1, holder_address=ADDRESS.upper().replace("0X", "0x"), balance=2),
    )


def test_chain_event_idempotency_constraint(app):
    def event():
        return ChainEvent(chain_id=11155111, block_number=1, block_hash="0x" + "a" * 64,
                          transaction_index=0, tx_hash="0x" + "b" * 64, log_index=0,
                          contract_address=ADDRESS, contract_name="RoleManager",
                          event_name="RoleGranted", event_args={},
                          block_timestamp=datetime.now(timezone.utc))
    _expect_duplicate(event(), event())


def test_large_amount_round_trips_without_precision_loss(app):
    amount = 2**256 - 1
    invoice = Invoice(chain_id=11155111, invoice_no="INV-1", supplier_address=ADDRESS,
                      buyer_address=OTHER, amount=amount, due_date=2_000_000_000,
                      file_hash="0x" + "c" * 64, status="FILE_UPLOADED")
    db.session.add(invoice)
    db.session.commit()
    db.session.expire_all()
    stored = db.session.get(Invoice, invoice.id)
    assert stored.to_dict()["amount"] == str(amount)


@pytest.mark.parametrize("role", ["SUPPLIER", "CORE_ENTERPRISE", "FUNDER"])
def test_valid_enterprise_roles(app, role):
    item = Enterprise(wallet_address=ADDRESS, enterprise_name="Acme",
                      role_applied=role, contact_person="Alice")
    db.session.add(item)
    db.session.commit()
