from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import OptionalTrimmedText, TrimmedTextModelMixin
from app.schemas.task import TaskRead

ProjectStatus = Literal["active", "paused", "done"]
ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ProjectDescription = Annotated[
    OptionalTrimmedText,
    StringConstraints(max_length=1000),
]


class ProjectCreate(TrimmedTextModelMixin, BaseModel):
    name: ProjectName
    description: ProjectDescription = None
    status: ProjectStatus = "active"


class ProjectUpdate(TrimmedTextModelMixin, BaseModel):
    name: ProjectName | None = None
    description: ProjectDescription = None
    status: ProjectStatus | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectWithTasks(ProjectRead):
    tasks: list[TaskRead] = Field(default_factory=list)
