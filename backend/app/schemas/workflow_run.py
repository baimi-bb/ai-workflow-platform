from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


WorkflowRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
WorkflowRunTriggerType = Literal["manual", "api", "schedule", "retry"]
TaskRunStatus = Literal[
    "pending",
    "ready",
    "running",
    "waiting_human",
    "completed",
    "failed",
    "skipped",
    "cancelled",
]
TaskRunExecutorType = Literal["system", "agent", "human"]


class WorkflowRunCreate(BaseModel):
    trigger_type: WorkflowRunTriggerType = "manual"
    input_payload: dict | None = None


class TaskRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_run_id: int
    task_id: int
    assigned_agent_id: int | None
    assigned_agent_name: str | None
    title_snapshot: str
    node_type: str
    status: TaskRunStatus
    executor_type: TaskRunExecutorType
    task_dependencies_snapshot: list[int] = Field(default_factory=list)
    input_payload: dict | None
    output_payload: dict | None
    error_message: str | None
    attempt_count: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: WorkflowRunStatus
    trigger_type: WorkflowRunTriggerType
    input_payload: dict | None
    output_payload: dict | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkflowRunDetailRead(WorkflowRunRead):
    task_runs: list[TaskRunRead] = Field(default_factory=list)
