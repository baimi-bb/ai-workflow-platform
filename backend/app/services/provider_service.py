from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.provider import Provider
from app.schemas.provider import (
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    ProviderValidationRequest,
    ProviderValidationResult,
)


def _mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def _to_provider_read(provider: Provider) -> ProviderRead:
    return ProviderRead(
        id=provider.id,
        platform=provider.platform,
        label=provider.label,
        api_key_preview=_mask_api_key(provider.api_key),
        base_url=provider.base_url,
        is_enabled=provider.is_enabled,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _resolve_validation_url(platform: str, base_url: str | None, api_key: str) -> tuple[str, dict[str, str]]:
    normalized_base_url = (base_url or "").strip().rstrip("/")

    if platform == "openai":
        normalized_base_url = normalized_base_url or "https://api.openai.com/v1"
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {api_key}"},
        )

    if platform == "deepseek":
        normalized_base_url = normalized_base_url or "https://api.deepseek.com"
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {api_key}"},
        )

    if platform == "openrouter":
        normalized_base_url = normalized_base_url or "https://openrouter.ai/api/v1"
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {api_key}"},
        )

    if platform == "anthropic":
        normalized_base_url = normalized_base_url or "https://api.anthropic.com"
        return (
            f"{normalized_base_url}/v1/models",
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )

    if platform == "google":
        normalized_base_url = normalized_base_url or "https://generativelanguage.googleapis.com"
        query_string = urllib_parse.urlencode({"key": api_key})
        return (f"{normalized_base_url}/v1beta/models?{query_string}", {})

    if platform == "custom":
        if not normalized_base_url:
            raise HTTPException(
                status_code=400,
                detail="Custom provider validation requires a base URL",
            )
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {api_key}"},
        )

    raise HTTPException(status_code=400, detail="Unsupported provider platform")


def validate_provider_credentials(
    payload: ProviderValidationRequest,
) -> ProviderValidationResult:
    validation_url, headers = _resolve_validation_url(
        payload.platform,
        payload.base_url,
        payload.api_key,
    )
    request = urllib_request.Request(
        validation_url,
        headers={
            "Accept": "application/json",
            **headers,
        },
        method="GET",
    )

    try:
        with urllib_request.urlopen(request, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                return ProviderValidationResult(
                    is_valid=True,
                    message="API credentials look valid",
                    resolved_base_url=validation_url.rsplit("/", 1)[0],
                )
    except urllib_error.HTTPError as exc:
        message = "Provider API validation failed"
        if exc.code in {401, 403}:
            message = "API key is invalid or unauthorized"
        elif exc.code == 404:
            message = "Provider base URL is reachable but the validation endpoint was not found"
        return ProviderValidationResult(
            is_valid=False,
            message=f"{message} (HTTP {exc.code})",
            resolved_base_url=validation_url.rsplit("/", 1)[0],
        )
    except urllib_error.URLError as exc:
        return ProviderValidationResult(
            is_valid=False,
            message=f"Provider API validation failed: {exc.reason}",
            resolved_base_url=validation_url.rsplit("/", 1)[0],
        )

    return ProviderValidationResult(
        is_valid=False,
        message="Provider API validation returned an unexpected response",
        resolved_base_url=validation_url.rsplit("/", 1)[0],
    )


def get_provider_or_404(db: Session, provider_id: int) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


def create_provider(db: Session, payload: ProviderCreate) -> ProviderRead:
    provider = Provider(
        platform=payload.platform,
        label=payload.label,
        api_key=payload.api_key,
        base_url=payload.base_url,
        is_enabled=payload.is_enabled,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return _to_provider_read(provider)


def update_provider(
    db: Session,
    provider_id: int,
    payload: ProviderUpdate,
) -> ProviderRead:
    provider = get_provider_or_404(db, provider_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(provider, field, value)
    db.commit()
    db.refresh(provider)
    return _to_provider_read(provider)


def delete_provider(db: Session, provider_id: int) -> None:
    provider = get_provider_or_404(db, provider_id)
    db.delete(provider)
    db.commit()


def list_providers(db: Session) -> list[ProviderRead]:
    statement = select(Provider).order_by(Provider.platform, Provider.label, Provider.id)
    providers = list(db.scalars(statement).all())
    return [_to_provider_read(provider) for provider in providers]
