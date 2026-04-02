from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.provider_model import (
    ProviderModelCreate,
    ProviderModelRead,
    ProviderModelUpdate,
    ProviderModelValidationRequest,
    ProviderModelValidationResult,
)
from app.services import provider_model_service

router = APIRouter()


@router.get("/", response_model=list[ProviderModelRead])
def list_provider_models(db: Session = Depends(get_db)) -> list[ProviderModelRead]:
    return provider_model_service.list_provider_models(db)


@router.post("/validate", response_model=ProviderModelValidationResult)
def validate_provider_model(
    payload: ProviderModelValidationRequest,
    db: Session = Depends(get_db),
) -> ProviderModelValidationResult:
    return provider_model_service.validate_provider_model(db, payload)


@router.post("/", response_model=ProviderModelRead, status_code=status.HTTP_201_CREATED)
def create_provider_model(
    payload: ProviderModelCreate,
    db: Session = Depends(get_db),
) -> ProviderModelRead:
    return provider_model_service.create_provider_model(db, payload)


@router.patch("/{provider_model_id}", response_model=ProviderModelRead)
def update_provider_model(
    provider_model_id: int,
    payload: ProviderModelUpdate,
    db: Session = Depends(get_db),
) -> ProviderModelRead:
    return provider_model_service.update_provider_model(db, provider_model_id, payload)


@router.delete("/{provider_model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_model(
    provider_model_id: int,
    db: Session = Depends(get_db),
) -> Response:
    provider_model_service.delete_provider_model(db, provider_model_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
