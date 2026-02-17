# Nango Integration (Self-Hosted)

## Overview

[Nango](https://www.nango.dev/) manages OAuth connections to external services (CRM, ERP, etc.). We self-host it in Docker for dev. Nango handles:

- OAuth flow orchestration (redirects, popups)
- Token storage and encryption
- Automatic token refresh
- Pre-built connectors for 250+ APIs

We **never store OAuth tokens** in our database. We only store a reference (`NangoConnection`) linking a tenant to a Nango connection.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Frontend    │     │  FastAPI     │     │  Nango       │
│  (React)     │────►│  Backend     │────►│  Server      │
│              │     │              │     │  (:3003)     │
│  Integrations│     │ /integrations│     │              │
│  Page        │     │ /nango/*     │     │  - OAuth     │
│              │     │              │     │  - Tokens    │
│              │◄────┤              │     │  - Refresh   │
│  OAuth Popup │     └──────────────┘     └──────┬───────┘
│  (Nango)     │                                  │
└──────────────┘                           ┌──────┴───────┐
                                           │  Nango DB    │
                                           │  (Postgres)  │
                                           │  (:5433)     │
                                           └──────────────┘
```

## Running locally

### 1. Start Nango services

```bash
docker compose up nango nango-db -d
```

Nango will be available at http://localhost:3003.

### 2. Verify Nango is running

```bash
curl http://localhost:3003/health
```

### 3. Configure a provider (example: HubSpot)

Via the Nango API or dashboard, create an integration:

```bash
curl -X POST http://localhost:3003/config \
  -H "Authorization: Bearer nango-dev-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_config_key": "hubspot",
    "provider": "hubspot",
    "oauth_client_id": "YOUR_HUBSPOT_CLIENT_ID",
    "oauth_client_secret": "YOUR_HUBSPOT_CLIENT_SECRET",
    "oauth_scopes": "crm.objects.contacts.read"
  }'
```

For Salesforce:
```bash
curl -X POST http://localhost:3003/config \
  -H "Authorization: Bearer nango-dev-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_config_key": "salesforce",
    "provider": "salesforce",
    "oauth_client_id": "YOUR_SF_CLIENT_ID",
    "oauth_client_secret": "YOUR_SF_CLIENT_SECRET",
    "oauth_scopes": "api refresh_token"
  }'
```

### 4. Use the Integrations page

Navigate to `/app/integrations` in the frontend. Click "Connecter" on a provider to start the OAuth flow.

## Docker Compose services

| Service | Port | Description |
|---------|------|-------------|
| `nango` | 3003 | Nango server (API + OAuth handling) |
| `nango-db` | 5433 | Dedicated PostgreSQL for Nango |

Nango uses its own database (separate from our app DB) to store connection credentials, tokens, and configuration.

## Environment variables

### Backend (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `NANGO_URL` | `http://localhost:3003` | Nango server URL |
| `NANGO_SECRET_KEY` | `nango-dev-secret-key` | API secret key |
| `NANGO_PUBLIC_KEY` | `nango-dev-public-key` | Public key (frontend) |

### Docker Compose

| Variable | Default | Description |
|----------|---------|-------------|
| `NANGO_SECRET_KEY` | `nango-dev-secret-key` | Override in .env |
| `NANGO_PUBLIC_KEY` | `nango-dev-public-key` | Override in .env |
| `NANGO_ENCRYPTION_KEY` | `000...` (dev only) | 32-byte hex for token encryption |

**Production**: Generate a real encryption key:
```bash
openssl rand -hex 32
```

## API Endpoints

### `POST /api/v1/integrations/nango/connect/{provider}`

Initiate an OAuth connection. Returns a `connect_url` for the frontend to open in a popup.

**Auth**: Clerk JWT required
**Multi-tenant**: Connection is scoped to `{tenant_id}:{provider}`

### `GET /api/v1/integrations/nango/callback`

Called by the frontend after the OAuth popup closes to update connection status.

**Params**: `providerConfigKey`, `connectionId`

### `GET /api/v1/integrations/nango/connections`

List all connections for the current tenant.

### `DELETE /api/v1/integrations/nango/connections/{provider}`

Delete a connection (both in our DB and Nango).

## Database model

`nango_connections` table (our DB, NOT Nango's DB):

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `tenant_id` | UUID | FK to tenants |
| `provider` | VARCHAR(100) | e.g. "hubspot" |
| `nango_connection_id` | VARCHAR(255) | ID in Nango: "{tenant_id}:{provider}" |
| `status` | VARCHAR(50) | pending / connected / error |
| `metadata_json` | TEXT | Optional JSON |
| `created_at` | TIMESTAMP | Auto |
| `updated_at` | TIMESTAMP | Auto |

## Multi-tenant isolation

- Each Nango connection ID is prefixed with the `tenant_id`: `"{tenant_id}:{provider}"`
- All API endpoints verify the user's tenant before returning or modifying data
- Nango stores tokens internally - our DB only holds references
- The `CurrentUser` dependency (Clerk JWT) ensures authentication

## Files

### Backend
- `app/integrations/nango/client.py` - HTTP client for Nango API
- `app/integrations/nango/schemas.py` - Pydantic request/response models
- `app/integrations/nango/models.py` - SQLAlchemy `NangoConnection` model
- `app/api/v1/integrations.py` - FastAPI endpoints

### Frontend
- `frontend/src/pages/integrations.tsx` - Integrations page UI
- `frontend/src/api/integrations.ts` - API client

### Config
- `app/config.py` - Settings (nango_url, nango_secret_key, nango_public_key)
- `.env.example` - Environment template
- `docker-compose.yml` - Nango + nango-db services
