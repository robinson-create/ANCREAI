# Ancre AI - Project Memory

## Architecture
- Monorepo: FastAPI backend (`app/`), React/Vite frontend (`frontend/`), CopilotKit runtime (`copilot-runtime/`)
- DB: Postgres (async via asyncpg+SQLAlchemy 2.0), migrations via Alembic
- Auth: Clerk JWT, `DEV_AUTH_BYPASS=true` for local dev
- Multi-tenant: `tenant_id` on all resources, `CurrentUser` dependency extracts from JWT
- Package manager: npm (frontend), pip with pyproject.toml (backend)
- Frontend port: 3000 (Vite), Backend: 8000 (uvicorn)

## Key Patterns
- Dependencies: `CurrentUser`, `DbSession`, `TenantId` in `app/deps.py`
- SSE streaming in `app/api/v1/chat.py` via `StreamingResponse`
- API client with Clerk token interceptor in `frontend/src/api/client.ts`
- shadcn/ui components in `frontend/src/components/ui/`
- `@/lib/utils.ts` contains the `cn()` helper (clsx + tailwind-merge)

## Testing
- Async DB pool causes session pollution between sync TestClient tests
- **Fix**: Use `with TestClient(app) as c:` context manager per test for isolation
- Schema/route tests don't need DB → put them first in test files

## Integrations Added
- **CopilotKit**: Provider + Popup + Actions in frontend, Node runtime in `copilot-runtime/`, FastAPI actions endpoint
- **Nango**: Self-hosted Docker services, `app/integrations/nango/` module, `NangoConnection` model, `/app/integrations` page
