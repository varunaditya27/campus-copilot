# Everyday commands. `make help` lists them.
COMPOSE      = docker compose
COMPOSE_DEV  = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.DEFAULT_GOAL := help
.PHONY: help dev build up down logs test test-backend test-frontend coverage lint ingest migrate create-admin clean

help:  ## Show this list
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

dev:  ## Start everything with hot reload (backend and frontend reload when files change)
	$(COMPOSE_DEV) up --build

build:  ## Build the backend and frontend images
	$(COMPOSE) build

up:  ## Start the production-style stack in the background
	$(COMPOSE) up -d --build

down:  ## Stop the stack (data is kept)
	$(COMPOSE) down

logs:  ## Follow the logs
	$(COMPOSE) logs -f --tail=100

test: test-backend test-frontend  ## Run all the tests

test-backend:  ## Backend tests, on this machine (needs backend/venv)
	cd backend && ./venv/bin/pytest -q

test-frontend:  ## Type-check, lint and run the component tests of the frontend, on this machine
	cd frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint app lib && ./node_modules/.bin/vitest run

coverage:  ## Backend tests with a coverage report
	cd backend && ./venv/bin/pytest -q --cov=app --cov-report=term-missing:skip-covered

lint:  ## Type-check and lint the frontend
	cd frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint app lib

ingest:  ## Build or update the knowledge base in the running backend (add FULL=1 to rebuild everything)
	$(COMPOSE) exec backend python -m app.rag.ingest $(if $(FULL),--full,)

migrate:  ## Apply database migrations in the running backend
	$(COMPOSE) exec backend alembic upgrade head

create-admin:  ## Create an administrator account in the running backend
	$(COMPOSE) exec backend python -m app.cli create-user --role admin

clean:  ## Stop the stack AND delete its data volumes (asks first)
	@read -p "Delete all data volumes for this project? [y/N] " answer && [ "$$answer" = "y" ] && $(COMPOSE) down -v
