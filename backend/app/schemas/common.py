from typing import Annotated

from pydantic import BeforeValidator, field_validator


def _normalize_optional_text(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    normalized = value.strip()
    return normalized or None


NonEmptyShortText = Annotated[str, BeforeValidator(lambda value: value.strip() if isinstance(value, str) else value)]
OptionalTrimmedText = Annotated[str | None, BeforeValidator(_normalize_optional_text)]


class TrimmedTextModelMixin:
    @field_validator("name", "title", mode="after", check_fields=False)
    @classmethod
    def _reject_blank_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("This field cannot be blank")
        return value
