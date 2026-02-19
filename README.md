# Ancre

> SaaS de RAG (Retrieval-Augmented Generation) multi-tenant avec assistants personnalisables, recherche hybride et intégrations OAuth.

## Fonctionnalités

- **Multi-tenant** — Isolation complète par tenant (données, fichiers, vecteurs, quotas)
- **Multi-assistants** — Créez plusieurs assistants avec leurs propres collections de documents et connecteurs
- **RAG Hybride** — Recherche keyword (PostgreSQL FTS) + vectorielle (Qdrant) fusionnée par RRF + reranking
- **Streaming** — Réponses en temps réel via SSE avec tool-calling itératif
- **Citations** — Sources citées avec nom de fichier, numéro de page et extrait
- **Documents** — Éditeur de documents structurés avec IA (contrats, devis, NDA…)
- **Emails** — Compositeur d'emails assisté par IA avec contexte RAG
- **Email Suggestion** — L'assistant propose de transformer une réponse actionnable en email via un bloc CTA (suivi, synthèse, relance, proposition)
- **Recherche** — Interface de recherche avec historique, reprise de conversations et dictée vocale
- **Dictée vocale** — Reconnaissance vocale native (Web Speech API) sur toutes les pages
- **Generative UI** — Blocs dynamiques (KPIs, tableaux, étapes) générés par le LLM
- **Connecteurs OAuth** — Intégrations HubSpot, Gmail, Google Drive, Notion, Slack, etc. via Nango
- **Authentification** — Clerk pour l'auth utilisateur (JWT + JWKS)
- **Billing** — Stripe pour les abonnements (Free / Pro)

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Uvicorn |
| **Frontend** | React 18, Vite 6, TypeScript |
| **UI** | TailwindCSS, shadcn/ui (Radix UI), Lucide icons |
| **State / Data** | TanStack Query (React Query), Zustand |
| **Base de données** | PostgreSQL 16 (+ Full-Text Search via TSVECTOR) |
| **Vector Store** | Qdrant (cosine similarity) |
| **Stockage fichiers** | MinIO (dev) / S3 (prod) |
| **File d'attente** | Arq + Redis 7 |
| **Auth** | Clerk (JWT + JWKS) |
| **Billing** | Stripe |
| **LLM** | Mistral (`mistral-medium-latest`) via API OpenAI-compatible |
| **Embeddings** | Mistral (`mistral-embed`, 1024 dimensions) |
| **Reranking** | HuggingFace Inference Endpoint (primaire) / Mistral (fallback) |
| **Transcription** | Mistral Voxtral (`mistral-stt-latest`) |
| **OCR** | Mistral OCR (`mistral-ocr-latest`) |
| **Chat UI** | Assistant UI (composer, dictée) + Web Speech API |
| **Generative UI** | CopilotKit (runtime Node.js + React) |
| **OAuth / Connecteurs** | Nango (self-hosted) |

## Architecture RAG

### Pipeline d'ingestion

```
Upload fichier (.pdf, .docx, .pptx, .md, .txt, .html)
       │
       ▼
  Validation (quota, doublon SHA256, taille max)
       │
       ▼
  Stockage S3 : {tenant_id}/{collection_id}/{filename}
       │
       ▼
  Worker Arq (background)
       │
       ├─► Parse document (Mistral OCR pour les PDFs, python-docx, etc.)
       ├─► Découpage en chunks (taille fixe ~800 tokens, overlap 100 tokens)
       │     └─ Split sur frontières de phrases (sentence-aware)
       ├─► Génération embeddings batch (Mistral Embed, 1024 dim)
       ├─► Indexation PostgreSQL (TSVECTOR + GIN index pour FTS)
       └─► Indexation Qdrant (vecteurs cosine)
              │
              ▼
        status = "ready"
```

### Pipeline de recherche (retrieval)

```
Question utilisateur
       │
       ▼
  Embedding de la query (Mistral Embed)
       │
       ├────────────────────────────────────────┐
       ▼                                        ▼
  Recherche Keyword (PostgreSQL FTS)     Recherche Vectorielle (Qdrant)
    - to_tsquery() avec logique OR         - Cosine similarity
    - Filtre: tenant_id + collection_ids   - Filtre: tenant_id + collection_ids
    - Ranking: ts_rank_cd()                - Top-K résultats
    - Top-40 candidats                     - Top-40 candidats
       │                                        │
       └────────────┬───────────────────────────┘
                    ▼
          RRF Merge (Reciprocal Rank Fusion)
            score = Σ 1/(k + rang),  k=60
            Déduplique les chunks communs
                    │
                    ▼
          Reranking (optionnel)
            - Primaire: HuggingFace Inference Endpoint
            - Fallback: Mistral Small (LLM-based)
            - Top-10 résultats finaux
                    │
                    ▼
          Contexte assemblé pour le LLM
            (chunks avec source, page, extrait)
```

