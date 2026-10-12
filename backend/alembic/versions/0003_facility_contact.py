"""facilities: add phone + address

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("facilities", sa.Column("phone", sa.String(length=64), nullable=True))
    op.add_column("facilities", sa.Column("address", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("facilities", "address")
    op.drop_column("facilities", "phone")
