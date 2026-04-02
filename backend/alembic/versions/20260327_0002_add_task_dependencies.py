"""Add task dependencies to tasks

Revision ID: 20260327_0002
Revises: 20260326_0001
Create Date: 2026-03-27 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0002"
down_revision: Union[str, Sequence[str], None] = "20260326_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "task_dependencies",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "task_dependencies")
