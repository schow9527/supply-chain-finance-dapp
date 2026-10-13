"""Add chain projection fields and receivables.

Revision ID: 20261009_0003
Revises: 20261009_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20261009_0003"
down_revision = "20261009_0002"
branch_labels = None
depends_on = None
UINT256 = sa.Numeric(78, 0).with_variant(sa.String(78), "sqlite")


def upgrade():
    with op.batch_alter_table("enterprises") as batch:
        batch.add_column(sa.Column("chain_role", sa.String(32)))
        batch.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True)))
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("submit_tx_hash", sa.String(66)))
        batch.add_column(sa.Column("submit_block_number", sa.BigInteger()))
        batch.add_column(sa.Column("confirmed_tx_hash", sa.String(66)))
        batch.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("rejected_tx_hash", sa.String(66)))
    with op.batch_alter_table("financing_requests") as batch:
        batch.add_column(sa.Column("request_tx_hash", sa.String(66)))
        batch.add_column(sa.Column("funded_tx_hash", sa.String(66)))
        batch.add_column(sa.Column("funder_address", sa.String(42)))
        batch.add_column(sa.Column("payout", UINT256))
    with op.batch_alter_table("quotes") as batch:
        batch.add_column(sa.Column("submit_tx_hash", sa.String(66)))
    with op.batch_alter_table("chain_events") as batch:
        batch.add_column(sa.Column("participants", sa.JSON(), nullable=False,
                                   server_default="[]"))
    op.create_table(
        "receivables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("receivable_id", UINT256, nullable=False),
        sa.Column("supplier_address", sa.String(42), nullable=False),
        sa.Column("buyer_address", sa.String(42), nullable=False),
        sa.Column("face_value", UINT256, nullable=False),
        sa.Column("due_date", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("frozen", sa.Boolean(), nullable=False),
        sa.Column("freeze_reason", sa.Text()),
        sa.Column("frozen_by", sa.String(42)),
        sa.Column("minted_tx_hash", sa.String(66)),
        sa.Column("repayment_amount", UINT256),
        sa.Column("repayment_tx_hash", sa.String(66)),
        sa.Column("repaid_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_receivables"),
        sa.UniqueConstraint("chain_id", "receivable_id", name="uq_receivables_chain_id"),
    )
    op.create_index("ix_receivables_supplier_address", "receivables", ["supplier_address"])
    op.create_index("ix_receivables_buyer_address", "receivables", ["buyer_address"])


def downgrade():
    op.drop_index("ix_receivables_buyer_address", table_name="receivables")
    op.drop_index("ix_receivables_supplier_address", table_name="receivables")
    op.drop_table("receivables")
    with op.batch_alter_table("chain_events") as batch:
        batch.drop_column("participants")
    with op.batch_alter_table("quotes") as batch:
        batch.drop_column("submit_tx_hash")
    with op.batch_alter_table("financing_requests") as batch:
        batch.drop_column("payout")
        batch.drop_column("funder_address")
        batch.drop_column("funded_tx_hash")
        batch.drop_column("request_tx_hash")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_column("rejected_tx_hash")
        batch.drop_column("confirmed_at")
        batch.drop_column("confirmed_tx_hash")
        batch.drop_column("submit_block_number")
        batch.drop_column("submit_tx_hash")
    with op.batch_alter_table("enterprises") as batch:
        batch.drop_column("revoked_at")
        batch.drop_column("chain_role")
