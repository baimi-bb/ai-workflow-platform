from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.provider_model import ProviderModel
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.services.provider_model_service import get_provider_model_or_404
from app.services.workspace_service import get_workspace_or_404


def _to_agent_read(agent: Agent) -> AgentRead:
    return AgentRead(
        id=agent.id,
        workspace_id=agent.workspace_id,
        provider_model_id=agent.provider_model_id,
        provider_model_label=agent.provider_model.label,
        provider_model_name=agent.provider_model.model_name,
        provider_label=agent.provider_model.provider.label,
        provider_platform=agent.provider_model.provider.platform,
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        is_enabled=agent.is_enabled,
        max_concurrency=agent.max_concurrency,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def get_agent_for_workspace_or_404(db: Session, workspace_id: int, agent_id: int) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.workspace_id != workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Agent does not belong to the specified workspace",
        )
    return agent


def _validate_provider_model(provider_model: ProviderModel) -> None:
    if not provider_model.is_enabled:
        raise HTTPException(status_code=400, detail="Provider model must be enabled")
    if not provider_model.provider.is_enabled:
        raise HTTPException(status_code=400, detail="Provider must be enabled")


def create_agent(db: Session, workspace_id: int, payload: AgentCreate) -> AgentRead:
    get_workspace_or_404(db, workspace_id)
    provider_model = get_provider_model_or_404(db, payload.provider_model_id)
    _validate_provider_model(provider_model)

    agent = Agent(
        workspace_id=workspace_id,
        provider_model_id=provider_model.id,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        is_enabled=payload.is_enabled,
        max_concurrency=payload.max_concurrency,
    )
    agent.provider_model = provider_model
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _to_agent_read(agent)


def update_agent(
    db: Session,
    workspace_id: int,
    agent_id: int,
    payload: AgentUpdate,
) -> AgentRead:
    agent = get_agent_for_workspace_or_404(db, workspace_id, agent_id)
    updates = payload.model_dump(exclude_unset=True)

    if "provider_model_id" in updates:
        provider_model = get_provider_model_or_404(db, updates["provider_model_id"])
        _validate_provider_model(provider_model)
        agent.provider_model = provider_model
        agent.provider_model_id = provider_model.id

    for field, value in updates.items():
        if field == "provider_model_id":
            continue
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    return _to_agent_read(agent)


def delete_agent(db: Session, workspace_id: int, agent_id: int) -> None:
    agent = get_agent_for_workspace_or_404(db, workspace_id, agent_id)
    db.delete(agent)
    db.commit()


def list_agents_for_workspace(db: Session, workspace_id: int) -> list[AgentRead]:
    get_workspace_or_404(db, workspace_id)
    statement = (
        select(Agent)
        .join(ProviderModel, ProviderModel.id == Agent.provider_model_id)
        .where(Agent.workspace_id == workspace_id)
        .order_by(Agent.name, Agent.id)
    )
    agents = list(db.scalars(statement).all())
    return [_to_agent_read(agent) for agent in agents]
