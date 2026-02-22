"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import ObservabilityMiddleware
from app.database import engine
from app.api.v1.router import api_router

settings = get_settings()

# Initialize structured logging before anything else
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    # Connection pools are created lazily, but we can test connection here
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    
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

# Observability middleware (injects request_id, tenant_id into structlog context)
app.add_middleware(ObservabilityMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
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
