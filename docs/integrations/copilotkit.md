# CopilotKit Integration

## Architecture

CopilotKit adds **Generative UI** capabilities to Ancre: the AI can render structured UI components (cards, charts, forms) directly in the chat, not just text.

### Components

```
┌─────────────────────┐      ┌─────────────────────┐      ┌──────────────┐
│  Frontend (React)   │      │  CopilotKit Runtime  │      │ FastAPI      │
│                     │◄────►│  (Node.js :4000)     │─────►│ Backend      │
│  - CopilotProvider  │      │                      │      │ (:8000)      │
│  - CopilotPopup     │      │  - OpenAI Adapter    │      │              │
│  - useCopilotAction │      │  - Remote Actions    │      │  /copilotkit │
│  - KpiCard          │      │    → FastAPI backend  │      │  /actions/kpi│
└─────────────────────┘      └─────────────────────┘      └──────────────┘
```

### How it works

1. **CopilotKit Provider** (`CopilotProvider.tsx`) wraps the app and connects to the runtime
2. **CopilotKit Popup** (`CopilotChatPopup.tsx`) renders a floating chat widget
3. **Actions** (`CopilotActions.tsx`) register tools the LLM can call:
   - `render_kpi_card`: renders a KPI card with metrics and trends
4. **Runtime** (`copilot-runtime/`) is a minimal Node.js/Express server using `@copilotkit/runtime`
5. **Backend actions** (`app/api/v1/copilotkit.py`) handle server-side logic (auth, DB queries)

### Streaming: CopilotKit vs existing SSE

| Aspect | Existing chat (RAG) | CopilotKit popup |
|--------|---------------------|------------------|
| Protocol | Custom SSE via `fetch()` | CopilotKit protocol (GraphQL-based) |
| LLM | OpenAI via our FastAPI | OpenAI via CopilotKit Runtime |
| Features | Document retrieval, citations | Generative UI, tool calls |
| UI | Custom chat component | CopilotKit `<CopilotPopup>` |

**Decision**: Both coexist. The existing RAG chat is untouched. CopilotKit adds a complementary popup for tool-based interactions. A future consolidation could route all chat through CopilotKit, but this requires migrating the RAG pipeline to CopilotKit actions.

## Files

### Frontend
- `frontend/src/components/copilotkit/CopilotProvider.tsx` - Provider wrapper
- `frontend/src/components/copilotkit/CopilotActions.tsx` - Action registrations
- `frontend/src/components/copilotkit/CopilotChatPopup.tsx` - Popup chat widget
- `frontend/src/components/copilotkit/KpiCard.tsx` - KPI card component (shadcn/ui)

### Runtime
- `copilot-runtime/src/index.ts` - Express server with CopilotKit runtime
- `copilot-runtime/Dockerfile` - Container build

### Backend
- `app/api/v1/copilotkit.py` - FastAPI endpoints for remote actions

## Running locally

### Option 1: Docker Compose (recommended)
```bash
docker compose up copilot-runtime -d
```

### Option 2: Manual
```bash
cd copilot-runtime
npm install
OPENAI_API_KEY=sk-xxx npm run dev
```

The runtime runs on http://localhost:4000. The Vite dev server proxies `/copilotkit` to it.

## Environment variables

| Variable | Where | Default | Description |
|----------|-------|---------|-------------|
| `OPENAI_API_KEY` | Runtime | required | OpenAI API key for CopilotKit LLM |
| `COPILOT_LLM_MODEL` | Runtime | `gpt-4o-mini` | LLM model for CopilotKit |
| `COPILOT_RUNTIME_PORT` | Runtime | `4000` | Runtime server port |
| `BACKEND_ACTIONS_URL` | Runtime | `http://localhost:8000/api/v1/copilotkit/actions` | FastAPI actions URL |
| `VITE_COPILOTKIT_RUNTIME_URL` | Frontend | `/copilotkit` | Runtime URL (proxied in dev) |

## Adding new actions

1. **Frontend-only action** (renders UI, no backend call):
   ```tsx
   // In CopilotActions.tsx
   useCopilotAction({
     name: "my_action",
     description: "...",
     parameters: [...],
     render: ({ args }) => <MyComponent {...args} />,
     handler: async (args) => "Done",
   })
   ```

2. **Backend action** (needs DB/auth):
   - Add endpoint in `app/api/v1/copilotkit.py`
   - The CopilotKit runtime calls it as a remote action
   - Auth is handled via the same `CurrentUser` dependency

## Tenant isolation

The FastAPI endpoint uses `CurrentUser` dependency which extracts `tenant_id` from the Clerk JWT. All data is scoped to the tenant. The CopilotKit popup inherits the user's auth session.
