.PHONY: help install dev up down logs migrate worker api test lint format clean start

help:
	@echo "Mecano Man - RAG SaaS Backend"
	@echo ""
	@echo "Commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Install with dev dependencies"
	@echo "  make up         - Start all services (docker)"
	@echo "  make down       - Stop all services"
	@echo "  make start      - Start API + frontend (dev)"
	@echo "  make logs       - View docker logs"
	@echo "  make migrate    - Run database migrations"
	@echo "  make worker     - Start Arq worker"
	@echo "  make api        - Start FastAPI server"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linter"
	@echo "  make format     - Format code"
	@echo "  make clean      - Clean up"

start:
	./start-dev.sh

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

worker:
	python run_worker.py

api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v --cov=app

lint:
	ruff check app tests

format:
	ruff format app tests
	ruff check --fix app tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

# Development workflow
setup: install up migrate
	@echo "Setup complete! Run 'make api' to start the server."

reset-db: down
	docker volume rm mecano-man_postgres_data || true
	docker compose up -d postgres
	sleep 3
	$(MAKE) migrate