### Flow complet d'un message

```
Message utilisateur
       │
       ▼
  1. Chargement assistant (collections + intégrations)
  2. Vérification quota (Free tier: 100 requêtes/jour)
  3. Historique conversation (si include_history=true)
  4. Retrieval hybride (keyword + vector → RRF → rerank)
  5. Construction du prompt système :
       - Instructions de l'assistant (system_prompt)
       - Contexte RAG (chunks avec métadonnées)
       - Instructions pour les outils (blocks UI + intégrations)
  6. Appel LLM (Mistral Medium) avec tool-calling :
       - Boucle itérative (max 5 tours) :
         · Si outil "block" → Generative UI (KPI, tableau, étapes, callout)
         · Si outil "suggestEmail" → Crée un EmailDraftBundle en DB + bloc CTA
         · Si outil "integration" → Appel API externe via Nango
         · Sinon → Réponse texte
  7. Streaming SSE des tokens vers le frontend
  8. Sauvegarde en DB (messages, citations, blocks, tokens)
  9. Extraction des citations (top-5 chunks, score > 0)
```

### Email Suggestion (chat → email)

```
Réponse assistant (contenu actionnable: synthèse, suivi, relance…)
       │
       ▼
  LLM appelle suggestEmail(subject, body_draft, tone, reason)
       │
       ▼
  Backend crée un EmailDraftBundle en DB
    (tenant_id, conversation_id, subject, body_draft, tone, reason, citations)
       │
       ▼
  SSE event: block { type: "email_suggestion", payload: { bundle_id, subject, reason, tone } }
       │
       ▼
  Frontend affiche un bloc CTA "Transformer en email"
    - Bouton "Créer l'email" → /app/email?bundle=<bundle_id>
    - Bouton "Ignorer" → masque le bloc
       │
       ▼
  Page Email Composer charge le bundle via GET /mail/bundles/{id}
    → Hydrate le sujet, le brouillon et le ton
```

### Cloisonnement des données

| Niveau | Mécanisme |
|--------|-----------|
| **Multi-tenant** | `tenant_id` sur tous les modèles (assistant, collection, chunk, connexion) |
| **Entre assistants** | Scoping par `collection_ids` — chaque assistant ne cherche que dans ses collections |
| **Collections partagées** | Deux assistants d'un même tenant peuvent partager une collection (M:N) |
| **Connecteurs** | Liés par assistant (max 2), scopés par tenant |
| **Vector store** | Filtrage Qdrant par `tenant_id` + `collection_ids` dans le payload |
| **Full-Text Search** | `WHERE tenant_id = ? AND collection_id = ANY(?)` avec champs dénormalisés |
| **Stockage S3** | Clé : `{tenant_id}/{collection_id}/{filename}` |

### Connecteurs disponibles (Nango)

| Provider | Usage |
|----------|-------|
| HubSpot | CRM, contacts, deals |
| Pipedrive | CRM |
| Gmail | Emails |
| Outlook | Emails |
| Google Drive | Documents |
| Notion | Pages |
| Slack | Messages |
| Shopify | E-commerce |
| Stripe | Paiements |

Chaque connecteur est invoqué par le LLM via **function calling**. L'appel transite par le Nango Proxy qui injecte automatiquement le token OAuth. Max 2 connecteurs par assistant.

## Pages de l'application

| Page | Route | Description |
|------|-------|-------------|
| **Accueil** | `/app` | Actions rapides, prompt libre avec dictée, historique unifié |
| **Documents** | `/app/documents` | Liste des documents rédigés (contrats, devis, NDA…) |
| **Éditeur** | `/app/documents/:id` | Éditeur structuré avec IA (génération, réécriture, ligne items) |
| **Emails** | `/app/email` | Compositeur d'email avec ton, contexte et sources RAG |
| **Recherche** | `/app/search` | Recherche dans les sources, historique en vignettes, conversations avec fil d'Ariane |
| **Assistants** | `/app/assistants` | Liste et création des assistants |
| **Config assistant** | `/app/assistant/:id` | Configuration (prompt, documents, liens, connecteurs) |
| **Profil** | `/app/profile` | Paramètres utilisateur et connecteurs OAuth |
| **Facturation** | `/app/billing` | Abonnement Stripe (Free / Pro) |

