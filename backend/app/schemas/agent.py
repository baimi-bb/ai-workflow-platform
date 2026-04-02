from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import OptionalTrimmedText, TrimmedTextModelMixin


AgentName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
AgentDescription = Annotated[
    OptionalTrimmedText,
    StringConstraints(max_length=1000),
]
AgentSystemPrompt = Annotated[
    OptionalTrimmedText,
    StringConstraints(max_length=12000),
]


class AgentCreate(TrimmedTextModelMixin, BaseModel):
    provider_model_id: int
    name: AgentName
    description: AgentDescription = None
    system_prompt: AgentSystemPrompt = None
    is_enabled: bool = True
    max_concurrency: int = Field(default=1, ge=1, le=1)


class AgentUpdate(TrimmedTextModelMixin, BaseModel):
    provider_model_id: int | None = None
    name: AgentName | None = None
    description: AgentDescription = None
    system_prompt: AgentSystemPrompt = None
    is_enabled: bool | None = None
    max_concurrency: int | None = Field(default=None, ge=1, le=1)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    provider_model_id: int
    provider_model_label: str
    provider_model_name: str
    provider_label: str
    provider_platform: str
    name: str
    description: str | None
    system_prompt: str | None
    is_enabled: bool
    max_concurrency: int
    created_at: datetime
    updated_at: datetime
