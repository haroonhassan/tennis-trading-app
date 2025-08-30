.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend format clean build

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend dependencies
	cd backend && python -m venv venv && \
	. venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

dev: ## Run both backend and frontend in development mode
	@echo "Starting development servers..."
	@make -j 2 dev-backend dev-frontend

dev-backend: ## Run backend in development mode
	cd backend && \
	. venv/bin/activate && \
	uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run frontend in development mode
	cd frontend && npm start

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && \
	. venv/bin/activate && \
	pytest -v --cov=app

test-frontend: ## Run frontend tests
	cd frontend && npm test -- --watchAll=false

lint: lint-backend lint-frontend ## Lint all code

lint-backend: ## Lint backend code
	cd backend && \
	. venv/bin/activate && \
	flake8 app tests && \
	mypy app

lint-frontend: ## Lint frontend code
	cd frontend && npm run lint

format: format-backend format-frontend ## Format all code

format-backend: ## Format backend code
	cd backend && \
	. venv/bin/activate && \
	black app tests && \
	isort app tests

format-frontend: ## Format frontend code
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,js,jsx,css}"

clean: ## Clean build artifacts and cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete

build: build-backend build-frontend ## Build for production

build-backend: ## Build backend for production
	cd backend && \
	. venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt

build-frontend: ## Build frontend for production
	cd frontend && npm run build

redis: ## Start Redis server
	redis-server

setup-env: ## Copy environment files
	cp backend/.env.example backend/.env
	cp frontend/.env.example frontend/.env.local
	@echo "Environment files created. Please edit them with your configuration."

db-upgrade: ## Run database migrations
	cd backend && \
	. venv/bin/activate && \
	alembic upgrade head

db-downgrade: ## Rollback database migration
	cd backend && \
	. venv/bin/activate && \
	alembic downgrade -1

db-history: ## Show migration history
	cd backend && \
	. venv/bin/activate && \
	alembic history

check: lint test ## Run linting and tests

serve-docs: ## Serve documentation locally
	cd docs && python -m http.server 8080

docker-build: ## Build Docker containers
	docker-compose build

docker-up: ## Start Docker containers
	docker-compose up -d

docker-down: ## Stop Docker containers
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f