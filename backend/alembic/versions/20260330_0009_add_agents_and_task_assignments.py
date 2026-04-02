"""Add agents and task assignments

Revision ID: 20260330_0009
Revises: 20260330_0008
Create Date: 2026-03-30 05:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0009"
down_revision: Union[str, Sequence[str], None] = "20260330_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_model_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_model_id"], ["provider_models.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])
    op.create_index("ix_agents_provider_model_id", "agents", ["provider_model_id"])

    op.add_column("tasks", sa.Column("agent_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_agent_id_agents",
        "tasks",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_agent_id", "tasks", ["agent_id"])

    op.add_column("task_runs", sa.Column("assigned_agent_id", sa.BigInteger(), nullable=True))
    op.add_column("task_runs", sa.Column("assigned_agent_name", sa.String(length=100), nullable=True))
    op.create_foreign_key(
        "fk_task_runs_assigned_agent_id_agents",
        "task_runs",
        "agents",
        ["assigned_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_task_runs_assigned_agent_id", "task_runs", ["assigned_agent_id"])


def downgrade() -> None:
    op.drop_index("ix_task_runs_assigned_agent_id", table_name="task_runs")
    op.drop_constraint("fk_task_runs_assigned_agent_id_agents", "task_runs", type_="foreignkey")
    op.drop_column("task_runs", "assigned_agent_name")
    op.drop_column("task_runs", "assigned_agent_id")

    op.drop_index("ix_tasks_agent_id", table_name="tasks")
    op.drop_constraint("fk_tasks_agent_id_agents", "tasks", type_="foreignkey")
    op.drop_column("tasks", "agent_id")

    op.drop_index("ix_agents_provider_model_id", table_name="agents")
    op.drop_index("ix_agents_workspace_id", table_name="agents")
    op.drop_table("agents")
