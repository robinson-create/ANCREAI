"""CopilotKit integration endpoints.

This module provides a FastAPI endpoint that the CopilotKit runtime
calls as a "remote action". It demonstrates how backend-driven actions
work with CopilotKit while respecting multi-tenant auth.

The CopilotKit runtime (Node.js) orchestrates LLM calls and tool execution.
When the LLM decides to call a tool that lives on our backend, the runtime
forwards the call here. We process it with full access to our DB, auth, etc.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import CurrentUser, DbSession

router = APIRouter()


class KpiRequest(BaseModel):
    """Request payload for the KPI demo action."""
    category: str = "general"


class KpiMetric(BaseModel):
    """A single KPI metric."""
    label: str
    value: str
    change: float | None = None


class KpiResponse(BaseModel):
    """Response payload with KPI data."""
    title: str
    description: str
    period: str
    kpis: list[KpiMetric]
    tenant_id: str


@router.post("/actions/kpi", response_model=KpiResponse)
async def get_kpi_data(
    request: KpiRequest,
    user: CurrentUser,
    db: DbSession,
) -> KpiResponse:
    """Demo endpoint: return stub KPI data for the current tenant.

    This shows how a CopilotKit remote action can:
    1. Authenticate via Clerk JWT (same as all our endpoints)
    2. Access the tenant context
    3. Query the database if needed
    4. Return structured data that CopilotKit renders as a card

    In production, this would query real metrics from the DB.
    """
    tenant_id = str(user.tenant_id)

    # Stub data - in production, query from DB
    kpis = [
        KpiMetric(label="Documents indexés", value="1,247", change=12.5),
        KpiMetric(label="Conversations", value="89", change=8.3),
        KpiMetric(label="Tokens utilisés", value="2.1M", change=-3.2),
        KpiMetric(label="Assistants actifs", value="5", change=0),
    ]

    return KpiResponse(
        title=f"KPI - {request.category.title()}",
        description=f"Métriques pour le tenant {tenant_id[:8]}...",
        period="30 derniers jours",
        kpis=kpis,
        tenant_id=tenant_id,
    )
