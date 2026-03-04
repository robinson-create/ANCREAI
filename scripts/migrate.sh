#!/bin/bash
# Run Alembic migrations (one-shot, isolated from API boot).
# Usage:
#   - Railway: configure as a cron/one-shot service, or run via `railway run`
#   - Local:   DATABASE_URL="postgresql+asyncpg://..." ./scripts/migrate.sh
set -e
echo "Running Alembic migrations..."
alembic upgrade head
echo "Migrations complete."
