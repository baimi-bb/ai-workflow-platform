from datetime import datetime, UTC

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.agent import Agent
from app.models.project import Project
from app.models.task import Task
from app.models.task_run import TaskRun
from app.models.workflow_run import WorkflowRun
from app.schemas.workflow_run import WorkflowRunCreate
from app.services import agent_execution_service
from app.services.project_service import get_project_for_workspace_or_404


def _list_project_tasks(db: Session, project_id: int) -> list[Task]:
    statement = (
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.display_order, Task.id)
    )
    return list(db.scalars(statement).all())


def _build_effective_dependency_map(project_tasks: list[Task]) -> dict[int, list[int]]:
    start_task = next((task for task in project_tasks if task.node_type == "start"), None)
    task_nodes = [task for task in project_tasks if task.node_type == "task"]
    successor_map: dict[int, set[int]] = {task.id: set() for task in project_tasks}

    for task in project_tasks:
        for dependency_id in task.task_dependencies or []:
            successor_map.setdefault(dependency_id, set()).add(task.id)

    terminal_task_ids = [
        task.id for task in task_nodes if not successor_map.get(task.id)
    ]
    if not terminal_task_ids and start_task is not None:
        terminal_task_ids = [start_task.id]

    effective_dependencies: dict[int, list[int]] = {}
    for task in project_tasks:
        dependency_ids = set(task.task_dependencies or [])
        if task.node_type == "start":
            dependency_ids = set()
        elif task.node_type == "task" and not dependency_ids and start_task is not None:
            dependency_ids.add(start_task.id)
        elif task.node_type == "end":
            dependency_ids.update(terminal_task_ids)

        dependency_ids.discard(task.id)
        effective_dependencies[task.id] = sorted(dependency_ids)

    return effective_dependencies


def _load_workflow_run_for_execution_or_404(
    db: Session,
    project_id: int,
    workflow_run_id: int,
) -> WorkflowRun:
    statement = (
        select(WorkflowRun)
        .where(WorkflowRun.id == workflow_run_id)
        .options(
            selectinload(WorkflowRun.project).selectinload(Project.workspace),
            selectinload(WorkflowRun.task_runs).selectinload(TaskRun.task),
            selectinload(WorkflowRun.task_runs)
            .selectinload(TaskRun.assigned_agent)
            .selectinload(Agent.provider_model),
        )
    )
    workflow_run = db.scalar(statement)
    if workflow_run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if workflow_run.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="Workflow run does not belong to the specified project",
        )
    return workflow_run


def _priority_sort_value(priority: str | None) -> int:
    return {
        "high": 0,
        "medium": 1,
        "low": 2,
    }.get((priority or "medium").lower(), 1)


def _sort_ready_task_runs_for_queue(task_runs: list[TaskRun]) -> list[TaskRun]:
    return sorted(
        task_runs,
        key=lambda task_run: (
            _priority_sort_value(task_run.task.priority if task_run.task is not None else None),
            task_run.updated_at or task_run.created_at,
            task_run.task.display_order if task_run.task is not None else 0,
            task_run.id,
        ),
    )


def _fail_task_run_without_agent(db: Session, workflow_run: WorkflowRun, task_run: TaskRun) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    task_run.status = "failed"
    task_run.error_message = "Ready task run must have an assigned agent"
    task_run.finished_at = now
    workflow_run.status = "failed"
    workflow_run.error_message = task_run.error_message
    workflow_run.finished_at = now
    db.commit()


def _sync_workflow_run_state(db: Session, workflow_run: WorkflowRun) -> WorkflowRun:
    agent_execution_service._promote_ready_task_runs(db, workflow_run.id)
    agent_execution_service._finalize_workflow_run_if_complete(workflow_run)
    db.commit()
    return _load_workflow_run_for_execution_or_404(db, workflow_run.project_id, workflow_run.id)


def get_workflow_run_for_project_or_404(
    db: Session,
    project_id: int,
    workflow_run_id: int,
) -> WorkflowRun:
    statement = (
        select(WorkflowRun)
        .where(WorkflowRun.id == workflow_run_id)
        .options(selectinload(WorkflowRun.task_runs))
    )
    workflow_run = db.scalar(statement)
    if workflow_run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if workflow_run.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="Workflow run does not belong to the specified project",
        )
    return workflow_run


