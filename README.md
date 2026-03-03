# Ancre

> SaaS de RAG (Retrieval-Augmented Generation) multi-tenant avec assistants personnalisables, recherche hybride et intégrations OAuth.

## Fonctionnalités

- **Multi-tenant** — Isolation complète par tenant (données, fichiers, vecteurs, quotas)
- **3 scopes RAG** — Org (assistants partagés), Personal (dossiers privés), Project (espaces projet collaboratifs)
- **Chat personnel global** — Assistant personnel qui cherche dans TOUS les contenus d'un utilisateur (dossiers + projets) sans configuration
- **RAG Hybride** — Recherche keyword (PostgreSQL FTS) + vectorielle (Qdrant) fusionnée par RRF + reranking
- **Mémoire structurée** — Extraction automatique de faits/décisions/préférences depuis les conversations, indexés pour le RAG
- **Streaming** — Réponses en temps réel via SSE avec tool-calling itératif
- **Citations** — Sources citées avec nom de fichier, numéro de page et extrait
- **Présentations** — Génération de slides par IA avec 12 templates (Presenton)
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

### Les 3 scopes RAG

ANCRE supporte 3 scopes de contenu mutuellement exclusifs, plus un mode **personnel global** qui agrège les scopes personal + project d'un utilisateur :

| Scope | Identifiant | Filtrage | Cas d'usage |
|-------|------------|----------|-------------|
| **Org** | `assistant_id` → `collection_ids` | `tenant_id` + `collection_id` | Assistants d'entreprise partagés (plan Org) |
| **Personal** | `dossier_id` | `tenant_id` + `user_id` + `dossier_id` | Dossiers personnels thématiques (plan Premium) |
| **Project** | `project_id` | `tenant_id` + `user_id` + `project_id` | Espaces projet avec documents et résumés |
| **Personal Global** | `user_id` (seul) | `tenant_id` + `user_id` + `scope IN (personal, project)` | Chat global — cherche dans TOUT le contenu de l'utilisateur (plan Free) |

#### Invariants de scope

1. **Scopes mutuellement exclusifs au runtime** — exactement un de `assistant_id` / `dossier_id` / `project_id` / `user_id` global. Erreur si combinés.
2. **Double filtre `tenant_id` + `user_id`** — jamais `user_id` seul, toujours combiné avec `tenant_id` (Qdrant ET PostgreSQL).
3. **Filtrage scope explicite** dans Qdrant — `scope IN ('personal','project')` toujours dans les filtres, même si `user_id` suffirait.
4. **CHECK constraints DB** — La table `chunks` et la table `conversations` ont des contraintes CHECK qui empêchent les combinaisons incohérentes.

#### Modèle de données par scope

```
Scope ORG:
  Chunk → scope='org', collection_id=X, tenant_id=T
          user_id=NULL, dossier_id=NULL, project_id=NULL

Scope PERSONAL:
  Chunk → scope='personal', user_id=U, tenant_id=T
          dossier_id=D (ou NULL pour les chunks mémoire)
          collection_id=NULL, project_id=NULL

Scope PROJECT:
  Chunk → scope='project', user_id=U, project_id=P, tenant_id=T
          collection_id=NULL, dossier_id=NULL
```

### Pipeline d'ingestion

Chaque scope a son propre pipeline d'ingestion, mais tous partagent les mêmes étapes de base :

```
Upload fichier (.pdf, .docx, .pptx, .md, .txt, .html)
       │
       ▼
  Validation (quota, doublon SHA256, taille max)
       │
       ▼
  Stockage S3 :
    Org     → {tenant_id}/{collection_id}/{filename}
    Personal → personal/{user_id}/{dossier_id}/{filename}
    Project  → projects/{user_id}/{project_id}/{filename}
       │
       ▼
  Worker Arq (background)
       │
       ├─► Parse document (Docling pipeline ou Mistral OCR fallback)
       ├─► Découpage en chunks (taille fixe ~800 tokens, overlap 100 tokens)
       │     └─ Split sur frontières de phrases (sentence-aware)
       ├─► Génération embeddings batch (Mistral Embed, 1024 dim)
       ├─► Indexation PostgreSQL (TSVECTOR + GIN index pour FTS)
       │     └─ Champs dénormalisés : tenant_id, collection_id/dossier_id/project_id, user_id, scope
       └─► Indexation Qdrant (vecteurs cosine)
              └─ Payload : scope, tenant_id, user_id, collection_id/dossier_id/project_id, source_type
              │
              ▼
        status = "ready"
```

#### Source types

| `source_type` | Origine | Scope |
|---------------|---------|-------|
| `document` (ou NULL) | Document uploadé | org, personal, project |
| `conversation_summary` | Résumé structuré extrait d'une conversation | personal, project |
| `project_summary` | Résumé de conversation projet (ProjectKnowledge) | project |

### Pipeline de recherche (retrieval)