## Outils de développement

- **Python** : uv ou pip, venv, Ruff (lint/format), Pytest
- **Node** : npm, Vite (dev server + build)
- **DB** : Alembic (migrations)
- **Conteneurs** : Docker & Docker Compose (PostgreSQL, Redis, Qdrant, MinIO, Nango, CopilotKit runtime)

## Structure du projet

```
├── app/                         # Backend FastAPI
│   ├── api/v1/                 # Routes API (chat, assistants, documents, dictation…)
│   ├── core/                   # Auth, chunking, parsing, vector store
│   │   └── retrieval/          # Pipeline hybride (orchestrator, keyword, vector, RRF, reranker)
│   ├── models/                 # Modèles SQLAlchemy (assistant, message, chunk, document…)
│   ├── schemas/                # Schémas Pydantic
│   ├── services/               # Logique métier (chat, retrieval, embedding, transcription…)
│   ├── integrations/           # Nango (OAuth tools, executor, registry)
│   └── workers/                # Workers Arq (ingestion async)
├── frontend/                   # Frontend React + Vite
│   └── src/
│       ├── api/                # Clients API (chat, assistants, dictation…)
│       ├── components/         # Composants UI (blocks, documents, layout…)
│       ├── hooks/              # Hooks React (auth, dictation…)
│       ├── lib/                # Utilitaires (dictation adapter, cn…)
│       └── pages/              # Pages de l'application
├── copilot-runtime/            # CopilotKit Node.js runtime
├── alembic/                    # Migrations database
├── tests/                      # Tests
└── docs/                       # Documentation
    └── integrations/           # CopilotKit & Nango docs
```

## Prérequis

