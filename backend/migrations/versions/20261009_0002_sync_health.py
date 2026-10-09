"""Add persisted event synchronization health.

Revision ID: 20261009_0002
Revises: 20261008_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20261009_0002"
down_revision = "20261008_0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sync_state") as batch_op:
        batch_op.add_column(sa.Column("latest_chain_block", sa.BigInteger(), nullable=True))
        batch_op.add_column(
            sa.Column("status", sa.String(length=20), nullable=False,
                      server_default="healthy")
        )
        batch_op.add_column(sa.Column("last_error", sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table("sync_state") as batch_op:
        batch_op.drop_column("last_error")
        batch_op.drop_column("status")
        batch_op.drop_column("latest_chain_block")
