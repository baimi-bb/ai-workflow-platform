from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import TrimmedTextModelMixin


ModelLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ModelName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class ProviderModelCreate(TrimmedTextModelMixin, BaseModel):
    provider_id: int
    label: ModelLabel
    model_name: ModelName
    is_enabled: bool = True
    is_default: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)
    supports_tools: bool = False


class ProviderModelUpdate(TrimmedTextModelMixin, BaseModel):
    label: ModelLabel | None = None
    model_name: ModelName | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)
    supports_tools: bool | None = None


class ProviderModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    provider_label: str
    provider_platform: str
    label: str
    model_name: str
    is_enabled: bool
    is_default: bool
    temperature: float | None
    max_output_tokens: int | None
    supports_tools: bool
    created_at: datetime
    updated_at: datetime


class ProviderModelValidationRequest(TrimmedTextModelMixin, BaseModel):
    provider_id: int
    model_name: ModelName


class ProviderModelValidationResult(BaseModel):
    is_valid: bool
    message: str
    resolved_model_name: str | None = None
