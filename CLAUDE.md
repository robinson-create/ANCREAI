# ANCRE AI — Developer Guide

## Project Overview

Multi-tenant RAG SaaS platform. Users upload documents, connect integrations, and chat with AI assistants that retrieve relevant context from their knowledge base.

**Monorepo structure:**
```
ancre-ai/
├── app/                    # FastAPI backend (Python 3.11)
├── frontend/               # React + Vite frontend (TypeScript)
├── packages/               # Shared packages (presentation-layout)
├── copilot-runtime/        # CopilotKit Node.js runtime (dev only, NOT deployed in prod)
├── slide-export-service/   # Puppeteer-based PPTX export service
├── alembic/                # Database migrations
├── scripts/                # Utility scripts
└── tests/                  # Backend tests
```

---

## Production Infrastructure

### Hosting

| Service | Platform | URL / Access |
|---------|----------|-------------|
| **Frontend** | Vercel | `https://ancreai.eu` |
| **Backend API** | Railway | `https://ancreai-production.up.railway.app` |
| **PostgreSQL** | Railway (managed) | `postgres.railway.internal:5432` |
| **Redis** | Railway (managed) | `redis.railway.internal:6379` |
| **Qdrant** | Railway (Docker: `qdrant/qdrant`) | `http://qdrant-db.railway.internal:6333` |
| **Object Storage** | Scaleway S3 (`fr-par`) | `https://s3.fr-par.scw.cloud` / bucket: `mecano-documents` |
| **Auth** | Clerk (Production instance) | `https://clerk.ancreai.eu` |

### Railway Project

- **Project name**: `celebrated-creativity`
- **Project ID**: `8c5d914d-d41f-4cf6-a6ae-7ddd97627160`
- **Region**: `europe-west4`
- **Services**: ANCREAI (backend), Postgres, Redis, qdrant-db

**Railway CLI access:**
```bash
railway login
railway link --project 8c5d914d-d41f-4cf6-a6ae-7ddd97627160 --environment production
railway service ANCREAI      # switch to backend
railway variables            # view env vars
railway logs                 # view deploy logs
```

### Vercel (Frontend)

- **Project**: `ancreai`
- **Framework**: Vite (React)
- **Root directory**: `frontend/`
- **Build command**: `npm run build` (includes prebuild for `packages/presentation-layout`)
- **Output**: `frontend/dist/`
- **SPA rewrites**: `vercel.json` rewrites all routes to `/index.html`

**Key Vercel env vars:**
- `VITE_CLERK_PUBLISHABLE_KEY` = `pk_live_Y2xlcmsuYW5jcmVhaS5ldSQ`
- `VITE_API_BASE_URL` = `https://ancreai-production.up.railway.app`
- `VITE_COPILOTKIT_RUNTIME_URL` = (empty — disabled in prod)

### Scaleway Object Storage

- **Endpoint**: `https://s3.fr-par.scw.cloud`
- **Region**: `fr-par`
- **Bucket**: `mecano-documents`
- Access keys stored in Railway env vars: `S3_ACCESS_KEY`, `S3_SECRET_KEY`

---

## Backend Stack

### Core Technologies

- **Framework**: FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) + asyncpg
- **Task queue**: Arq + Redis (worker: `app/workers/tasks.py`, run: `python run_worker.py`)
- **Auth**: Clerk JWT → `app/core/auth.py` validates via JWKS, `app/deps.py` resolves user
- **Config**: `app/config.py` (pydantic-settings, reads from env vars)
- **Migrations**: Alembic (async, in `alembic/versions/`)

