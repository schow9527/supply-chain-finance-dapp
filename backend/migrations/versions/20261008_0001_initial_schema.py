"""Initial application and database foundation.

Revision ID: 20261008_0001
Revises: None
"""

from alembic import op
import sqlalchemy as sa

revision = "20261008_0001"
down_revision = None
branch_labels = None
depends_on = None
UINT256 = sa.Numeric(78, 0).with_variant(sa.String(78), "sqlite")


def upgrade():
    op.create_table(
        "auth_nonces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_address", sa.String(42), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_auth_nonces"),
        sa.UniqueConstraint("nonce_hash", name="uq_auth_nonces_nonce_hash"),
    )
    op.create_index("ix_auth_nonces_wallet_address", "auth_nonces", ["wallet_address"])
    op.create_index("ix_auth_nonces_expires_at", "auth_nonces", ["expires_at"])

    op.create_table(
        "enterprises",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_address", sa.String(42), nullable=False),
        sa.Column("enterprise_name", sa.String(200), nullable=False),
        sa.Column("role_applied", sa.String(32), nullable=False),
        sa.Column("contact_person", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("approval_tx_hash", sa.String(66), nullable=True),
        sa.Column("reviewed_by", sa.String(42), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role_applied IN ('SUPPLIER', 'CORE_ENTERPRISE', 'FUNDER')", name="ck_enterprises_role_applied_values"),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_enterprises_status_values"),
        sa.PrimaryKeyConstraint("id", name="pk_enterprises"),
        sa.UniqueConstraint("wallet_address", name="uq_enterprises_wallet_address"),
    )
    op.create_index("ix_enterprises_wallet_address", "enterprises", ["wallet_address"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("onchain_id", UINT256, nullable=True),
        sa.Column("invoice_no", sa.String(100), nullable=False),
        sa.Column("supplier_address", sa.String(42), nullable=False),
        sa.Column("buyer_address", sa.String(42), nullable=False),
        sa.Column("amount", UINT256, nullable=False),
        sa.Column("due_date", sa.BigInteger(), nullable=False),
        sa.Column("file_hash", sa.String(66), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('FILE_UPLOADED', 'FILE_MISSING', 'PENDING', 'CONFIRMED', 'REJECTED')", name="ck_invoices_status_values"),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
        sa.UniqueConstraint("onchain_id", name="uq_invoices_onchain_id"),
    )
    for column in ("chain_id", "onchain_id", "invoice_no", "supplier_address", "buyer_address"):
        op.create_index(f"ix_invoices_{column}", "invoices", [column])

    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("receivable_id", UINT256, nullable=False),
        sa.Column("holder_address", sa.String(42), nullable=False),
        sa.Column("balance", UINT256, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_holdings"),
        sa.UniqueConstraint("chain_id", "receivable_id", "holder_address", name="uq_holdings_holding_identity"),
    )
    op.create_index("ix_holdings_holder_address", "holdings", ["holder_address"])

    op.create_table(
        "financing_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("onchain_request_id", UINT256, nullable=False),
        sa.Column("receivable_id", UINT256, nullable=False),
        sa.Column("supplier_address", sa.String(42), nullable=False),
        sa.Column("amount", UINT256, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("accepted_quote_id", UINT256, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_financing_requests"),
        sa.UniqueConstraint("onchain_request_id", name="uq_financing_requests_onchain_request_id"),
    )
    op.create_index("ix_financing_requests_receivable_id", "financing_requests", ["receivable_id"])
    op.create_index("ix_financing_requests_supplier_address", "financing_requests", ["supplier_address"])

    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("onchain_quote_id", UINT256, nullable=False),
        sa.Column("onchain_request_id", UINT256, nullable=False),
        sa.Column("financier_address", sa.String(42), nullable=False),
        sa.Column("discount_rate_bps", sa.Integer(), nullable=False),
        sa.Column("payout", UINT256, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quotes"),
        sa.UniqueConstraint("onchain_quote_id", name="uq_quotes_onchain_quote_id"),
    )
    op.create_index("ix_quotes_onchain_request_id", "quotes", ["onchain_request_id"])
    op.create_index("ix_quotes_financier_address", "quotes", ["financier_address"])

    op.create_table(
        "chain_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("block_number", sa.BigInteger(), nullable=False),
        sa.Column("block_hash", sa.String(66), nullable=False),
        sa.Column("transaction_index", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.String(66), nullable=False),
        sa.Column("log_index", sa.Integer(), nullable=False),
        sa.Column("contract_address", sa.String(42), nullable=False),
        sa.Column("contract_name", sa.String(100), nullable=False),
        sa.Column("event_name", sa.String(100), nullable=False),
        sa.Column("event_args", sa.JSON(), nullable=False),
        sa.Column("block_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chain_events"),
        sa.UniqueConstraint("chain_id", "tx_hash", "log_index", name="uq_chain_events_chain_log"),
    )
    for column in ("block_number", "tx_hash", "contract_name", "event_name"):
        op.create_index(f"ix_chain_events_{column}", "chain_events", [column])

    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_address", sa.String(42), nullable=False),
        sa.Column("contract_name", sa.String(100), nullable=False),
        sa.Column("last_synced_block", sa.BigInteger(), nullable=False),
        sa.Column("last_synced_block_hash", sa.String(66), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sync_state"),
        sa.UniqueConstraint("chain_id", "contract_address", name="uq_sync_state_chain_contract"),
    )


def downgrade():
    op.drop_table("sync_state")
    for column in ("event_name", "contract_name", "tx_hash", "block_number"):
        op.drop_index(f"ix_chain_events_{column}", table_name="chain_events")
    op.drop_table("chain_events")
    op.drop_index("ix_quotes_financier_address", table_name="quotes")
    op.drop_index("ix_quotes_onchain_request_id", table_name="quotes")
    op.drop_table("quotes")
    op.drop_index("ix_financing_requests_supplier_address", table_name="financing_requests")
    op.drop_index("ix_financing_requests_receivable_id", table_name="financing_requests")
    op.drop_table("financing_requests")
    op.drop_index("ix_holdings_holder_address", table_name="holdings")
    op.drop_table("holdings")
    for column in ("buyer_address", "supplier_address", "invoice_no", "onchain_id", "chain_id"):
        op.drop_index(f"ix_invoices_{column}", table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_enterprises_wallet_address", table_name="enterprises")
    op.drop_table("enterprises")
    op.drop_index("ix_auth_nonces_expires_at", table_name="auth_nonces")
    op.drop_index("ix_auth_nonces_wallet_address", table_name="auth_nonces")
    op.drop_table("auth_nonces")
