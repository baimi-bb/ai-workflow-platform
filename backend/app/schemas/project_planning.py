from pydantic import BaseModel, Field
from typing import Literal

from app.schemas.common import TrimmedTextModelMixin

PlanningTaskPriority = Literal["low", "medium", "high"]


class ProjectPlanCreate(TrimmedTextModelMixin, BaseModel):
    planner_agent_id: int


class ProjectPlanTaskRead(BaseModel):
    id: int
    title: str
    assigned_agent_id: int | None
    assigned_agent_name: str | None
    priority: PlanningTaskPriority
    task_dependencies: list[int] = Field(default_factory=list)


class ProjectPlanResultRead(BaseModel):
    summary: str
    created_task_count: int
    created_tasks: list[ProjectPlanTaskRead] = Field(default_factory=list)
