from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str
    type: str | None = None
    input: Any | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
