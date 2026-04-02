from fastapi import APIRouter, Depends, Response, status
from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import Query

from app.db.session import get_db
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ProjectWithTasks,
)
from app.schemas.project_planning import ProjectPlanCreate, ProjectPlanResultRead
from app.schemas.task import TaskCreate, TaskRead, TaskStatusUpdate, TaskUpdate
from app.schemas.workflow_run import (
    WorkflowRunCreate,
    WorkflowRunDetailRead,
    WorkflowRunRead,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceFileListRead,
    WorkspaceRead,
    WorkspaceUpdate,
    WorkspaceWithProjects,
)
from app.services import (
    agent_execution_service,
    project_service,
    project_planning_service,
    task_service,
    workflow_run_service,
    workspace_service,
)

router = APIRouter()


@router.post("/", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
) -> WorkspaceRead:
    return workspace_service.create_workspace(db, payload)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
) -> WorkspaceRead:
    return workspace_service.update_workspace(db, workspace_id, payload)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> Response:
    workspace_service.delete_workspace(db, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/", response_model=list[WorkspaceWithProjects])
def list_workspaces(db: Session = Depends(get_db)) -> list[WorkspaceWithProjects]:
    return workspace_service.list_workspaces(db)


@router.get("/{workspace_id}", response_model=WorkspaceWithProjects)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> WorkspaceWithProjects:
    return workspace_service.get_workspace_with_projects_or_404(db, workspace_id)


@router.get("/{workspace_id}/files", response_model=WorkspaceFileListRead)
def list_workspace_files(
    workspace_id: int,
    path: Annotated[str, Query()] = "",
    db: Session = Depends(get_db),
) -> WorkspaceFileListRead:
    return workspace_service.list_workspace_files(db, workspace_id, path)


@router.post(
    "/{workspace_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_under_workspace(
    workspace_id: int,
    payload: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectRead:
    return project_service.create_project_under_workspace(db, workspace_id, payload)


@router.patch("/{workspace_id}/projects/{project_id}", response_model=ProjectRead)
def update_project(
    workspace_id: int,
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
) -> ProjectRead:
    return project_service.update_project(db, workspace_id, project_id, payload)


@router.delete(
    "/{workspace_id}/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    workspace_id: int,
    project_id: int,
    db: Session = Depends(get_db),
) -> Response:
    project_service.delete_project(db, workspace_id, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/projects", response_model=list[ProjectWithTasks])
def list_projects_for_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> list[ProjectWithTasks]:
    return project_service.list_projects_for_workspace(db, workspace_id)


@router.post(
    "/{workspace_id}/projects/{project_id}/plan",
    response_model=ProjectPlanResultRead,
    status_code=status.HTTP_201_CREATED,
)
def plan_project(
    workspace_id: int,
    project_id: int,
    payload: ProjectPlanCreate,
    db: Session = Depends(get_db),
) -> ProjectPlanResultRead:
    return project_planning_service.plan_project_tasks(
        db,
        workspace_id,
        project_id,
        payload,
    )


@router.post(
    "/{workspace_id}/projects/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_task_under_project(
    workspace_id: int,
    project_id: int,
    payload: TaskCreate,
    db: Session = Depends(get_db),
) -> TaskRead:
    return task_service.create_task_under_project(
        db,
        workspace_id,
        project_id,
        payload,
    )


@router.patch(
    "/{workspace_id}/projects/{project_id}/tasks/{task_id}/status",
    response_model=TaskRead,
)
def update_task_status(
    workspace_id: int,
    project_id: int,
    task_id: int,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
) -> TaskRead:
    return task_service.update_task_status(
        db,
        workspace_id,
        project_id,
        task_id,
        payload,
    )


@router.patch(
    "/{workspace_id}/projects/{project_id}/tasks/{task_id}",
    response_model=TaskRead,
)
def update_task(
    workspace_id: int,
    project_id: int,
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
) -> TaskRead:
    return task_service.update_task(
        db,
        workspace_id,
        project_id,
        task_id,
        payload,
    )


@router.delete(
    "/{workspace_id}/projects/{project_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task(
    workspace_id: int,
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
) -> Response:
    task_service.delete_task(db, workspace_id, project_id, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{workspace_id}/projects/{project_id}/tasks",
    response_model=list[TaskRead],
)
def list_tasks_for_project(
    workspace_id: int,
    project_id: int,
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    return task_service.list_tasks_for_project(db, workspace_id, project_id)


@router.post(
    "/{workspace_id}/projects/{project_id}/runs",
    response_model=WorkflowRunDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_run_under_project(
    workspace_id: int,
    project_id: int,
    payload: WorkflowRunCreate,
    db: Session = Depends(get_db),
) -> WorkflowRunDetailRead:
    return workflow_run_service.create_workflow_run_under_project(
        db,
        workspace_id,
        project_id,
        payload,
    )


@router.get(
    "/{workspace_id}/projects/{project_id}/runs",
    response_model=list[WorkflowRunRead],
)
def list_workflow_runs_for_project(
    workspace_id: int,
    project_id: int,
    db: Session = Depends(get_db),
) -> list[WorkflowRunRead]:
    return workflow_run_service.list_workflow_runs_for_project(
        db,
        workspace_id,
        project_id,
    )


@router.get(
    "/{workspace_id}/projects/{project_id}/runs/{workflow_run_id}",
    response_model=WorkflowRunDetailRead,
)
def get_workflow_run_detail(
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
    db: Session = Depends(get_db),
) -> WorkflowRunDetailRead:
    return workflow_run_service.get_workflow_run_detail(
        db,
        workspace_id,
        project_id,
        workflow_run_id,
    )


@router.delete(
    "/{workspace_id}/projects/{project_id}/runs/{workflow_run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_workflow_run(
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
    db: Session = Depends(get_db),
) -> Response:
    workflow_run_service.delete_workflow_run(
        db,
        workspace_id,
        project_id,
        workflow_run_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workspace_id}/projects/{project_id}/runs/{workflow_run_id}/execute",
    response_model=WorkflowRunDetailRead,
)
def execute_workflow_run(
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
    db: Session = Depends(get_db),
) -> WorkflowRunDetailRead:
    return workflow_run_service.execute_workflow_run(
        db,
        workspace_id,
        project_id,
        workflow_run_id,
    )


@router.post(
    "/{workspace_id}/projects/{project_id}/runs/{workflow_run_id}/task-runs/{task_run_id}/execute",
    response_model=WorkflowRunDetailRead,
)
def execute_task_run(
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
    task_run_id: int,
    db: Session = Depends(get_db),
) -> WorkflowRunDetailRead:
    return agent_execution_service.execute_task_run(
        db,
        workspace_id,
        project_id,
        workflow_run_id,
        task_run_id,
    )
