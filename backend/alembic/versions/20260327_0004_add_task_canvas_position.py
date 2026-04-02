"""Add task canvas position

Revision ID: 20260327_0004
Revises: 20260327_0003
Create Date: 2026-03-27 00:50:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0004"
down_revision: Union[str, Sequence[str], None] = "20260327_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("canvas_x", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tasks",
        sa.Column("canvas_y", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        WITH ordered_tasks AS (
            SELECT
                id,
                node_type,
                display_order,
                ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY display_order, id) AS row_num
            FROM tasks
        )
        UPDATE tasks
        SET
            canvas_x = CASE
                WHEN ordered_tasks.node_type = 'start' THEN 40
                WHEN ordered_tasks.node_type = 'end' THEN 1160
                ELSE 420 + GREATEST(ordered_tasks.display_order - 1, 0) * 160
            END,
            canvas_y = CASE
                WHEN ordered_tasks.node_type = 'start' THEN 120
                WHEN ordered_tasks.node_type = 'end' THEN 120
                ELSE 120 + GREATEST(ordered_tasks.row_num - 2, 0) * 36
            END
        FROM ordered_tasks
        WHERE tasks.id = ordered_tasks.id
        """
    )
    op.execute("ALTER TABLE tasks ALTER COLUMN canvas_x DROP DEFAULT")
    op.execute("ALTER TABLE tasks ALTER COLUMN canvas_y DROP DEFAULT")


def downgrade() -> None:
    op.drop_column("tasks", "canvas_y")
    op.drop_column("tasks", "canvas_x")
