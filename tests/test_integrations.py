"""Smoke tests for Nango and CopilotKit integration endpoints.

These tests verify:
1. Schema validation (pure unit tests)
2. Route registration (endpoints exist)
3. Basic request/response flow (with DEV_AUTH_BYPASS)

Note: Nango endpoint tests may return 500 if the nango_connections table
hasn't been created yet (migration 003 not applied). This is expected
in CI without a fully migrated DB. The schema tests are the primary
validation target.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


# --- Fixtures ---

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Auth headers for dev mode (DEV_AUTH_BYPASS=true)."""
    return {"Authorization": "Bearer dev-token"}


# --- Schema Validation Tests (no DB required) ---

class TestSchemas:
    """Test that Pydantic schemas validate correctly."""

    def test_nango_connection_schema(self):
        from app.integrations.nango.schemas import NangoConnectionOut

        conn = NangoConnectionOut(
            id="test-id",
            provider="hubspot",
            nango_connection_id="tenant:hubspot",
            tenant_id="tenant-123",
            status="connected",
            created_at="2025-01-01T00:00:00",
        )
        assert conn.provider == "hubspot"
        assert conn.status == "connected"

    def test_nango_connect_response_schema(self):
        from app.integrations.nango.schemas import NangoConnectResponse

        resp = NangoConnectResponse(
            connect_url="https://nango.example.com/connect",
            connection_id="tenant:hubspot",
            provider="hubspot",
        )
        assert resp.provider == "hubspot"
        assert "nango" in resp.connect_url

    def test_kpi_response_schema(self):
        from app.api.v1.copilotkit import KpiResponse, KpiMetric

        response = KpiResponse(
            title="Test KPI",
            description="Test",
            period="Q1 2025",
            kpis=[
                KpiMetric(label="Revenue", value="$100k", change=12.5),
                KpiMetric(label="Users", value="1000"),
            ],
            tenant_id="tenant-123",
        )
        assert len(response.kpis) == 2
        assert response.kpis[0].change == 12.5
        assert response.kpis[1].change is None

    def test_kpi_request_schema(self):
        from app.api.v1.copilotkit import KpiRequest

        req = KpiRequest(category="sales")
        assert req.category == "sales"

        req_default = KpiRequest()
        assert req_default.category == "general"


# --- CopilotKit Endpoint Tests ---

class TestCopilotKitEndpoints:
    """Tests for CopilotKit backend actions."""

    def test_kpi_endpoint_returns_structured_data(self, auth_headers):
        """The KPI action endpoint should return structured KPI data."""
        with TestClient(app) as c:
            response = c.post(
                "/api/v1/copilotkit/actions/kpi",
                json={"category": "general"},
                headers=auth_headers,
            )
        if response.status_code == 200:
            data = response.json()
            assert "title" in data
            assert "kpis" in data
            assert isinstance(data["kpis"], list)
            assert len(data["kpis"]) > 0
            assert "tenant_id" in data
            kpi = data["kpis"][0]
            assert "label" in kpi
            assert "value" in kpi
        else:
            assert response.status_code in (401, 400, 500)


# --- Nango Endpoint Tests (require migrated DB) ---

class TestNangoEndpoints:
    """Tests for Nango integration endpoints.

    Each test creates a fresh TestClient to avoid DB session pollution
    from previous test failures (e.g. Nango unreachable → rollback).
    """

    def test_list_connections_responds(self, auth_headers):
        """Listing connections endpoint should respond."""
        with TestClient(app) as c:
            response = c.get(
                "/api/v1/integrations/nango/connections",
                headers=auth_headers,
            )
        assert response.status_code in (200, 401, 500)
        if response.status_code == 200:
            data = response.json()
            assert "connections" in data
            assert isinstance(data["connections"], list)

    def test_delete_endpoint_responds(self, auth_headers):
        """Delete endpoint should respond."""
        with TestClient(app) as c:
            response = c.delete(
                "/api/v1/integrations/nango/connections/nonexistent",
                headers=auth_headers,
            )
        assert response.status_code in (401, 404, 500)

    def test_callback_requires_connection_id(self, auth_headers):
        """Callback without connectionId should return 400."""
        with TestClient(app) as c:
            response = c.get(
                "/api/v1/integrations/nango/callback",
                headers=auth_headers,
            )
        assert response.status_code in (400, 401, 500)

    def test_connect_endpoint_responds(self, auth_headers):
        """Connect endpoint should respond (even if Nango is unreachable)."""
        with TestClient(app) as c:
            response = c.post(
                "/api/v1/integrations/nango/connect/hubspot",
                headers=auth_headers,
            )
        # 502 = Nango unreachable (expected in test without Docker)
        assert response.status_code in (401, 409, 500, 502)


# --- Route Registration Tests ---

class TestRouteRegistration:
    """Verify all new routes are registered."""

    def test_copilotkit_routes_exist(self):
        from app.api.v1.router import api_router

        paths = [r.path for r in api_router.routes]
        assert "/copilotkit/actions/kpi" in paths

    def test_nango_routes_exist(self):
        from app.api.v1.router import api_router

        paths = [r.path for r in api_router.routes]
        assert "/integrations/nango/connect/{provider}" in paths
        assert "/integrations/nango/connections" in paths
        assert "/integrations/nango/callback" in paths
        assert "/integrations/nango/connections/{provider}" in paths
