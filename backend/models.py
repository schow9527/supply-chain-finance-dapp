import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Enterprise(Base):
    __tablename__ = "enterprises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(42), unique=True, nullable=False, index=True)
    enterprise_name = Column(String(200), nullable=False)
    role_applied = Column(String(50), nullable=False) # SUPPLIER, CORE_ENTERPRISE, FINANCIER
    contact_person = Column(String(100), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, APPROVED, REJECTED
    reject_reason = Column(Text, nullable=True)
    tx_hash = Column(String(66), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "wallet_address": self.wallet_address,
            "enterprise_name": self.enterprise_name,
            "role_applied": self.role_applied,
            "contact_person": self.contact_person,
            "status": self.status,
            "reject_reason": self.reject_reason,
            "tx_hash": self.tx_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    onchain_id = Column(Integer, nullable=True, index=True)
    invoice_no = Column(String(100), nullable=False, index=True)
    supplier_address = Column(String(42), nullable=False, index=True)
    buyer_address = Column(String(42), nullable=False, index=True)
    amount = Column(String(78), nullable=False) # Store large wei numbers as string
    due_date = Column(BigInteger, nullable=False) # Unix timestamp
    file_hash = Column(String(66), nullable=False) # SHA-256 hex
    file_path = Column(String(500), nullable=True)
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, CONFIRMED, REJECTED
    reject_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "onchain_id": self.onchain_id,
            "invoice_no": self.invoice_no,
            "supplier_address": self.supplier_address,
            "buyer_address": self.buyer_address,
            "amount": self.amount,
            "due_date": self.due_date,
            "file_hash": self.file_hash,
            "file_path": self.file_path,
            "status": self.status,
            "reject_reason": self.reject_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receivable_id = Column(Integer, nullable=False, index=True)
    holder_address = Column(String(42), nullable=False, index=True)
    balance = Column(String(78), default="0", nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "receivable_id": self.receivable_id,
            "holder_address": self.holder_address,
            "balance": self.balance,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class FinancingRequest(Base):
    __tablename__ = "financing_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    onchain_request_id = Column(Integer, nullable=True, index=True)
    receivable_id = Column(Integer, nullable=False, index=True)
    supplier_address = Column(String(42), nullable=False, index=True)
    amount = Column(String(78), nullable=False)
    status = Column(String(20), default="PENDING_QUOTE", nullable=False) # PENDING_QUOTE, FUNDED, CANCELLED
    accepted_quote_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "onchain_request_id": self.onchain_request_id,
            "receivable_id": self.receivable_id,
            "supplier_address": self.supplier_address,
            "amount": self.amount,
            "status": self.status,
            "accepted_quote_id": self.accepted_quote_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    onchain_quote_id = Column(Integer, nullable=True, index=True)
    request_id = Column(Integer, nullable=False, index=True)
    financier_address = Column(String(42), nullable=False, index=True)
    discount_rate_bps = Column(Integer, nullable=False) # e.g. 500 = 5%
    status = Column(String(20), default="SUBMITTED", nullable=False) # SUBMITTED, ACCEPTED, REJECTED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "onchain_quote_id": self.onchain_quote_id,
            "request_id": self.request_id,
            "financier_address": self.financier_address,
            "discount_rate_bps": self.discount_rate_bps,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ChainEvent(Base):
    __tablename__ = "chain_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    block_number = Column(BigInteger, nullable=False, index=True)
    tx_hash = Column(String(66), nullable=False, index=True)
    contract_name = Column(String(100), nullable=False, index=True)
    event_name = Column(String(100), nullable=False, index=True)
    event_args_json = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "block_number": self.block_number,
            "tx_hash": self.tx_hash,
            "contract_name": self.contract_name,
            "event_name": self.event_name,
            "event_args_json": self.event_args_json,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class SyncState(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_name = Column(String(100), unique=True, nullable=False)
    last_synced_block = Column(BigInteger, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "contract_name": self.contract_name,
            "last_synced_block": self.last_synced_block,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
