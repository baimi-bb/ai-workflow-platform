from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.agent import AgentRead
from app.schemas.common import OptionalTrimmedText, TrimmedTextModelMixin
from app.schemas.project import ProjectWithTasks


WorkspaceName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
WorkspaceDescription = Annotated[
    OptionalTrimmedText,
    StringConstraints(max_length=1000),
]
WorkspaceRootPath = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
OptionalWorkspaceRootPath = Annotated[
    OptionalTrimmedText,
    StringConstraints(max_length=1000),
]


class WorkspaceCreate(TrimmedTextModelMixin, BaseModel):
    name: WorkspaceName
    description: WorkspaceDescription = None
    root_path: WorkspaceRootPath


class WorkspaceUpdate(TrimmedTextModelMixin, BaseModel):
    name: WorkspaceName | None = None
    description: WorkspaceDescription = None
    root_path: OptionalWorkspaceRootPath = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    root_path: str | None
    created_at: datetime
    updated_at: datetime


class WorkspaceWithProjects(WorkspaceRead):
    projects: list[ProjectWithTasks] = Field(default_factory=list)
    agents: list[AgentRead] = Field(default_factory=list)


class WorkspaceFileEntry(BaseModel):
    name: str
    relative_path: str
    entry_type: str
    size: int | None = None
    modified_at: datetime | None = None


class WorkspaceFileListRead(BaseModel):
    workspace_id: int
    root_path: str
    current_path: str
    entries: list[WorkspaceFileEntry] = Field(default_factory=list)
