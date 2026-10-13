"""Database models for off-chain state and idempotent chain synchronization."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import validates
from sqlalchemy.types import TypeDecorator

from backend.extensions import db


class UInt256(TypeDecorator):
    """Exact uint256 storage: NUMERIC on PostgreSQL, decimal text on SQLite."""

    impl = db.Numeric(78, 0)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(db.String(78))
        return dialect.type_descriptor(db.Numeric(78, 0))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        integer = int(value)
        return str(integer) if dialect.name == "sqlite" else Decimal(integer)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_address(value: str | None) -> str | None:
    return value.lower() if isinstance(value, str) else value


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class Enterprise(TimestampMixin, db.Model):
    __tablename__ = "enterprises"
    __table_args__ = (
        db.UniqueConstraint("wallet_address", name="uq_enterprises_wallet_address"),
        db.CheckConstraint(
            "role_applied IN ('SUPPLIER', 'CORE_ENTERPRISE', 'FUNDER')",
            name="role_applied_values",
        ),
        db.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')", name="status_values"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(42), nullable=False, index=True)
    enterprise_name = db.Column(db.String(200), nullable=False)
    role_applied = db.Column(db.String(32), nullable=False)
    contact_person = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    reject_reason = db.Column(db.Text)
    approval_tx_hash = db.Column(db.String(66))
    reviewed_by = db.Column(db.String(42))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    chain_role = db.Column(db.String(32))
    revoked_at = db.Column(db.DateTime(timezone=True))

    @validates("wallet_address", "reviewed_by")
    def normalize_wallets(self, _key, value):
        return normalize_address(value)

    def to_dict(self):
        return {
            "id": self.id,
            "wallet_address": self.wallet_address,
            "enterprise_name": self.enterprise_name,
            "role_applied": self.role_applied,
            "contact_person": self.contact_person,
            "status": self.status,
            "reject_reason": self.reject_reason,
            "approval_tx_hash": self.approval_tx_hash,
            "tx_hash": self.approval_tx_hash,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": _iso(self.reviewed_at),
            "chain_role": self.chain_role,
            "revoked_at": _iso(self.revoked_at),
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class Invoice(TimestampMixin, db.Model):
    __tablename__ = "invoices"
    __table_args__ = (
        db.UniqueConstraint("onchain_id", name="uq_invoices_onchain_id"),
        db.CheckConstraint(
            "status IN ('FILE_UPLOADED', 'FILE_MISSING', 'PENDING', 'CONFIRMED', 'REJECTED')",
            name="status_values",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    chain_id = db.Column(db.BigInteger, nullable=False, default=11155111, index=True)
    onchain_id = db.Column(UInt256(), index=True)
    invoice_no = db.Column(db.String(100), nullable=False, index=True)
    supplier_address = db.Column(db.String(42), nullable=False, index=True)
    buyer_address = db.Column(db.String(42), nullable=False, index=True)
    amount = db.Column(UInt256(), nullable=False)
    due_date = db.Column(db.BigInteger, nullable=False)
    file_hash = db.Column(db.String(66), nullable=False)
    storage_key = db.Column(db.String(500))
    original_filename = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default="FILE_UPLOADED")
    reject_reason = db.Column(db.Text)
    submit_tx_hash = db.Column(db.String(66))
    submit_block_number = db.Column(db.BigInteger)
    confirmed_tx_hash = db.Column(db.String(66))
    confirmed_at = db.Column(db.DateTime(timezone=True))
    rejected_tx_hash = db.Column(db.String(66))

    @validates("supplier_address", "buyer_address")
    def normalize_wallets(self, _key, value):
        return normalize_address(value)

    def to_dict(self):
        return {
            "id": self.id,
            "chain_id": self.chain_id,
            "onchain_id": _integer_string(self.onchain_id),
            "invoice_no": self.invoice_no,
            "supplier_address": self.supplier_address,
            "buyer_address": self.buyer_address,
            "amount": _integer_string(self.amount),
            "due_date": self.due_date,
            "file_hash": self.file_hash,
            "storage_key": self.storage_key,
            "original_filename": self.original_filename,
            "status": self.status,
            "reject_reason": self.reject_reason,
            "tx_hash": self.submit_tx_hash,
            "submit_block_number": self.submit_block_number,
            "confirmed_tx_hash": self.confirmed_tx_hash,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class Holding(db.Model):
    __tablename__ = "holdings"
    __table_args__ = (
        db.UniqueConstraint(
            "chain_id", "receivable_id", "holder_address",
            name="uq_holdings_holding_identity",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    chain_id = db.Column(db.BigInteger, nullable=False, default=11155111)
    receivable_id = db.Column(UInt256(), nullable=False)
    holder_address = db.Column(db.String(42), nullable=False, index=True)
    balance = db.Column(UInt256(), nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    @validates("holder_address")
    def normalize_wallet(self, _key, value):
        return normalize_address(value)


class Receivable(db.Model):
    __tablename__ = "receivables"
    id = db.Column(db.Integer, primary_key=True)
    chain_id = db.Column(db.BigInteger, nullable=False)
    receivable_id = db.Column(UInt256(), nullable=False)
    supplier_address = db.Column(db.String(42), nullable=False, index=True)
    buyer_address = db.Column(db.String(42), nullable=False, index=True)
    face_value = db.Column(UInt256(), nullable=False)
    due_date = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    frozen = db.Column(db.Boolean, nullable=False, default=False)
    freeze_reason = db.Column(db.Text)
    frozen_by = db.Column(db.String(42))
    minted_tx_hash = db.Column(db.String(66))
    repayment_amount = db.Column(UInt256())
    repayment_tx_hash = db.Column(db.String(66))
    repaid_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    __table_args__ = (
        db.UniqueConstraint("chain_id", "receivable_id", name="uq_receivables_chain_id"),
    )

    @validates("supplier_address", "buyer_address", "frozen_by")
    def normalize_wallets(self, _key, value):
        return normalize_address(value)


class FinancingRequest(TimestampMixin, db.Model):
    __tablename__ = "financing_requests"
    __table_args__ = (
        db.UniqueConstraint(
            "onchain_request_id", name="uq_financing_requests_onchain_request_id"
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    onchain_request_id = db.Column(UInt256(), nullable=False)
    receivable_id = db.Column(UInt256(), nullable=False, index=True)
    supplier_address = db.Column(db.String(42), nullable=False, index=True)
    amount = db.Column(UInt256(), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="PENDING_QUOTE")
    accepted_quote_id = db.Column(UInt256())
    request_tx_hash = db.Column(db.String(66))
    funded_tx_hash = db.Column(db.String(66))
    funder_address = db.Column(db.String(42))
    payout = db.Column(UInt256())

    @validates("supplier_address")
    def normalize_wallet(self, _key, value):
        return normalize_address(value)


class Quote(TimestampMixin, db.Model):
    __tablename__ = "quotes"
    __table_args__ = (
        db.UniqueConstraint("onchain_quote_id", name="uq_quotes_onchain_quote_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    onchain_quote_id = db.Column(UInt256(), nullable=False)
    onchain_request_id = db.Column(UInt256(), nullable=False, index=True)
    financier_address = db.Column(db.String(42), nullable=False, index=True)
    discount_rate_bps = db.Column(db.Integer, nullable=False)
    payout = db.Column(UInt256(), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="SUBMITTED")
    submit_tx_hash = db.Column(db.String(66))

    @validates("financier_address")
    def normalize_wallet(self, _key, value):
        return normalize_address(value)


class ChainEvent(db.Model):
    __tablename__ = "chain_events"
    __table_args__ = (
        db.UniqueConstraint(
            "chain_id", "tx_hash", "log_index", name="uq_chain_events_chain_log"
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    chain_id = db.Column(db.BigInteger, nullable=False)
    block_number = db.Column(db.BigInteger, nullable=False, index=True)
    block_hash = db.Column(db.String(66), nullable=False)
    transaction_index = db.Column(db.Integer, nullable=False)
    tx_hash = db.Column(db.String(66), nullable=False, index=True)
    log_index = db.Column(db.Integer, nullable=False)
    contract_address = db.Column(db.String(42), nullable=False)
    contract_name = db.Column(db.String(100), nullable=False, index=True)
    event_name = db.Column(db.String(100), nullable=False, index=True)
    event_args = db.Column(db.JSON, nullable=False)
    participants = db.Column(db.JSON, nullable=False, default=list)
    block_timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    @validates("contract_address")
    def normalize_contract(self, _key, value):
        return normalize_address(value)


class SyncState(db.Model):
    __tablename__ = "sync_state"
    __table_args__ = (
        db.UniqueConstraint(
            "chain_id", "contract_address", name="uq_sync_state_chain_contract"
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    chain_id = db.Column(db.BigInteger, nullable=False)
    contract_address = db.Column(db.String(42), nullable=False)
    contract_name = db.Column(db.String(100), nullable=False)
    last_synced_block = db.Column(db.BigInteger, nullable=False, default=0)
    last_synced_block_hash = db.Column(db.String(66))
    latest_chain_block = db.Column(db.BigInteger)
    status = db.Column(db.String(20), nullable=False, default="healthy")
    last_error = db.Column(db.String(100))
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    @validates("contract_address")
    def normalize_contract(self, _key, value):
        return normalize_address(value)


class AuthNonce(db.Model):
    __tablename__ = "auth_nonces"
    __table_args__ = (
        db.UniqueConstraint("nonce_hash", name="uq_auth_nonces_nonce_hash"),
    )
    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(42), nullable=False, index=True)
    nonce_hash = db.Column(db.String(64), nullable=False)
    issued_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    consumed_at = db.Column(db.DateTime(timezone=True))

    @validates("wallet_address")
    def normalize_wallet(self, _key, value):
        return normalize_address(value)

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= utcnow()


def _integer_string(value: Decimal | int | None) -> str | None:
    return None if value is None else str(int(value))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
