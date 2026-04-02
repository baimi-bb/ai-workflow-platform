import json
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.provider import Provider
from app.models.provider_model import ProviderModel
from app.schemas.provider_model import (
    ProviderModelCreate,
    ProviderModelRead,
    ProviderModelUpdate,
    ProviderModelValidationRequest,
    ProviderModelValidationResult,
)
from app.services.provider_service import get_provider_or_404


def _to_provider_model_read(model: ProviderModel) -> ProviderModelRead:
    return ProviderModelRead(
        id=model.id,
        provider_id=model.provider_id,
        provider_label=model.provider.label,
        provider_platform=model.provider.platform,
        label=model.label,
        model_name=model.model_name,
        is_enabled=model.is_enabled,
        is_default=model.is_default,
        temperature=model.temperature,
        max_output_tokens=model.max_output_tokens,
        supports_tools=model.supports_tools,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def get_provider_model_or_404(db: Session, provider_model_id: int) -> ProviderModel:
    model = db.get(ProviderModel, provider_model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Provider model not found")
    return model


def _clear_default_models(db: Session, provider_id: int, exclude_id: int | None = None) -> None:
    statement = select(ProviderModel).where(ProviderModel.provider_id == provider_id)
    models = list(db.scalars(statement).all())
    for model in models:
        if exclude_id is not None and model.id == exclude_id:
            continue
        if model.is_default:
            model.is_default = False


def _resolve_provider_models_url(provider: Provider) -> tuple[str, dict[str, str]]:
    normalized_base_url = (provider.base_url or "").strip().rstrip("/")

    if provider.platform == "openai":
        normalized_base_url = normalized_base_url or "https://api.openai.com/v1"
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {provider.api_key}"},
        )
    if provider.platform == "deepseek":
        normalized_base_url = normalized_base_url or "https://api.deepseek.com"
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {provider.api_key}"},
        )
    if provider.platform == "openrouter":
        normalized_base_url = normalized_base_url or "https://openrouter.ai/api/v1"
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {provider.api_key}"},
        )
    if provider.platform == "anthropic":
        normalized_base_url = normalized_base_url or "https://api.anthropic.com"
        return (
            f"{normalized_base_url}/v1/models",
            {
                "x-api-key": provider.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
    if provider.platform == "google":
        normalized_base_url = normalized_base_url or "https://generativelanguage.googleapis.com"
        query_string = urllib_parse.urlencode({"key": provider.api_key})
        return (
            f"{normalized_base_url}/v1beta/models?{query_string}",
            {},
        )
    if provider.platform == "custom":
        if not normalized_base_url:
            raise HTTPException(
                status_code=400,
                detail="Custom provider model validation requires a base URL",
            )
        return (
            f"{normalized_base_url}/models",
            {"Authorization": f"Bearer {provider.api_key}"},
        )
    raise HTTPException(status_code=400, detail="Unsupported provider platform")


def _extract_candidate_model_names(item: object) -> set[str]:
    names: set[str] = set()
    if not isinstance(item, dict):
        return names

    for key in ("id", "name", "model", "slug"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            names.add(value.strip())

    google_name = item.get("name")
    if isinstance(google_name, str) and google_name.startswith("models/"):
        names.add(google_name.split("/", 1)[1])

    return names


def _extract_available_model_names(payload: object) -> set[str]:
    names: set[str] = set()
    if isinstance(payload, dict):
        data_items = payload.get("data")
        if isinstance(data_items, list):
            for item in data_items:
                names.update(_extract_candidate_model_names(item))
        models_items = payload.get("models")
        if isinstance(models_items, list):
            for item in models_items:
                names.update(_extract_candidate_model_names(item))
    elif isinstance(payload, list):
        for item in payload:
            names.update(_extract_candidate_model_names(item))
    return names


def validate_provider_model(
    db: Session,
    payload: ProviderModelValidationRequest,
) -> ProviderModelValidationResult:
    provider = get_provider_or_404(db, payload.provider_id)
    request_url, headers = _resolve_provider_models_url(provider)
    request = urllib_request.Request(
        request_url,
        headers={
            "Accept": "application/json",
            **headers,
        },
        method="GET",
    )

    try:
        with urllib_request.urlopen(request, timeout=10) as response:
            raw_payload = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        if exc.code in {401, 403}:
            message = "Provider rejected model validation request: API key is invalid or unauthorized"
        elif exc.code == 404:
            message = "Provider model validation endpoint was not found"
        else:
            message = f"Provider model validation failed with HTTP {exc.code}"
        return ProviderModelValidationResult(
            is_valid=False,
            message=message,
            resolved_model_name=None,
        )
    except urllib_error.URLError as exc:
        return ProviderModelValidationResult(
            is_valid=False,
            message=f"Provider model validation failed: {exc.reason}",
            resolved_model_name=None,
        )

    available_names = _extract_available_model_names(raw_payload)
    if payload.model_name in available_names:
        return ProviderModelValidationResult(
            is_valid=True,
            message="Model is available for this provider",
            resolved_model_name=payload.model_name,
        )

    lowered_target = payload.model_name.casefold()
    casefold_map = {name.casefold(): name for name in available_names}
    if lowered_target in casefold_map:
        return ProviderModelValidationResult(
            is_valid=True,
            message="Model is available for this provider",
            resolved_model_name=casefold_map[lowered_target],
        )

    return ProviderModelValidationResult(
        is_valid=False,
        message=(
            f"Model `{payload.model_name}` is not available for provider `{provider.label}`"
        ),
        resolved_model_name=None,
    )


def _ensure_provider_model_is_available(
    db: Session,
    provider: Provider,
    model_name: str,
) -> None:
    result = validate_provider_model(
        db,
        ProviderModelValidationRequest(provider_id=provider.id, model_name=model_name),
    )
    if not result.is_valid:
        raise HTTPException(status_code=400, detail=result.message)


def create_provider_model(db: Session, payload: ProviderModelCreate) -> ProviderModelRead:
    provider = get_provider_or_404(db, payload.provider_id)
    _ensure_provider_model_is_available(db, provider, payload.model_name)
    if payload.is_default:
        _clear_default_models(db, provider.id)

    model = ProviderModel(
        provider_id=provider.id,
        label=payload.label,
        model_name=payload.model_name,
        is_enabled=payload.is_enabled,
        is_default=payload.is_default,
        temperature=payload.temperature,
        max_output_tokens=payload.max_output_tokens,
        supports_tools=payload.supports_tools,
    )
    model.provider = provider
    db.add(model)
    db.commit()
    db.refresh(model)
    return _to_provider_model_read(model)


def update_provider_model(
    db: Session,
    provider_model_id: int,
    payload: ProviderModelUpdate,
) -> ProviderModelRead:
    model = get_provider_model_or_404(db, provider_model_id)
    updates = payload.model_dump(exclude_unset=True)
    if "model_name" in updates and isinstance(updates["model_name"], str):
        _ensure_provider_model_is_available(db, model.provider, updates["model_name"])

    if updates.get("is_default") is True:
        _clear_default_models(db, model.provider_id, exclude_id=model.id)

    for field, value in updates.items():
        setattr(model, field, value)
    db.commit()
    db.refresh(model)
    return _to_provider_model_read(model)


def delete_provider_model(db: Session, provider_model_id: int) -> None:
    model = get_provider_model_or_404(db, provider_model_id)
    statement = (
        select(Agent.id)
        .where(Agent.provider_model_id == provider_model_id)
        .limit(1)
    )
    if db.scalar(statement) is not None:
        raise HTTPException(
            status_code=409,
            detail="Provider model is still used by one or more agents",
        )
    db.delete(model)
    db.commit()


def list_provider_models(db: Session) -> list[ProviderModelRead]:
    statement = (
        select(ProviderModel)
        .join(Provider, Provider.id == ProviderModel.provider_id)
        .order_by(Provider.label, ProviderModel.label, ProviderModel.id)
    )
    models = list(db.scalars(statement).all())
    return [_to_provider_model_read(model) for model in models]
