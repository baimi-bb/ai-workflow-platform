from datetime import datetime
import os
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.agent import Agent
from app.models.project import Project
from app.models.provider_model import ProviderModel
from app.models.task import Task
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceFileListRead, WorkspaceUpdate


def _normalize_workspace_root_path(root_path: str) -> str:
    normalized_path = Path(root_path).expanduser().resolve()

    if not normalized_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Workspace root path does not exist",
        )
    if not normalized_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Workspace root path must be a directory",
        )
    if not os.access(normalized_path, os.R_OK):
        raise HTTPException(
            status_code=400,
            detail="Workspace root path must be readable",
        )
    if not os.access(normalized_path, os.W_OK):
        raise HTTPException(
            status_code=400,
            detail="Workspace root path must be writable",
        )

    return str(normalized_path)


def get_workspace_or_404(db: Session, workspace_id: int) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def create_workspace(db: Session, payload: WorkspaceCreate) -> Workspace:
    workspace = Workspace(
        name=payload.name,
        description=payload.description,
        root_path=_normalize_workspace_root_path(payload.root_path),
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def update_workspace(
    db: Session,
    workspace_id: int,
    payload: WorkspaceUpdate,
) -> Workspace:
    workspace = get_workspace_or_404(db, workspace_id)
    updates = payload.model_dump(exclude_unset=True)
    if "root_path" in updates and updates["root_path"] is not None:
        updates["root_path"] = _normalize_workspace_root_path(updates["root_path"])
    for field, value in updates.items():
        setattr(workspace, field, value)
    db.commit()
    db.refresh(workspace)
    return workspace


def delete_workspace(db: Session, workspace_id: int) -> None:
    workspace = get_workspace_or_404(db, workspace_id)
    db.delete(workspace)
    db.commit()


def list_workspaces(db: Session) -> list[Workspace]:
    statement = (
        select(Workspace)
        .options(
            selectinload(Workspace.projects).selectinload(Project.tasks).selectinload(Task.agent),
            selectinload(Workspace.agents)
            .selectinload(Agent.provider_model)
            .selectinload(ProviderModel.provider),
        )
        .order_by(Workspace.id)
    )
    return list(db.scalars(statement).unique().all())


def get_workspace_with_projects_or_404(db: Session, workspace_id: int) -> Workspace:
    statement = (
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(
            selectinload(Workspace.projects).selectinload(Project.tasks).selectinload(Task.agent),
            selectinload(Workspace.agents)
            .selectinload(Agent.provider_model)
            .selectinload(ProviderModel.provider),
        )
    )
    workspace = db.scalar(statement)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def list_workspace_files(
    db: Session,
    workspace_id: int,
    relative_path: str = "",
) -> WorkspaceFileListRead:
    workspace = get_workspace_or_404(db, workspace_id)
    if not workspace.root_path:
        raise HTTPException(status_code=400, detail="Workspace root path is not configured")

    normalized_root_path = Path(_normalize_workspace_root_path(workspace.root_path))
    requested_path = (relative_path or "").strip().replace("\\", "/").strip("/")
    target_path = normalized_root_path / requested_path if requested_path else normalized_root_path

    try:
        normalized_target_path = target_path.resolve()
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workspace file path: {exc}",
        ) from exc

    try:
        normalized_target_path.relative_to(normalized_root_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Requested path must stay within the workspace root path",
        ) from exc

    if not normalized_target_path.exists():
        raise HTTPException(status_code=404, detail="Workspace path not found")
    if not normalized_target_path.is_dir():
        raise HTTPException(status_code=400, detail="Requested workspace path must be a directory")

    entries = []
    try:
        for entry in normalized_target_path.iterdir():
            stat_result = entry.stat()
            entries.append(
                {
                    "name": entry.name,
                    "relative_path": entry.relative_to(normalized_root_path).as_posix(),
                    "entry_type": "directory" if entry.is_dir() else "file",
                    "size": None if entry.is_dir() else stat_result.st_size,
                    "modified_at": datetime.fromtimestamp(stat_result.st_mtime),
                }
            )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read workspace files: {exc}",
        ) from exc

    entries.sort(
        key=lambda item: (
            0 if item["entry_type"] == "directory" else 1,
            item["name"].lower(),
        )
    )

    return WorkspaceFileListRead(
        workspace_id=workspace.id,
        root_path=str(normalized_root_path),
        current_path="" if normalized_target_path == normalized_root_path else normalized_target_path.relative_to(normalized_root_path).as_posix(),
        entries=entries,
    )
