from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.provider import (
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    ProviderValidationRequest,
    ProviderValidationResult,
)
from app.services import provider_service

router = APIRouter()


@router.get("/", response_model=list[ProviderRead])
def list_providers(db: Session = Depends(get_db)) -> list[ProviderRead]:
    return provider_service.list_providers(db)


@router.post("/", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
def create_provider(
    payload: ProviderCreate,
    db: Session = Depends(get_db),
) -> ProviderRead:
    return provider_service.create_provider(db, payload)


@router.post("/validate", response_model=ProviderValidationResult)
def validate_provider(
    payload: ProviderValidationRequest,
) -> ProviderValidationResult:
    return provider_service.validate_provider_credentials(payload)


@router.patch("/{provider_id}", response_model=ProviderRead)
def update_provider(
    provider_id: int,
    payload: ProviderUpdate,
    db: Session = Depends(get_db),
) -> ProviderRead:
    return provider_service.update_provider(db, provider_id, payload)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
) -> Response:
    provider_service.delete_provider(db, provider_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
