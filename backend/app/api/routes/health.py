from fastapi import APIRouter

from app.db.session import check_database_connection
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    database_connected = check_database_connection()
    return HealthResponse(
        status="ok" if database_connected else "degraded",
        database="connected" if database_connected else "disconnected",
    )
