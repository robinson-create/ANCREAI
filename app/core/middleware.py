"""FastAPI middleware for observability context injection."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_var, tenant_id_var, user_id_var

logger = get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Injects request_id, tenant_id, user_id into context vars for structured logging."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Generate or propagate request ID
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request_id_var.set(request_id)

        # Extract tenant_id from header (set by auth middleware)
        raw_tenant = request.headers.get("x-tenant-id")
        if raw_tenant:
            tenant_id_var.set(raw_tenant)

        raw_user = request.headers.get("x-user-id")
        if raw_user:
            user_id_var.set(raw_user)

        logger.debug(
            "request_started",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        response.headers["x-request-id"] = request_id

        logger.debug(
            "request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )

        return response
