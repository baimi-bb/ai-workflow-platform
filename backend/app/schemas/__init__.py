"""Pydantic schemas package."""

from app.schemas.error import ErrorDetail, ErrorResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ProjectWithTasks,
)
from app.schemas.task import TaskCreate, TaskRead, TaskStatusUpdate, TaskUpdate
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
    WorkspaceWithProjects,
)

__all__ = [
    "WorkspaceCreate",
    "WorkspaceRead",
    "WorkspaceUpdate",
    "WorkspaceWithProjects",
    "ProjectCreate",
    "ProjectRead",
    "ProjectUpdate",
    "ProjectWithTasks",
    "TaskCreate",
    "TaskRead",
    "TaskStatusUpdate",
    "TaskUpdate",
    "ErrorDetail",
    "ErrorResponse",
]
