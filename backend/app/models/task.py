from datetime import datetime

from sqlalchemy import BIGINT, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("agents.id", ondelete="SET NULL"),
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False, default="task")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="todo")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    display_order: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    canvas_x: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    canvas_y: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    task_dependencies: Mapped[list[int]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")
    agent: Mapped["Agent | None"] = relationship(back_populates="tasks")
    task_runs: Mapped[list["TaskRun"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def agent_name(self) -> str | None:
        return self.agent.name if self.agent is not None else None
