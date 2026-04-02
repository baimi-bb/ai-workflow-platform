from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env", override=False)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    app_name: str = "AI Workflow Platform API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    debug: bool = False
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/ai_workflow_platform"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    agent_web_enabled: bool = True
    agent_web_max_iterations: int = 3
    agent_web_search_max_results: int = 5
    agent_web_fetch_max_chars: int = 12000
    agent_task_auto_retry_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("BACKEND_APP_NAME", "AI Workflow Platform API"),
        app_version=os.getenv("BACKEND_APP_VERSION", "0.1.0"),
        api_prefix=os.getenv("BACKEND_API_PREFIX", "/api/v1"),
        debug=_parse_bool(os.getenv("BACKEND_DEBUG"), default=False),
        database_url=os.getenv(
            "BACKEND_DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/ai_workflow_platform",
        ),
        agent_web_enabled=_parse_bool(os.getenv("BACKEND_AGENT_WEB_ENABLED"), default=True),
        agent_web_max_iterations=max(
            1,
            int(os.getenv("BACKEND_AGENT_WEB_MAX_ITERATIONS", "3")),
        ),
        agent_web_search_max_results=max(
            1,
            int(os.getenv("BACKEND_AGENT_WEB_SEARCH_MAX_RESULTS", "5")),
        ),
        agent_web_fetch_max_chars=max(
            1000,
            int(os.getenv("BACKEND_AGENT_WEB_FETCH_MAX_CHARS", "12000")),
        ),
        agent_task_auto_retry_attempts=max(
            1,
            int(os.getenv("BACKEND_AGENT_TASK_AUTO_RETRY_ATTEMPTS", "3")),
        ),
    )


settings = get_settings()
