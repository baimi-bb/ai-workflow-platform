from datetime import datetime

from sqlalchemy import BIGINT, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_agent_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("agents.id", ondelete="SET NULL"),
    )
    assigned_agent_name: Mapped[str | None] = mapped_column(String(100))
    title_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    executor_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="system",
    )
    task_dependencies_snapshot: Mapped[list[int]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="task_runs")
    task: Mapped["Task"] = relationship(back_populates="task_runs")
    assigned_agent: Mapped["Agent | None"] = relationship(back_populates="task_runs")
