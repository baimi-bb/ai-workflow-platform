"""Add workspace root path

Revision ID: 20260330_0006
Revises: 20260330_0005
Create Date: 2026-03-30 01:50:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0006"
down_revision: Union[str, Sequence[str], None] = "20260330_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("root_path", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "root_path")
