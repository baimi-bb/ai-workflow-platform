from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.common import OptionalTrimmedText, TrimmedTextModelMixin


ProviderPlatform = Literal[
    "openai",
    "anthropic",
    "google",
    "deepseek",
    "openrouter",
    "custom",
]
ProviderLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ProviderApiKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
ProviderBaseUrl = Annotated[
    OptionalTrimmedText,
    StringConstraints(max_length=500),
]


class ProviderCreate(TrimmedTextModelMixin, BaseModel):
    platform: ProviderPlatform
    label: ProviderLabel
    api_key: ProviderApiKey
    base_url: ProviderBaseUrl = None
    is_enabled: bool = True


class ProviderUpdate(TrimmedTextModelMixin, BaseModel):
    label: ProviderLabel | None = None
    api_key: ProviderApiKey | None = None
    base_url: ProviderBaseUrl = None
    is_enabled: bool | None = None


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: ProviderPlatform
    label: str
    api_key_preview: str
    base_url: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class ProviderValidationRequest(TrimmedTextModelMixin, BaseModel):
    platform: ProviderPlatform
    api_key: ProviderApiKey
    base_url: ProviderBaseUrl = None


class ProviderValidationResult(BaseModel):
    is_valid: bool
    message: str
    resolved_base_url: str | None = None
