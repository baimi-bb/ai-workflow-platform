from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskStatusUpdate, TaskUpdate
from app.services.project_service import get_project_for_workspace_or_404


BLOCKED_STATUSES = {"in_progress", "done"}


def get_task_for_project_or_404(
    db: Session,
    project_id: int,
    task_id: int,
) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="Task does not belong to the specified project",
        )
    return task


def _list_project_tasks(db: Session, project_id: int) -> list[Task]:
    statement = (
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.display_order, Task.id)
    )
    return list(db.scalars(statement).all())


def _validate_task_dependencies(
    *,
    project_tasks: list[Task],
    task_dependencies: list[int],
    task_id: int | None = None,
) -> None:
    if task_id is not None and task_id in task_dependencies:
        raise HTTPException(status_code=400, detail="Task cannot depend on itself")

    task_ids = {task.id for task in project_tasks}
    missing_ids = [
        dependency_id
        for dependency_id in task_dependencies
        if dependency_id not in task_ids
    ]
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Task dependencies not found in project: {missing_ids}",
        )

    if task_id is None:
        return

    dependency_graph = {
        task.id: list(task.task_dependencies or []) for task in project_tasks
    }
    dependency_graph[task_id] = task_dependencies

    def has_path(current_id: int, target_id: int, visited: set[int]) -> bool:
        if current_id == target_id:
            return True
        if current_id in visited:
            return False
        visited.add(current_id)
        return any(
            has_path(next_id, target_id, visited)
            for next_id in dependency_graph.get(current_id, [])
        )

    for dependency_id in task_dependencies:
        if has_path(dependency_id, task_id, set()):
            raise HTTPException(
                status_code=400,
                detail="Task dependencies cannot contain cycles",
            )


def _ensure_dependencies_satisfied(
    *,
    project_tasks: list[Task],
    task_dependencies: list[int],
) -> None:
    task_map = {task.id: task for task in project_tasks}
    blocked_dependency_ids = [
        dependency_id
        for dependency_id in task_dependencies
        if task_map[dependency_id].status != "done"
    ]
    if blocked_dependency_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Task cannot enter this status until dependencies are done: "
                f"{blocked_dependency_ids}"
            ),
        )


def _validate_task_agent(
    *,
    db: Session,
    workspace_id: int,
    agent_id: int | None,
) -> None:
    if agent_id is None:
        return

    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=400, detail="Assigned agent not found")
    if agent.workspace_id != workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Assigned agent must belong to the same workspace",
        )
    if not agent.is_enabled:
        raise HTTPException(status_code=400, detail="Assigned agent must be enabled")


def create_task_under_project(
    db: Session,
    workspace_id: int,
    project_id: int,
    payload: TaskCreate,
) -> Task:
    agent_id = getattr(payload, "agent_id", None)
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    project_tasks = _list_project_tasks(db, project_id)
    _validate_task_dependencies(
        project_tasks=project_tasks,
        task_dependencies=payload.task_dependencies,
    )
    _validate_task_agent(db=db, workspace_id=workspace_id, agent_id=agent_id)

    if payload.status in BLOCKED_STATUSES:
        _ensure_dependencies_satisfied(
            project_tasks=project_tasks,
            task_dependencies=payload.task_dependencies,
        )

    if payload.node_type in {"start", "end"}:
        raise HTTPException(
            status_code=400,
            detail=f"{payload.node_type.capitalize()} node is created automatically",
        )

    next_display_order = (
        payload.display_order
        if payload.display_order is not None
        else max((task.display_order for task in project_tasks), default=0) + 1
    )
    default_x = 420 + max(next_display_order - 1, 0) * 160
    default_y = 120 + max(next_display_order - 1, 0) * 36

    task = Task(
        project_id=project_id,
        agent_id=agent_id,
        title=payload.title,
        description=payload.description,
        node_type=payload.node_type,
        status=payload.status,
        priority=payload.priority,
        display_order=next_display_order,
        canvas_x=payload.canvas_x if payload.canvas_x is not None else default_x,
        canvas_y=payload.canvas_y if payload.canvas_y is not None else default_y,
        task_dependencies=payload.task_dependencies,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task_status(
    db: Session,
    workspace_id: int,
    project_id: int,
    task_id: int,
    payload: TaskStatusUpdate,
) -> Task:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    task = get_task_for_project_or_404(db, project_id, task_id)
    project_tasks = _list_project_tasks(db, project_id)

    if payload.status in BLOCKED_STATUSES:
        _ensure_dependencies_satisfied(
            project_tasks=project_tasks,
            task_dependencies=task.task_dependencies or [],
        )

    task.status = payload.status
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    workspace_id: int,
    project_id: int,
    task_id: int,
    payload: TaskUpdate,
) -> Task:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    task = get_task_for_project_or_404(db, project_id, task_id)
    updates = payload.model_dump(exclude_unset=True)
    project_tasks = _list_project_tasks(db, project_id)
    next_dependencies = updates.get("task_dependencies", task.task_dependencies or [])
    next_agent_id = updates["agent_id"] if "agent_id" in updates else task.agent_id
    _validate_task_dependencies(
        project_tasks=project_tasks,
        task_dependencies=next_dependencies,
        task_id=task.id,
    )
    _validate_task_agent(db=db, workspace_id=workspace_id, agent_id=next_agent_id)

    next_status = updates.get("status", task.status)
    if next_status in BLOCKED_STATUSES:
        _ensure_dependencies_satisfied(
            project_tasks=project_tasks,
            task_dependencies=next_dependencies,
        )

    if task.node_type == "start":
        if "task_dependencies" in updates and next_dependencies:
            raise HTTPException(
                status_code=400,
                detail="Start node cannot depend on other tasks",
            )
        if updates.get("status") == "todo":
            raise HTTPException(
                status_code=400,
                detail="Start node cannot be moved back to todo",
            )

    for field, value in updates.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, workspace_id: int, project_id: int, task_id: int) -> None:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    task = get_task_for_project_or_404(db, project_id, task_id)
    if task.node_type in {"start", "end"}:
        raise HTTPException(
            status_code=400,
            detail=f"{task.node_type.capitalize()} node cannot be deleted",
        )
    project_tasks = _list_project_tasks(db, project_id)
    blocked_task_ids = [
        project_task.id
        for project_task in project_tasks
        if task_id in (project_task.task_dependencies or [])
    ]
    if blocked_task_ids:
        raise HTTPException(
            status_code=409,
            detail=f"Task is still required by tasks: {blocked_task_ids}",
        )
    db.delete(task)
    db.commit()


def list_tasks_for_project(
    db: Session,
    workspace_id: int,
    project_id: int,
) -> list[Task]:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    return _list_project_tasks(db, project_id)