- **Python 3.11+**
- **Node.js 18+** (LTS recommandé)
- **Docker & Docker Compose** (pour PostgreSQL, Redis, Qdrant, MinIO, Nango)
- Comptes / clés :
  - [Mistral AI](https://console.mistral.ai) (obligatoire — LLM, embeddings, OCR, transcription)
  - [Clerk](https://dashboard.clerk.com) (optionnel en dev avec `DEV_AUTH_BYPASS=true`)
  - [Stripe](https://dashboard.stripe.com) (optionnel pour le billing)

## Installation en local

### 1. Cloner le dépôt

```bash
git clone https://github.com/<org>/ancre-ai.git
cd ancre-ai
```

### 2. Environnement Python

```bash
# Créer et activer un venv (recommandé)
python3.11 -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

# Installer les dépendances (backend)
make dev
# ou : pip install -e ".[dev]"
```

### 3. Variables d'environnement backend

À la **racine** du projet :

```bash
cp .env.example .env
```

Éditer `.env` et renseigner au minimum :

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Déjà prêt si vous gardez `postgresql+asyncpg://mecano:mecano@localhost:5432/mecano` après `make up` |
| `MISTRAL_API_KEY` | Clé API Mistral (obligatoire — LLM, embeddings, OCR, transcription) |
| `CLERK_SECRET_KEY` | Clé secrète Clerk ([dashboard](https://dashboard.clerk.com)) |
| `CLERK_PUBLISHABLE_KEY` | Clé publique Clerk (même dashboard) |
| `CLERK_JWKS_URL` | `https://<votre-instance>.clerk.accounts.dev/.well-known/jwks.json` |

En dev, `DEV_AUTH_BYPASS=true` permet de tester sans Clerk. Stripe, Nango et CopilotKit ont des valeurs par défaut ou optionnelles (voir `.env.example`).

### 4. Variables d'environnement frontend

Dans le dossier **frontend** :

```bash
cp frontend/.env.example frontend/.env
```

À configurer :

| Variable | Description |
|----------|-------------|
| `VITE_CLERK_PUBLISHABLE_KEY` | Même clé publique Clerk que le backend (préfixe **VITE_** obligatoire pour Vite) |

Sans clé Clerk valide, l'app tourne en mode « sans auth » (message en console). Les autres variables (`VITE_STRIPE_PUBLISHABLE_KEY`, `VITE_COPILOTKIT_RUNTIME_URL`, etc.) sont optionnelles pour un premier run.

### 5. Dépendances frontend

```bash
cd frontend
npm install
cd ..
```

### 6. Lancer les services Docker

À la racine :

```bash
make up
```

Démarre PostgreSQL, Redis, Qdrant, MinIO, Nango et (optionnel) le runtime CopilotKit. Attendre quelques secondes que les healthchecks passent.

### 7. Migrations base de données

```bash
make migrate
# ou : alembic upgrade head
```

### 8. Démarrer l'application

Ouvrir **4 terminaux** à la racine du projet :

| Terminal | Commande | Rôle |
|----------|----------|------|
| 1 | `make api` | API FastAPI (port 8000) |
| 2 | `make worker` | Worker Arq (ingestion documents) |
| 3 | `cd frontend && npm run dev` | Frontend Vite (port 3000) |
| 4 | `cd copilot-runtime && npm run dev` | CopilotKit runtime (port 4000, optionnel) |

Ou utiliser le script fourni (si présent) : `make start` / `./start-dev.sh`.

### URLs locales

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **API** | http://localhost:8000 |
| **Swagger** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **MinIO Console** | http://localhost:9001 |
| **Qdrant Dashboard** | http://localhost:6333/dashboard |
| **CopilotKit Runtime** | http://localhost:4000 |
| **Nango** | http://localhost:3003 |

## API Endpoints

### Tenants
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/tenants` | Créer un tenant |
| `GET` | `/api/v1/tenants` | Lister les tenants |
| `GET` | `/api/v1/tenants/{id}` | Détails d'un tenant |

### Collections
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/collections` | Créer une collection |
| `GET` | `/api/v1/collections` | Lister les collections |
| `DELETE` | `/api/v1/collections/{id}` | Supprimer une collection |

### Documents
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/documents/upload/{collection_id}` | Uploader un fichier |
| `GET` | `/api/v1/documents` | Lister les documents |
| `DELETE` | `/api/v1/documents/{id}` | Supprimer un document |

### Assistants
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/assistants` | Créer un assistant |
| `GET` | `/api/v1/assistants` | Lister les assistants |
| `PATCH` | `/api/v1/assistants/{id}` | Modifier un assistant |
| `DELETE` | `/api/v1/assistants/{id}` | Supprimer un assistant |

### Chat
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/chat/{assistant_id}` | Chat (réponse complète) |
| `POST` | `/api/v1/chat/{assistant_id}/stream` | Chat (SSE streaming) |
| `GET` | `/api/v1/chat/{assistant_id}/conversations` | Lister les conversations |
| `GET` | `/api/v1/chat/{assistant_id}/conversations/{id}` | Historique conversation |

### Dictée vocale
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/dictation/transcribe` | Transcrire un fichier audio (Mistral Voxtral) |

### Workspace Documents
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/workspace-documents` | Créer un document de travail |
| `GET` | `/api/v1/workspace-documents` | Lister les documents |
| `GET` | `/api/v1/workspace-documents/{id}` | Détails d'un document |
| `PATCH` | `/api/v1/workspace-documents/{id}` | Modifier un document |
| `POST` | `/api/v1/workspace-documents/{id}/ai` | Actions IA sur le document |

### Email Draft Bundles
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/mail/bundles/{id}` | Récupérer un bundle email (tenant-scoped) |

### Usage & Billing
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/usage` | Usage courant avec quotas |
| `GET` | `/api/v1/usage/history` | Historique d'usage |
| `POST` | `/api/v1/billing/checkout` | Créer une session Stripe |
| `POST` | `/api/v1/billing/portal` | Portail client Stripe |

### Intégrations (Nango)
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/integrations/nango/connect/{provider}` | Initier une connexion OAuth |
| `GET` | `/api/v1/integrations/nango/callback` | Callback OAuth |
| `GET` | `/api/v1/integrations/nango/connections` | Lister les connexions du tenant |
| `DELETE` | `/api/v1/integrations/nango/connections/{provider}` | Supprimer une connexion |

### CopilotKit
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/copilotkit/actions/kpi` | Action KPI (données structurées) |

## Formats de documents supportés

| Format | Extensions |
|--------|------------|
| PDF | `.pdf` (avec OCR Mistral automatique) |
| Word | `.docx` |
| PowerPoint | `.pptx` |
| HTML | `.html`, `.htm` |
| Markdown | `.md` |
| Texte | `.txt` |
| CSV | `.csv` |
| Excel | `.xlsx`, `.xls` |

## Configuration

**Backend** (racine, fichier `.env`) — variables principales :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `DATABASE_URL` | URL PostgreSQL (async) | `postgresql+asyncpg://mecano:mecano@localhost:5432/mecano` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379` |
| `QDRANT_URL` | URL Qdrant | `http://localhost:6333` |
| `MISTRAL_API_KEY` | Clé API Mistral (obligatoire) | — |
| `LLM_MODEL` | Modèle LLM | `mistral-medium-latest` |
| `EMBEDDING_PROVIDER` | Provider embeddings | `mistral` |
| `EMBEDDING_MODEL` | Modèle embeddings | `mistral-embed` |
| `TRANSCRIPTION_MODEL` | Modèle transcription audio | `mistral-stt-latest` |
| `RERANK_PROVIDER` | Reranker primaire | `hf_endpoint` |
| `RERANK_FALLBACK_PROVIDER` | Reranker fallback | `mistral` |
| `USE_MISTRAL_OCR` | Activer l'OCR Mistral pour les PDFs | `true` |
| `CLERK_SECRET_KEY` | Clé secrète Clerk | — |
| `CLERK_PUBLISHABLE_KEY` | Clé publique Clerk | — |
| `CLERK_JWKS_URL` | URL JWKS Clerk (validation JWT) | — |
| `STRIPE_SECRET_KEY` | Clé secrète Stripe (optionnel) | — |
| `DEV_AUTH_BYPASS` | Bypass auth en dev | `false` |
| `NANGO_URL` | URL du serveur Nango | `http://localhost:3003` |
| `NANGO_SECRET_KEY` | Clé secrète Nango | — |
| `SMTP_ENCRYPTION_KEY` | Clé Fernet pour chiffrer les mots de passe SMTP (connexion Gmail/Outlook SMTP) | — |

> **SMTP** : Pour connecter un compte mail via SMTP (Gmail, Outlook ou serveur perso), générez une clé :
> `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` puis ajoutez `SMTP_ENCRYPTION_KEY=<la_clé>` dans `.env`.

**Frontend** (`frontend/.env`) — préfixe **`VITE_`** obligatoire pour exposition au navigateur :

| Variable | Description |
|----------|-------------|
| `VITE_CLERK_PUBLISHABLE_KEY` | Clé publique Clerk (même que backend) |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Clé publique Stripe (optionnel) |
| `VITE_COPILOTKIT_RUNTIME_URL` | URL du runtime CopilotKit (défaut: `/copilotkit` en dev) |

Voir `.env.example` et `frontend/.env.example` pour la liste complète.

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│     Frontend     │────▶│     FastAPI      │────▶│  PostgreSQL  │
│   React / Vite   │     │   + Arq Workers  │     │  + FTS (GIN) │
│  + Assistant UI  │     └──────┬───────────┘     └──────────────┘
└──────┬───────────┘            │
       │        ┌───────────────┼────────────────────┐
       │        ▼               ▼                    ▼
       │  ┌──────────┐   ┌──────────┐         ┌──────────┐
       │  │  Redis   │   │  Qdrant  │         │  MinIO   │
       │  │  (queue) │   │ (vectors)│         │   (S3)   │
       │  └────┬─────┘   └──────────┘         └──────────┘
       │       │
       │       ▼
       │  ┌──────────────────────────────────────────────┐
       │  │  Worker Arq                                  │
       │  │  Parse → OCR(Mistral) → Chunk →Embed → Index │
       │  └──────────────────────────────────────────────┘
       │
       │                 ┌──────────────────┐
       │                 │   Mistral AI     │
       │                 │  - Medium (LLM)  │
       │                 │  - Embed (RAG)   │
       └────────────────▶│  - OCR (docs)    │
                         │  - Voxtral (STT) │
                         └──────────────────┘
                         ┌──────────────────┐
                         │     Nango        │
                         │  (OAuth proxy)   │
                         │  HubSpot, Gmail, │
                         │  Drive, Notion…  │
                         └──────────────────┘
```

## Commandes Make

```bash
make install   # Installer les dépendances Python (prod)
make dev      # Installer les dépendances Python (avec dev)
make up       # Démarrer tous les services Docker
make down     # Arrêter les services Docker
make setup    # install + up + migrate (bootstrap rapide)
make api      # Lancer l'API FastAPI (port 8000)
make worker   # Lancer le worker Arq
make migrate  # Appliquer les migrations Alembic
make start    # Démarrer API + frontend (script start-dev.sh)
make test     # Lancer les tests (pytest)
make lint     # Linter (ruff)
make format   # Formater le code (ruff)
make clean    # Nettoyer caches Python
```

## License

MIT
