"""Add task node fields

Revision ID: 20260327_0003
Revises: 20260327_0002
Create Date: 2026-03-27 00:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0003"
down_revision: Union[str, Sequence[str], None] = "20260327_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("node_type", sa.String(length=20), nullable=False, server_default="task"),
    )
    op.add_column(
        "tasks",
        sa.Column("display_order", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE tasks SET node_type = 'task' WHERE node_type IS NULL OR node_type = ''")
    op.execute(
        """
        WITH ordered_tasks AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY id) AS row_num
            FROM tasks
        )
        UPDATE tasks
        SET display_order = ordered_tasks.row_num
        FROM ordered_tasks
        WHERE tasks.id = ordered_tasks.id
        """
    )
    op.execute(
        """
        INSERT INTO tasks (
            project_id,
            title,
            description,
            node_type,
            status,
            priority,
            display_order,
            task_dependencies
        )
        SELECT
            projects.id,
            'Start',
            'Default start node',
            'start',
            'done',
            'low',
            0,
            '[]'::jsonb
        FROM projects
        WHERE NOT EXISTS (
            SELECT 1
            FROM tasks
            WHERE tasks.project_id = projects.id
              AND tasks.node_type = 'start'
        )
        """
    )
    op.execute(
        """
        INSERT INTO tasks (
            project_id,
            title,
            description,
            node_type,
            status,
            priority,
            display_order,
            task_dependencies
        )
        SELECT
            projects.id,
            'End',
            'Default end node',
            'end',
            'todo',
            'low',
            COALESCE((
                SELECT MAX(tasks.display_order) + 1
                FROM tasks
                WHERE tasks.project_id = projects.id
            ), 1),
            '[]'::jsonb
        FROM projects
        WHERE NOT EXISTS (
            SELECT 1
            FROM tasks
            WHERE tasks.project_id = projects.id
              AND tasks.node_type = 'end'
        )
        """
    )
    op.execute("ALTER TABLE tasks ALTER COLUMN node_type DROP DEFAULT")
    op.execute("ALTER TABLE tasks ALTER COLUMN display_order DROP DEFAULT")


def downgrade() -> None:
    op.drop_column("tasks", "display_order")
    op.drop_column("tasks", "node_type")
