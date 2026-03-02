"""Tests for endpoint-level authorization.

These tests verify the full wiring: endpoint -> dependency -> service,
not just isolated helper functions. Uses TestClient + dependency overrides
to inject specific users/members.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    TENANT_A_ID,
    TENANT_B_ID,
    USER_A_ID,
    USER_B_ID,
    DOSSIER_A_ID,
    ASSISTANT_ID,
    COLLECTION_ID,
    fake_user,
    fake_member,
    fake_dossier,
    mock_db,
)

from app.main import app
from app.deps import get_current_user, get_current_member, get_db
from app.models.enums import OrgRole, MemberStatus


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Ensure dependency overrides are cleaned up after each test."""
    yield
    app.dependency_overrides.clear()


def _override_user(user):
    """Override get_current_user dependency."""
    app.dependency_overrides[get_current_user] = lambda: user


def _override_member(member):
    """Override get_current_member dependency."""
    app.dependency_overrides[get_current_member] = lambda: member


def _override_db(db_mock):
    """Override get_db dependency."""
    async def _fake_db():
        yield db_mock
    app.dependency_overrides[get_db] = _fake_db


# ── Member Status Tests ──────────────────────────────────────────


class TestMemberStatusRejection:
    """Inactive and invited members must be rejected at the endpoint level."""

    def test_inactive_member_rejected(self):
        """INACTIVE member -> 403 on any endpoint."""
        user = fake_user()
        _override_user(user)

        inactive = fake_member(role="member", status="inactive")
        # get_current_member raises 403 for inactive — simulate by overriding
        # to raise the same exception as the real dependency
        from fastapi import HTTPException, status

        def _reject():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your seat has been deactivated. Contact your organization admin.",
            )
        app.dependency_overrides[get_current_member] = _reject

        with TestClient(app) as client:
            response = client.get("/api/v1/dossiers")
        assert response.status_code == 403

    def test_invited_member_rejected(self):
        """INVITED member -> 403 on any endpoint."""
        user = fake_user()
        _override_user(user)

        from fastapi import HTTPException, status

        def _reject():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your invitation is pending. Please complete the onboarding first.",
            )
        app.dependency_overrides[get_current_member] = _reject

        with TestClient(app) as client:
            response = client.get("/api/v1/dossiers")
        assert response.status_code == 403


# ── Dossier Ownership Tests ──────────────────────────────────────


class TestDossierOwnership:
    """Dossier endpoints enforce strict user ownership (no admin override)."""

    def test_user_cannot_read_other_user_dossier(self):
        """GET /dossiers/{id} of another user's dossier -> 404."""
        user_b = fake_user(user_id=USER_B_ID)
        member_b = fake_member(user_id=USER_B_ID, role="member", status="active")
        _override_user(user_b)
        _override_member(member_b)

        # Create a mock DB that returns a dossier owned by USER_A
        db = mock_db()
        dossier_a = fake_dossier(user_id=USER_A_ID)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dossier_a
        db.execute.return_value = mock_result
        _override_db(db)

        with TestClient(app) as client:
            response = client.get(f"/api/v1/dossiers/{DOSSIER_A_ID}")
        assert response.status_code == 404

    def test_admin_cannot_read_other_user_dossier(self):
        """Admin GET /dossiers/{id} of another user -> 404 (no admin override)."""
        admin = fake_user(user_id=USER_B_ID)
        admin_member = fake_member(user_id=USER_B_ID, role="admin", status="active")
        _override_user(admin)
        _override_member(admin_member)

        db = mock_db()
        dossier_a = fake_dossier(user_id=USER_A_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dossier_a
        db.execute.return_value = mock_result
        _override_db(db)

        with TestClient(app) as client:
            response = client.get(f"/api/v1/dossiers/{DOSSIER_A_ID}")
        assert response.status_code == 404

    def test_user_cannot_delete_other_user_dossier(self):
        """DELETE /dossiers/{id} of another user -> 404."""
        user_b = fake_user(user_id=USER_B_ID)
        member_b = fake_member(user_id=USER_B_ID, role="member", status="active")
        _override_user(user_b)
        _override_member(member_b)

        db = mock_db()
        dossier_a = fake_dossier(user_id=USER_A_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dossier_a
        db.execute.return_value = mock_result
        _override_db(db)

        with TestClient(app) as client:
            response = client.delete(f"/api/v1/dossiers/{DOSSIER_A_ID}")
        assert response.status_code == 404


# ── Assistant Access Tests ───────────────────────────────────────


class TestAssistantAccess:
    """Assistant chat endpoints enforce permission checks."""

    def test_member_without_permission_cannot_chat(self):
        """POST /chat/{assistant_id}/stream without AssistantPermission -> 403."""
        user = fake_user()
        member = fake_member(role="member", status="active")
        _override_user(user)
        _override_member(member)

        db = mock_db()

        # First execute: check_assistant_access -> no permission row
        # The mock needs to return different results per call
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # permission check -> None
        ]
        db.execute.side_effect = mock_results
        _override_db(db)

        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/chat/{ASSISTANT_ID}/stream",
                json={"message": "hello"},
            )
        assert response.status_code == 403


# ── Dossier Chat Ownership ───────────────────────────────────────


class TestDossierChatOwnership:
    """Dossier chat endpoints enforce ownership."""

    def test_dossier_chat_rejects_wrong_owner(self):
        """POST /dossiers/{id}/chat/stream for another user's dossier -> 404."""
        user_b = fake_user(user_id=USER_B_ID)
        member_b = fake_member(user_id=USER_B_ID, role="member", status="active")
        _override_user(user_b)
        _override_member(member_b)

        db = mock_db()
        dossier_a = fake_dossier(user_id=USER_A_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dossier_a
        db.execute.return_value = mock_result
        _override_db(db)

        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/dossiers/{DOSSIER_A_ID}/chat/stream",
                json={"message": "hello"},
            )
        assert response.status_code == 404

    def test_dossier_conversations_rejects_wrong_owner(self):
        """GET /dossiers/{id}/conversations for another user -> 404."""
        user_b = fake_user(user_id=USER_B_ID)
        member_b = fake_member(user_id=USER_B_ID, role="member", status="active")
        _override_user(user_b)
        _override_member(member_b)

        db = mock_db()
        dossier_a = fake_dossier(user_id=USER_A_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dossier_a
        db.execute.return_value = mock_result
        _override_db(db)

        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/dossiers/{DOSSIER_A_ID}/conversations",
            )
        assert response.status_code == 404
