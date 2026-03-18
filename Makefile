# Mission Control — Development Commands
# Usage: make <target>

.PHONY: setup dev stop restart status logs test test-backend test-dashboard build clean migrate seed

# ─── Setup & Lifecycle ──────────────────────────

setup: ## Interactive setup wizard
	@./setup.sh

dev: ## Start all services (docker compose)
	docker compose up -d

stop: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

status: ## Show service status
	docker compose ps

logs: ## Tail logs from all services
	docker compose logs -f --tail=50

logs-backend: ## Tail backend logs only
	docker compose logs -f --tail=50 backend

logs-dashboard: ## Tail dashboard logs only
	docker compose logs -f --tail=50 dashboard

# ─── Development ────────────────────────────────

backend-dev: ## Run backend in dev mode (local, no Docker)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dashboard-dev: ## Run dashboard in dev mode (local, no Docker)
	cd dashboard && npm run dev

# ─── Testing ────────────────────────────────────

test: test-backend ## Run all tests

test-backend: ## Run backend tests
	cd backend && python -m pytest tests/ -v

test-dashboard: ## Run dashboard tests
	cd dashboard && npx vitest run

# ─── Database ───────────────────────────────────

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migration: ## Create a new migration (usage: make migration MSG="description")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed database with sample data
	cd backend && python -m app.db.seed

# ─── Build & Clean ──────────────────────────────

build: ## Build all Docker images
	docker compose build

build-backend: ## Build backend image only
	docker compose build backend

build-dashboard: ## Build dashboard image only
	docker compose build dashboard

clean: ## Remove containers, volumes, and build artifacts
	docker compose down -v
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf dashboard/.next dashboard/node_modules/.cache

# ─── Utilities ──────────────────────────────────

sync-skills: ## Reload agent skills from YAML files
	curl -s -X POST http://localhost:$${API_PORT:-8000}/api/agents/sync-skills | python -m json.tool

health: ## Check backend health
	@curl -sf http://localhost:$${API_PORT:-8000}/api/health | python -m json.tool || echo "Backend is not running"

shell-db: ## Open psql shell
	docker compose exec db psql -U $${POSTGRES_USER:-missionctl} -d $${POSTGRES_DB:-missioncontrol}

shell-backend: ## Open bash shell in backend container
	docker compose exec backend bash

# ─── Help ───────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
