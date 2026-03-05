FROM python:3.11-slim

# System deps for asyncpg, cryptography, lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (without docling/playwright — use Mistral OCR API in prod)
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py && pip install --no-cache-dir . && rm -rf app

# Copy application code
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY run_worker.py ./

EXPOSE 8000

# Default: API server. Override for worker with: python run_worker.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
