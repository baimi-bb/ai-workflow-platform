from datetime import datetime

from sqlalchemy import BIGINT, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_model_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("provider_models.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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

    workspace: Mapped["Workspace"] = relationship(back_populates="agents")
    provider_model: Mapped["ProviderModel"] = relationship(back_populates="agents")
    tasks: Mapped[list["Task"]] = relationship(back_populates="agent")
    task_runs: Mapped[list["TaskRun"]] = relationship(back_populates="assigned_agent")

    @property
    def provider_model_label(self) -> str | None:
        return self.provider_model.label if self.provider_model is not None else None

    @property
    def provider_model_name(self) -> str | None:
        return self.provider_model.model_name if self.provider_model is not None else None

    @property
    def provider_label(self) -> str | None:
        provider_model = self.provider_model
        if provider_model is None or provider_model.provider is None:
            return None
        return provider_model.provider.label

    @property
    def provider_platform(self) -> str | None:
        provider_model = self.provider_model
        if provider_model is None or provider_model.provider is None:
            return None
        return provider_model.provider.platform