def create_workflow_run_under_project(
    db: Session,
    workspace_id: int,
    project_id: int,
    payload: WorkflowRunCreate,
) -> WorkflowRun:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    project_tasks = _list_project_tasks(db, project_id)
    dependency_map = _build_effective_dependency_map(project_tasks)
    now = datetime.now(UTC).replace(tzinfo=None)

    workflow_run = WorkflowRun(
        project_id=project_id,
        status="running",
        trigger_type=payload.trigger_type,
        input_payload=payload.input_payload,
        started_at=now,
    )
    db.add(workflow_run)
    db.flush()

    initially_completed_task_ids = {
        task.id
        for task in project_tasks
        if task.node_type == "start" and task.agent_id is None
    }
    task_runs: list[TaskRun] = []
    for task in project_tasks:
        task_run_status = "pending"
        task_run_started_at = None
        task_run_finished_at = None
        effective_dependencies = dependency_map.get(task.id, [])

        if task.node_type == "start" and task.agent_id is None:
            task_run_status = "completed"
            task_run_started_at = now
            task_run_finished_at = now
        elif all(
            dependency_id in initially_completed_task_ids
            for dependency_id in effective_dependencies
        ):
            task_run_status = "ready"

        task_runs.append(
            TaskRun(
                workflow_run_id=workflow_run.id,
                task_id=task.id,
                assigned_agent_id=task.agent_id,
                assigned_agent_name=task.agent_name,
                title_snapshot=task.title,
                node_type=task.node_type,
                status=task_run_status,
                executor_type="system",
                task_dependencies_snapshot=effective_dependencies,
                attempt_count=0,
                started_at=task_run_started_at,
                finished_at=task_run_finished_at,
            )
        )

    db.add_all(task_runs)
    db.commit()

    return get_workflow_run_for_project_or_404(db, project_id, workflow_run.id)


def execute_workflow_run(
    db: Session,
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
) -> WorkflowRun:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    workflow_run = _load_workflow_run_for_execution_or_404(db, project_id, workflow_run_id)

    if workflow_run.status == "completed":
        raise HTTPException(status_code=400, detail="Workflow run is already completed")
    if workflow_run.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cancelled workflow runs cannot be executed")

    if workflow_run.status in {"queued", "failed"}:
        workflow_run.status = "running"
        workflow_run.error_message = None
        workflow_run.finished_at = None
        db.commit()
        workflow_run = _load_workflow_run_for_execution_or_404(db, project_id, workflow_run_id)

    workflow_run = _sync_workflow_run_state(db, workflow_run)
    if workflow_run.status == "completed":
        return workflow_run

    ready_task_runs = _sort_ready_task_runs_for_queue(
        [
            task_run
            for task_run in workflow_run.task_runs
            if task_run.status == "ready"
        ]
    )
    if not ready_task_runs:
        return workflow_run

    busy_waiting = False
    for task_run in ready_task_runs:
        if task_run.assigned_agent_id is None:
            if task_run.node_type in {"start", "end"}:
                return _sync_workflow_run_state(db, workflow_run)
            _fail_task_run_without_agent(db, workflow_run, task_run)
            return _load_workflow_run_for_execution_or_404(db, project_id, workflow_run_id)

        try:
            agent_execution_service.execute_task_run(
                db,
                workspace_id,
                project_id,
                workflow_run_id,
                task_run.id,
            )
            workflow_run = _load_workflow_run_for_execution_or_404(
                db,
                project_id,
                workflow_run_id,
            )
            return _sync_workflow_run_state(db, workflow_run)
        except HTTPException as exc:
            if exc.status_code == 409:
                busy_waiting = True
                continue
            raise

    if busy_waiting:
        workflow_run.status = "queued"
        workflow_run.error_message = None
        workflow_run.finished_at = None
        db.commit()
        return _load_workflow_run_for_execution_or_404(db, project_id, workflow_run_id)

    return workflow_run


def list_workflow_runs_for_project(
    db: Session,
    workspace_id: int,
    project_id: int,
) -> list[WorkflowRun]:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    statement = (
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
    )
    return list(db.scalars(statement).all())


def get_workflow_run_detail(
    db: Session,
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
) -> WorkflowRun:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    return get_workflow_run_for_project_or_404(db, project_id, workflow_run_id)


def delete_workflow_run(
    db: Session,
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
) -> None:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    workflow_run = get_workflow_run_for_project_or_404(db, project_id, workflow_run_id)
    db.delete(workflow_run)
    db.commit()
