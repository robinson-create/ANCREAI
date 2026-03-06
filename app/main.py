"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import ObservabilityMiddleware
from app.core.rate_limit import limiter
from app.database import engine
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize structured logging before anything else
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup — wait for Postgres to be reachable (Railway starts services in parallel)
    max_retries = 20
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("database_connected", extra={"attempt": attempt})
            break
        except Exception as exc:
            if attempt == max_retries:
                logger.error("database_connect_failed after %d attempts", max_retries)
                raise
            delay = min(2 ** attempt, 60)
            logger.warning(
                "database_connect_retry attempt=%d/%d delay=%ds error=%s",
                attempt, max_retries, delay, exc,
            )
            await asyncio.sleep(delay)
    
    yield

    # Shutdown
    from app.core.streams import close_redis
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Mecano Man",
    description="Multi-tenant RAG SaaS API",
    version="0.1.0",
    lifespan=lifespan,
    debug=settings.debug,
)

# Rate limiting (slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Observability middleware (injects request_id, tenant_id into structlog context)
app.add_middleware(ObservabilityMiddleware)

# CORS middleware
_cors_origins = (
    settings.cors_origins.split(",")
    if settings.cors_origins != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/detailed")
async def detailed_health() -> dict:
    """Detailed health check — DB, Redis, Qdrant, queue depth."""
    checks: dict[str, object] = {}

    # Database
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error("health_check_db_error", exc_info=e)
        checks["database"] = f"error: {type(e).__name__}"

    # Redis + Arq queue depth
    try:
        from app.core.streams import get_redis

        redis = await get_redis()
        await redis.ping()
        queue_len = await redis.llen("arq:queue")
        checks["redis"] = "ok"
        checks["queue_depth"] = queue_len
    except Exception as e:
        logger.error("health_check_redis_error", exc_info=e)
        checks["redis"] = f"error: {type(e).__name__}"

    # Qdrant
    try:
        from app.core.vector_store import vector_store

        await vector_store.client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        logger.error("health_check_qdrant_error", exc_info=e)
        checks["qdrant"] = f"error: {type(e).__name__}"

    status = (
        "healthy"
        if all(v == "ok" for k, v in checks.items() if k != "queue_depth")
        else "degraded"
    )
    return {"status": status, "checks": checks}
