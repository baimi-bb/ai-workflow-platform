from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.common import OptionalTrimmedText, TrimmedTextModelMixin

TaskStatus = Literal["todo", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]
TaskNodeType = Literal["start", "task", "end"]
TaskTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=140),
]
TaskDescription = Annotated[
    OptionalTrimmedText,
    StringConstraints(max_length=2000),
]


class TaskCreate(TrimmedTextModelMixin, BaseModel):
    agent_id: int | None = None
    title: TaskTitle
    description: TaskDescription = None
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    node_type: TaskNodeType = "task"
    display_order: int | None = None
    canvas_x: int | None = None
    canvas_y: int | None = None
    task_dependencies: list[int] = Field(default_factory=list)

    @field_validator("task_dependencies")
    @classmethod
    def validate_task_dependencies(cls, value: list[int]) -> list[int]:
        normalized: list[int] = []
        seen: set[int] = set()
        for item in value:
            if item <= 0:
                raise ValueError("Task dependency ids must be positive integers")
            if item not in seen:
                seen.add(item)
                normalized.append(item)
        return normalized


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    agent_id: int | None
    agent_name: str | None
    title: str
    description: str | None
    node_type: TaskNodeType
    status: TaskStatus
    priority: TaskPriority
    display_order: int
    canvas_x: int
    canvas_y: int
    task_dependencies: list[int]
    created_at: datetime
    updated_at: datetime


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskUpdate(TrimmedTextModelMixin, BaseModel):
    agent_id: int | None = None
    title: TaskTitle | None = None
    description: TaskDescription = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    display_order: int | None = None
    canvas_x: int | None = None
    canvas_y: int | None = None
    task_dependencies: list[int] | None = None

    @field_validator("task_dependencies")
    @classmethod
    def validate_task_dependencies(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value

        normalized: list[int] = []
        seen: set[int] = set()
        for item in value:
            if item <= 0:
                raise ValueError("Task dependency ids must be positive integers")
            if item not in seen:
                seen.add(item)
                normalized.append(item)
        return normalized