### Dockerfile & Startup

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```
Migrations run automatically before the server starts on each deploy.

### API Routes (`app/api/v1/router.py`)

All endpoints under `/api/v1/`:
- `/chat`, `/chat/personal` — RAG chat (SSE streaming)
- `/assistants` — CRUD for AI assistants
- `/collections`, `/documents` — Knowledge base management
- `/onboarding` — Signup flow (creates user, tenant, assistant, collection)
- `/presentations` — Slide deck generation & editing
- `/workspace-documents` — Document generation (contracts, reports)
- `/contacts`, `/calendar`, `/mail` — CRM-like features
- `/billing`, `/usage` — Stripe integration & usage tracking
- `/integrations` — Nango OAuth connectors
- `/uploads` — File uploads with OCR processing
- `/folders`, `/dossiers`, `/projects` — Organization features

### Key Services (`app/services/`)

- `chat.py` — ChatService: RAG pipeline (retrieve → prompt → stream)
- `retrieval.py` — Hybrid search orchestrator
- `embedding.py` — Mistral embeddings
- `presentation_slide_generator.py` — 3-step LLM pipeline for slide decks
- `stripe_service.py` — Billing & subscriptions
- `web_crawler.py` — Website crawling for knowledge base
- `storage.py` — S3/MinIO file storage

### Hybrid Search Pipeline

1. Embed query → parallel keyword search (PG FTS) + vector search (Qdrant)
2. RRF merge (k=60)
3. Rerank: HF Inference Endpoint → Mistral LLM fallback → RRF order
4. Returns top-N `RetrievedChunk` with scores

### Database Models (`app/models/`)

Key tables: `tenants`, `users`, `assistants`, `collections`, `documents`, `chunks`, `conversations`, `messages`, `subscriptions`, `org_members`, `presentations`, `workspace_documents`, `contacts`, `folders`, `dossiers`, `projects`

- Tenant isolation via `tenant_id` on all user-facing tables
- Chunks have denormalized `tenant_id`, `collection_id`, `content_tsv` (TSVECTOR)
- `DocumentPage` stores per-page text for citations

---

## Frontend Stack

### Technologies

- **React 18** + **TypeScript** + **Vite**
- **React Router v7** (DOM)
- **TanStack React Query v5** — data fetching & caching
- **Zustand v5** — local state stores
- **Clerk React** — authentication
- **Radix UI + Tailwind CSS** — components & styling
- **Framer Motion** — animations
- **TipTap** — rich text editing

### Important Patterns

- **API client**: `frontend/src/api/client.ts` — Axios with Clerk JWT interceptor
  - Base URL: `VITE_API_BASE_URL` → `${url}/api/v1` (production: Railway backend)
  - Dev: proxied via Vite to `localhost:8000`
- **Auth flow**: `ClerkProvider` → `AuthTokenProvider` → JWT injected on all API calls
- **Protected routes**: `ProtectedRoute` checks `onboarding-status` API, redirects if incomplete
- **CopilotKit**: Disabled in production (no runtime URL). Do NOT use `useCopilotReadable` / `useCopilotAction` hooks outside of `CopilotProvider`-wrapped components — crashes when provider is absent.

### Key Pages (`frontend/src/pages/`)

- `search.tsx` — Main search/chat interface
- `assistant-page.tsx` — Assistant configuration
- `documents.tsx` — File management & uploads
- `presentation-editor.tsx` — Slide deck editor
- `document-editor.tsx` — Workspace document editor
- `onboarding-v2.tsx` → `onboarding/transition.tsx` → `onboarding/setup.tsx` — Signup flow
- `profile.tsx` — User settings & integrations
- `billing.tsx` — Subscription management

---

## Environment Variables

### Backend (Railway) — Required

```
DATABASE_URL              # Auto-injected by Railway Postgres
REDIS_URL                 # Auto-injected by Railway Redis
QDRANT_URL                # http://qdrant-db.railway.internal:6333
CLERK_JWKS_URL            # https://clerk.ancreai.eu/.well-known/jwks.json
CLERK_SECRET_KEY          # sk_live_... (from Clerk Production dashboard)
CLERK_PUBLISHABLE_KEY     # pk_live_Y2xlcmsuYW5jcmVhaS5ldSQ
DEV_AUTH_BYPASS            # false (MUST be false in prod)
FRONTEND_URL              # https://ancreai.eu
CORS_ORIGINS              # https://ancreai.eu
MISTRAL_API_KEY           # For embeddings, LLM, OCR
S3_ENDPOINT_URL           # https://s3.fr-par.scw.cloud
S3_ACCESS_KEY / S3_SECRET_KEY / S3_BUCKET / S3_REGION
```

### Frontend (Vercel) — Build-time

```
VITE_CLERK_PUBLISHABLE_KEY    # pk_live_...
VITE_API_BASE_URL             # https://ancreai-production.up.railway.app
VITE_COPILOTKIT_RUNTIME_URL   # (empty — disabled in prod)
```

### Local Dev (`.env` at project root)

- `DEV_AUTH_BYPASS=true` — Skips Clerk auth, uses mock dev user
- `DATABASE_URL=postgresql+asyncpg://mecano:mecano@localhost:5432/mecano`
- All services run locally (Postgres, Redis, Qdrant on default ports)

---

## Deployment

### Backend (Railway)

- Auto-deploys from `main` branch on GitHub
- Dockerfile at project root builds the backend
- Migrations run automatically via `alembic upgrade head` in CMD
- Worker is a separate process: `python run_worker.py` (not currently deployed on Railway)

### Frontend (Vercel)

- Auto-deploys from `main` branch on GitHub
- Build: `npm run build` in `frontend/` directory
- `.env.production` in `frontend/` provides build-time env vars
- Vercel env vars override `.env.production` if set

### Clerk (Authentication)

- **Production instance** — Frontend API: `https://clerk.ancreai.eu`
- Session token must include custom claims: `{"email": "{{user.primary_email_address}}", "name": "{{user.first_name}}"}`
- Configure in Clerk Dashboard → Sessions → Customize session token

---

## Common Operations

### Run migrations
```bash
# Local
alembic upgrade head

# Production (automatic on deploy, or via Railway shell)
railway run alembic upgrade head
```

### Add a Railway env var
```bash
railway service ANCREAI
railway variables set KEY="value"
```

### Check production logs
```bash
railway service ANCREAI && railway logs
```

### Local development
```bash
# Backend
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Worker
python run_worker.py
```

---

## Git Workflow

- **Main branch**: `main` (auto-deploys to Railway + Vercel)
- Always test locally before pushing
- NEVER force-push to main
- Commit messages: concise, focused on "why"