Le pipeline est identique quel que soit le scope — seul le **filtre** change :

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
    - Filtre selon le scope :               - Filtre selon le scope :
      Org:     tenant_id + collection_ids      tenant_id + collection_id
      Personal: tenant_id + dossier_ids         tenant_id + dossier_id
      Project:  tenant_id + project_ids         tenant_id + project_id
      Global:   tenant_id + user_id             tenant_id + user_id
                + scope IN (personal,project)    + scope IN (personal,project)
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

### Flow complet d'un message (par scope)

#### Scope Org (assistant partagé)

```
POST /api/v1/chat/{assistant_id}/stream
       │
       ▼
  1. Chargement assistant (collections + intégrations)
  2. Vérification quota
  3. Historique conversation
  4. Retrieval hybride → filtre collection_ids de l'assistant
  5. Construction prompt : system_prompt assistant + contexte RAG + outils
  6. Appel LLM (Mistral) avec tool-calling itératif
  7. Streaming SSE → sauvegarde messages/citations/blocks
```

#### Scope Personal (dossier)

```
POST /api/v1/dossiers/{dossier_id}/chat/stream
       │
       ▼
  1. Vérification ownership dossier (user_id)
  2. Vérification quota
  3. Historique conversation (scopée au dossier)
  4. Retrieval hybride → filtre dossier_id
  5. Prompt système personnel + contexte RAG
  6. Streaming SSE → sauvegarde
```

#### Scope Personal Global (tous les contenus d'un user)

```
POST /api/v1/chat/personal/stream
       │
       ▼
  1. Auth utilisateur (pas de dossier_id, pas d'assistant_id)
  2. Vérification quota
  3. Conversation : scope='personal', dossier_id=NULL
  4. Retrieval hybride → filtre user_id + scope IN ('personal','project')
     → cherche dans TOUS les dossiers + TOUS les projets + mémoire
  5. Prompt système personnel global
  6. Streaming SSE → sauvegarde
  7. Toutes les 10 messages → extraction mémoire automatique (worker Arq)
```

#### Scope Project

```
POST /api/v1/projects/{project_id}/chat/stream
       │
       ▼
  1. Vérification ownership projet (user_id)
  2. Vérification quota
  3. Historique conversation (scopée au projet)
  4. Retrieval hybride → filtre project_id
  5. Prompt système projet + contexte RAG
  6. Streaming SSE → sauvegarde
  7. Toutes les 5 messages → résumé projet automatique (ProjectKnowledge)
```

### Mémoire structurée (Personal Global)

Le chat personnel global dispose d'un système de mémoire persistante qui transforme les conversations en connaissances indexables :

```
Conversation (10+ messages)
       │
       ▼  Worker Arq : extract_conversation_memory
  Extraction structurée (LLM)
    → Prompt forçant : objectifs, décisions, contraintes, faits, hypothèses, préférences
    → Sortie JSON structurée :
      {
        "goals": ["..."],
        "decisions": ["..."],
        "constraints": ["..."],
        "facts": ["..."],
        "hypotheses": ["..."],
        "preferences": ["..."]
      }
       │
       ▼
  Conversion en texte indexable (sections + bullet points)
       │
       ▼
  Chunking + Embedding + Indexation
    → scope='personal', source_type='conversation_summary'
    → dossier_id=NULL (chunks mémoire indépendants)
    → Qdrant : tenant_id + user_id + scope='personal'
    → PostgreSQL : FTS via content_tsv
```

#### Invariants mémoire

