"""Add provider models

Revision ID: 20260330_0008
Revises: 20260330_0007
Create Date: 2026-03-30 04:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0008"
down_revision: Union[str, Sequence[str], None] = "20260330_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_models",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("supports_tools", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_models_provider_id", "provider_models", ["provider_id"])


def downgrade() -> None:
    op.drop_index("ix_provider_models_provider_id", table_name="provider_models")
    op.drop_table("provider_models")
