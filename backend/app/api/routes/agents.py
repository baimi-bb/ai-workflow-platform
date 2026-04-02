from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.services import agent_service

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/agents",
    response_model=AgentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_agent(
    workspace_id: int,
    payload: AgentCreate,
    db: Session = Depends(get_db),
) -> AgentRead:
    return agent_service.create_agent(db, workspace_id, payload)


@router.get("/workspaces/{workspace_id}/agents", response_model=list[AgentRead])
def list_agents_for_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> list[AgentRead]:
    return agent_service.list_agents_for_workspace(db, workspace_id)


@router.patch("/workspaces/{workspace_id}/agents/{agent_id}", response_model=AgentRead)
def update_agent(
    workspace_id: int,
    agent_id: int,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
) -> AgentRead:
    return agent_service.update_agent(db, workspace_id, agent_id, payload)


@router.delete(
    "/workspaces/{workspace_id}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_agent(
    workspace_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
) -> Response:
    agent_service.delete_agent(db, workspace_id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
