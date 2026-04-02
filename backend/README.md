# Backend

FastAPI backend for the AI Workflow Platform.

## Quick start

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

## Database migrations

Alembic is configured under `backend/alembic/` with an initial baseline migration.

Common commands:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
alembic upgrade head
```

Create a new migration after model changes:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "describe_your_change"
```

Rollback one revision:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
alembic downgrade -1
```

## Environment variables

Add the following values to the project root `.env` file:

```env
BACKEND_APP_NAME=AI Workflow Platform API
BACKEND_APP_VERSION=0.1.0
BACKEND_API_PREFIX=/api/v1
BACKEND_DEBUG=true
BACKEND_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ai_workflow_platform
```

## Endpoints

- `GET /`
- `GET /api/v1/health/`
- `GET /docs`