1. **Jamais d'indexation brute** — seuls les résumés structurés sont indexés, jamais les Q/R bruts
2. **source_type explicite** — `conversation_summary` sur chaque chunk mémoire
3. **Consolidation périodique** — quand > 10 résumés existent, un worker les fusionne en une mémoire consolidée (merge JSON + déduplification + résolution de conflits)

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
| **Multi-tenant** | `tenant_id` sur tous les modèles — filtre systématique dans Qdrant ET PostgreSQL |
| **Scope Org** | `assistant_id` → `collection_ids` — chaque assistant ne cherche que dans ses collections |
| **Scope Personal** | `user_id` + `dossier_id` — un user ne voit que ses propres dossiers |
| **Scope Project** | `user_id` + `project_id` — un user ne voit que ses propres projets |
| **Scope Personal Global** | `user_id` + `scope IN (personal, project)` — agrège tout le contenu du user |
| **CHECK constraints** | Contraintes PostgreSQL empêchant les combinaisons incohérentes (ex: scope=org + user_id) |
| **Collections partagées** | Deux assistants d'un même tenant peuvent partager une collection (M:N) |
| **Connecteurs** | Liés par assistant (max 2), scopés par tenant |
| **Vector store** | Payload indexé : `tenant_id`, `collection_id`, `user_id`, `dossier_id`, `project_id`, `scope`, `source_type` |
| **Full-Text Search** | Index composite `(tenant_id, user_id, scope) WHERE user_id IS NOT NULL` pour les scopes personal/project |
| **Stockage S3** | Clé selon scope : `{tenant_id}/{collection_id}/...` (org), `personal/{user_id}/...` (personal), `projects/{user_id}/...` (project) |

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
│   ├── api/v1/                 # Routes API
│   │   ├── chat.py             # Chat org (assistants)
│   │   ├── personal_chat.py    # Chat personnel global
│   │   ├── dossiers.py         # Dossiers + chat personal
│   │   ├── projects.py         # Projets + chat project
│   │   ├── assistants.py       # CRUD assistants
│   │   └── ...                 # documents, dictation, mail, billing…
│   ├── core/                   # Auth, chunking, parsing, vector store
│   │   ├── vector_store.py     # Client Qdrant (search multi-scope)
│   │   └── retrieval/          # Pipeline hybride
│   │       ├── orchestrator.py # Combine keyword + vector → RRF → rerank
│   │       ├── keyword_retriever.py  # PostgreSQL FTS (multi-scope)
│   │       └── vector_retriever.py   # Qdrant (multi-scope)
│   ├── models/                 # Modèles SQLAlchemy
│   │   ├── chunk.py            # Chunks avec scope + CHECK constraint
│   │   ├── conversation.py     # Conversations avec scope + CHECK constraint
│   │   ├── dossier.py          # Dossiers personnels
│   │   ├── project.py          # Projets
│   │   └── ...                 # assistant, message, document…
│   ├── schemas/                # Schémas Pydantic
│   ├── services/               # Logique métier
│   │   ├── chat.py             # ChatService (user_id pour personal global)
│   │   ├── retrieval.py        # RetrievalService (multi-scope)
│   │   ├── memory_extractor.py # Extraction mémoire JSON structurée
│   │   ├── memory_consolidator.py # Consolidation mémoire périodique
│   │   ├── memory_prompts.py   # Prompts extraction + consolidation
│   │   └── ...                 # embedding, transcription, presentation…
│   ├── integrations/           # Nango (OAuth tools, executor, registry)
│   └── workers/                # Workers Arq
│       └── tasks.py            # Ingestion + extraction mémoire + consolidation
├── frontend/                   # Frontend React + Vite
│   └── src/
│       ├── api/                # Clients API (chat, assistants, dossiers…)
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

### Chat Org (assistants)
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/chat/{assistant_id}` | Chat (réponse complète) |
| `POST` | `/api/v1/chat/{assistant_id}/stream` | Chat (SSE streaming) |
| `GET` | `/api/v1/chat/{assistant_id}/conversations` | Lister les conversations |
| `GET` | `/api/v1/chat/{assistant_id}/conversations/{id}` | Historique conversation |

### Chat Personnel Global
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/chat/personal/stream` | Chat global personnel (SSE) — RAG sur tous les dossiers + projets du user |
| `GET` | `/api/v1/chat/personal/conversations` | Lister les conversations personnelles globales |
| `GET` | `/api/v1/chat/personal/conversations/{id}` | Historique d'une conversation globale |

### Dossiers (scope personal)
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/dossiers` | Créer un dossier personnel |
| `GET` | `/api/v1/dossiers` | Lister les dossiers du user |
| `GET` | `/api/v1/dossiers/{id}` | Détails d'un dossier |
| `PATCH` | `/api/v1/dossiers/{id}` | Modifier un dossier |
| `DELETE` | `/api/v1/dossiers/{id}` | Supprimer un dossier |
| `POST` | `/api/v1/dossiers/{id}/documents` | Uploader un document dans un dossier |
| `GET` | `/api/v1/dossiers/{id}/documents` | Lister les documents d'un dossier |
| `DELETE` | `/api/v1/dossiers/{id}/documents/{doc_id}` | Supprimer un document |
| `POST` | `/api/v1/dossiers/{id}/documents/import` | Importer un document existant dans un dossier |
| `POST` | `/api/v1/dossiers/{id}/chat/stream` | Chat dans un dossier (SSE) — RAG scopé au dossier |
| `GET` | `/api/v1/dossiers/{id}/conversations` | Lister les conversations d'un dossier |
| `GET` | `/api/v1/dossiers/{id}/conversations/{conv_id}` | Historique conversation dossier |
| `POST` | `/api/v1/dossiers/{id}/items` | Lier un élément (présentation, email…) au dossier |
| `GET` | `/api/v1/dossiers/{id}/items` | Lister les éléments liés |
| `DELETE` | `/api/v1/dossiers/{id}/items/{item_id}` | Supprimer un lien |

### Projets (scope project)
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/projects` | Créer un projet |
| `GET` | `/api/v1/projects` | Lister les projets du user |
| `GET` | `/api/v1/projects/{id}` | Détails d'un projet |
| `PATCH` | `/api/v1/projects/{id}` | Modifier un projet |
| `DELETE` | `/api/v1/projects/{id}` | Supprimer un projet |
| `POST` | `/api/v1/projects/{id}/documents` | Uploader un document projet |
| `GET` | `/api/v1/projects/{id}/documents` | Lister les documents projet |
| `POST` | `/api/v1/projects/{id}/chat/stream` | Chat dans un projet (SSE) — RAG scopé au projet |
| `GET` | `/api/v1/projects/{id}/conversations` | Lister les conversations projet |

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
