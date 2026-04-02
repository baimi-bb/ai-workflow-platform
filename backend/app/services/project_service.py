from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.project import Project
from app.models.task import Task
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.workspace_service import get_workspace_or_404


def get_project_for_workspace_or_404(
    db: Session,
    workspace_id: int,
    project_id: int,
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.workspace_id != workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Project does not belong to the specified workspace",
        )
    return project


def create_project_under_workspace(
    db: Session,
    workspace_id: int,
    payload: ProjectCreate,
) -> Project:
    get_workspace_or_404(db, workspace_id)

    project = Project(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    start_task = Task(
        project_id=project.id,
        title="Start",
        description="Default start node",
        node_type="start",
        status="done",
        priority="low",
        display_order=0,
        canvas_x=40,
        canvas_y=120,
        task_dependencies=[],
    )
    db.add(start_task)
    db.commit()

    end_task = Task(
        project_id=project.id,
        title="End",
        description="Default end node",
        node_type="end",
        status="todo",
        priority="low",
        display_order=1,
        canvas_x=1160,
        canvas_y=120,
        task_dependencies=[],
    )
    db.add(end_task)
    db.commit()

    return project


def update_project(
    db: Session,
    workspace_id: int,
    project_id: int,
    payload: ProjectUpdate,
) -> Project:
    project = get_project_for_workspace_or_404(db, workspace_id, project_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, workspace_id: int, project_id: int) -> None:
    project = get_project_for_workspace_or_404(db, workspace_id, project_id)
    db.delete(project)
    db.commit()


def list_projects_for_workspace(db: Session, workspace_id: int) -> list[Project]:
    get_workspace_or_404(db, workspace_id)

    statement = (
        select(Project)
        .where(Project.workspace_id == workspace_id)
        .options(selectinload(Project.tasks).selectinload(Task.agent))
        .order_by(Project.id)
    )
    return list(db.scalars(statement).unique().all())
