"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from app.api.v1 import tenants, assistants, collections, documents, chat, usage, billing, webhooks
from app.api.v1 import copilotkit
from app.api.v1 import integrations
from app.api.v1 import dictation
from app.api.v1 import workspace_documents
from app.api.v1 import mail
from app.api.v1 import onboarding
from app.api.v1 import calendar

api_router = APIRouter()

api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(assistants.router, prefix="/assistants", tags=["assistants"])
api_router.include_router(collections.router, prefix="/collections", tags=["collections"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(copilotkit.router, prefix="/copilotkit", tags=["copilotkit"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(dictation.router, prefix="/dictation", tags=["dictation"])
api_router.include_router(workspace_documents.router, prefix="/workspace-documents", tags=["workspace-documents"])
api_router.include_router(mail.router, prefix="/mail", tags=["mail"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
