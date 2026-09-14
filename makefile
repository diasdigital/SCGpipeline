# Makefile — SCGpipeline command shortcuts
# =========================================
# Requirement: make (install via choco: choco install make)
#
# Available commands:
#   make start          <- Start all services
#   make start-no-mlf   <- Start without MLflow
#   make stop           <- Stop all services
#   make redis-up       <- Start Redis only
#   make redis-down     <- Stop Redis only
#   make logs           <- Tail application log file
#   make backend        <- Start backend only
#   make celery         <- Start Celery only
#   make frontend       <- Start frontend only
#   make install        <- Install all dependencies
#   make docker-up      <- Run full stack via Docker (see README)
#   make docker-down    <- Stop full Docker stack
#   make docker-logs    <- Tail backend + celery-worker logs from Docker

.PHONY: start start-no-mlf stop redis-up redis-down \
        logs logs-celery backend celery frontend mlflow install \
        docker-up docker-down docker-logs docker-rebuild

# ─── Start all services ──────────────────────────────────────────────────────
start:
	powershell -ExecutionPolicy Bypass -File .\start.ps1

start-no-mlf:
	powershell -ExecutionPolicy Bypass -File .\start.ps1 -NoMLflow

# ─── Stop all services ───────────────────────────────────────────────────────
stop:
	powershell -ExecutionPolicy Bypass -File .\stop.ps1

# ─── Redis ───────────────────────────────────────────────────────────────────
redis-up:
	docker compose up -d redis

redis-down:
	docker compose stop redis

# ─── Run individual services ─────────────────────────────────────────────────
backend:
	uv run uvicorn app.main:app --reload

celery:
	uv run celery -A app.services.detection_task.celery_app worker --loglevel=info --pool=solo

frontend:
	cd frontend && npm run dev

mlflow:
	uv run mlflow ui --port 5000

# ─── Monitoring ──────────────────────────────────────────────────────────────
logs:
	powershell -Command "Get-Content logs\app.log -Wait -Tail 50"

logs-celery:
	powershell -Command "Get-Content logs\celery_task.log -Wait -Tail 50"

# ─── Install dependencies ────────────────────────────────────────────────────
install:
	uv sync
	cd frontend && npm install

# ─── Docker (alternative execution without manual setup) ──────────────────
docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend celery-worker

docker-rebuild:
	docker compose up -d --build --force-recreate