"""Add providers

Revision ID: 20260330_0007
Revises: 20260330_0006
Create Date: 2026-03-30 03:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0007"
down_revision: Union[str, Sequence[str], None] = "20260330_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("providers")
