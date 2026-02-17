# Mecano-Man API Documentation

**Version:** 1.0.0  
**Base URL:** `https://api.mecano-man.com/api/v1`

## Overview

Mecano-Man est une plateforme RAG (Retrieval-Augmented Generation) multi-tenant permettant de créer des assistants IA qui peuvent répondre à des questions basées sur des documents uploadés.

## Authentification

Toutes les requêtes doivent inclure le header `X-Tenant-ID` avec l'UUID du tenant.

```http
X-Tenant-ID: 550e8400-e29b-41d4-a716-446655440000
```

---

## Endpoints

### Tenants

#### GET /tenants
Liste tous les tenants.

**Response:** `200 OK`
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Acme Corp",
    "settings": {},
    "max_assistants": 3,
    "max_ingestion_tokens": 1000000,
    "max_chat_tokens": 500000,
    "max_storage_bytes": 1073741824,
    "created_at": "2026-01-29T10:00:00Z",
    "updated_at": "2026-01-29T10:00:00Z"
  }
]
```

---

#### POST /tenants
Crée un nouveau tenant.

**Request Body:**
```json
{
  "name": "Acme Corp",
  "settings": {},
  "max_assistants": 3,
  "max_ingestion_tokens": 1000000,
  "max_chat_tokens": 500000,
  "max_storage_bytes": 1073741824
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | ✅ | - | Nom du tenant |
| `settings` | object | ❌ | `null` | Configuration personnalisée |
| `max_assistants` | integer | ❌ | `3` | Nombre max d'assistants |
| `max_ingestion_tokens` | integer | ❌ | `1000000` | Quota tokens ingestion/mois |
| `max_chat_tokens` | integer | ❌ | `500000` | Quota tokens chat/mois |
| `max_storage_bytes` | integer | ❌ | `1073741824` | Quota stockage (1 GB) |

**Response:** `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme Corp",
  "settings": {},
  "max_assistants": 3,
  "max_ingestion_tokens": 1000000,
  "max_chat_tokens": 500000,
  "max_storage_bytes": 1073741824,
  "created_at": "2026-01-29T10:00:00Z",
  "updated_at": "2026-01-29T10:00:00Z"
}
```

---

#### GET /tenants/{tenant_id}
Récupère un tenant par son ID.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `tenant_id` | UUID | ID du tenant |

**Response:** `200 OK` - Même format que POST response

---

#### PATCH /tenants/{tenant_id}
Met à jour un tenant.

**Request Body:** (tous les champs sont optionnels)
```json
{
  "name": "Acme Corp Updated",
  "settings": { "theme": "dark" },
  "max_assistants": 5
}
```

**Response:** `200 OK` - Tenant mis à jour

---

#### DELETE /tenants/{tenant_id}
Supprime un tenant et toutes ses données.

**Response:** `204 No Content`

---

### Collections

#### GET /collections
Liste toutes les collections du tenant.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | integer | `0` | Offset pagination |
| `limit` | integer | `20` | Limite pagination (max 100) |
| `include_stats` | boolean | `false` | Inclure les statistiques |

**Response:** `200 OK`
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Documentation technique",
    "description": "Manuels et guides utilisateur",
    "created_at": "2026-01-29T10:00:00Z",
    "updated_at": "2026-01-29T10:00:00Z",
    "documents_count": 15,
    "total_chunks": 342
  }
]
```

---

#### POST /collections
Crée une nouvelle collection.

**Request Body:**
```json
{
  "name": "Documentation technique",
  "description": "Manuels et guides utilisateur"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Nom de la collection |
| `description` | string | ❌ | Description |

**Response:** `201 Created`
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Documentation technique",
  "description": "Manuels et guides utilisateur",
  "created_at": "2026-01-29T10:00:00Z",
  "updated_at": "2026-01-29T10:00:00Z"
}
```

---

#### GET /collections/{collection_id}
Récupère une collection par son ID.

**Response:** `200 OK`

---

#### PATCH /collections/{collection_id}
Met à jour une collection.

**Request Body:**
```json
{
  "name": "Nouveau nom",
  "description": "Nouvelle description"
}
```

**Response:** `200 OK`

---

#### DELETE /collections/{collection_id}
Supprime une collection et tous ses documents.

**Response:** `204 No Content`

---

### Documents

#### GET /collections/{collection_id}/documents
Liste les documents d'une collection.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | integer | `0` | Offset pagination |
| `limit` | integer | `20` | Limite pagination |
| `status` | string | - | Filtrer par statut |

**Response:** `200 OK`
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "collection_id": "660e8400-e29b-41d4-a716-446655440001",
    "filename": "manual-v2.pdf",
    "content_type": "application/pdf",
    "file_size": 2048576,
    "content_hash": "sha256:abc123...",
    "status": "ready",
    "error_message": null,
    "page_count": 45,
    "chunk_count": 128,
    "tokens_used": 15420,
    "metadata": { "version": "2.0" },
    "created_at": "2026-01-29T10:00:00Z",
    "updated_at": "2026-01-29T10:30:00Z",
    "processed_at": "2026-01-29T10:30:00Z"
  }
]
```

**Document Status Values:**
| Status | Description |
|--------|-------------|
| `pending` | En attente de traitement |
| `processing` | En cours de traitement |
| `ready` | Prêt pour le RAG |
| `failed` | Échec du traitement |

---

#### POST /collections/{collection_id}/documents
Upload un nouveau document.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | ✅ | Fichier à uploader (PDF, DOCX, TXT, MD) |
| `metadata` | string (JSON) | ❌ | Métadonnées personnalisées |

**Formats supportés:**
- `application/pdf`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `text/plain`
- `text/markdown`

**Response:** `202 Accepted`
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "filename": "manual-v2.pdf",
  "status": "pending",
  "message": "Document queued for processing"
}
```

---

#### GET /collections/{collection_id}/documents/{document_id}
Récupère les détails d'un document.

**Response:** `200 OK` - Même format que dans la liste

---

#### DELETE /collections/{collection_id}/documents/{document_id}
Supprime un document et ses chunks.

**Response:** `204 No Content`

---

#### GET /collections/{collection_id}/documents/{document_id}/download
Télécharge le fichier original.

**Response:** `200 OK`  
**Content-Type:** `application/octet-stream`  
**Content-Disposition:** `attachment; filename="manual-v2.pdf"`

---

### Assistants

#### GET /assistants
Liste les assistants du tenant.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | integer | `0` | Offset pagination |
| `limit` | integer | `20` | Limite pagination |

**Response:** `200 OK`
```json
[
  {
    "id": "880e8400-e29b-41d4-a716-446655440003",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Support Technique",
    "system_prompt": "Tu es un assistant technique qui aide les utilisateurs...",
    "model": "gpt-4o-mini",
    "settings": {
      "temperature": 0.7,
      "max_tokens": 1024
    },
    "collection_ids": [
      "660e8400-e29b-41d4-a716-446655440001"
    ],
    "created_at": "2026-01-29T10:00:00Z",
    "updated_at": "2026-01-29T10:00:00Z"
  }
]
```

---

#### POST /assistants
Crée un nouvel assistant.

**Request Body:**
```json
{
  "name": "Support Technique",
  "system_prompt": "Tu es un assistant technique qui aide les utilisateurs à résoudre leurs problèmes. Réponds de manière claire et concise en te basant sur la documentation fournie.",
  "model": "gpt-4o-mini",
  "settings": {
    "temperature": 0.7,
    "max_tokens": 1024
  },
  "collection_ids": [
    "660e8400-e29b-41d4-a716-446655440001"
  ]
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | ✅ | - | Nom de l'assistant |
| `system_prompt` | string | ❌ | `null` | Instructions système |
| `model` | string | ❌ | `gpt-4o-mini` | Modèle LLM |
| `settings` | object | ❌ | `null` | Configuration du modèle |
| `collection_ids` | UUID[] | ❌ | `[]` | Collections liées |

**Modèles disponibles:**
- `gpt-4o-mini` (par défaut, économique)
- `gpt-4o` (plus puissant)

**Response:** `201 Created`

---

#### GET /assistants/{assistant_id}
Récupère un assistant.

**Response:** `200 OK`

---

#### PATCH /assistants/{assistant_id}
Met à jour un assistant.

**Request Body:** (tous les champs optionnels)
```json
{
  "name": "Support Technique v2",
  "collection_ids": ["660e8400-e29b-41d4-a716-446655440001", "660e8400-e29b-41d4-a716-446655440002"]
}
```

**Response:** `200 OK`

---

#### DELETE /assistants/{assistant_id}
Supprime un assistant.

**Response:** `204 No Content`

---

### Chat

#### POST /chat/{assistant_id}
Envoie un message à l'assistant (réponse complète).

**Request Body:**
```json
{
  "message": "Comment installer le produit?",
  "conversation_id": null,
  "include_history": true,
  "max_history_messages": 10
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | ✅ | - | Message de l'utilisateur |
| `conversation_id` | UUID | ❌ | `null` | ID conversation existante (null = nouvelle) |
| `include_history` | boolean | ❌ | `true` | Inclure l'historique |
| `max_history_messages` | integer | ❌ | `10` | Nombre max de messages historiques |

**Response:** `200 OK`
```json
{
  "message": "Pour installer le produit, suivez ces étapes:\n\n1. Téléchargez le fichier d'installation...",
  "conversation_id": "990e8400-e29b-41d4-a716-446655440004",
  "citations": [
    {
      "chunk_id": "aa0e8400-e29b-41d4-a716-446655440005",
      "document_id": "770e8400-e29b-41d4-a716-446655440002",
      "document_filename": "manual-v2.pdf",
      "page_number": 12,
      "excerpt": "Pour installer le produit, commencez par télécharger le fichier...",
      "score": 0.92
    }
  ],
  "tokens_input": 1245,
  "tokens_output": 387
}
```

---

#### POST /chat/{assistant_id}/stream
Envoie un message avec réponse en streaming (SSE).

**Request Body:** Même format que `/chat/{assistant_id}`

**Response:** `200 OK` (Server-Sent Events)

```
event: start
data: {"conversation_id": "990e8400-e29b-41d4-a716-446655440004"}

event: token
data: "Pour"

event: token
data: " installer"

event: token
data: " le"

...

event: citations
data: [{"chunk_id": "...", "document_id": "...", ...}]

event: done
data: {"tokens_input": 1245, "tokens_output": 387}
```

**Event Types:**
| Event | Data | Description |
|-------|------|-------------|
| `start` | `{ conversation_id }` | Début de la réponse |
| `token` | string | Token de la réponse |
| `citations` | Citation[] | Citations trouvées |
| `done` | `{ tokens_input, tokens_output }` | Fin de la réponse |
| `error` | `{ message }` | Erreur |

---

### Usage

#### GET /usage
Récupère le résumé d'utilisation du tenant pour la période courante.

**Response:** `200 OK`
```json
{
  "period": "2026-01",
  "ingestion_tokens_used": 450000,
  "chat_tokens_used": 125000,
  "storage_bytes_used": 524288000,
  "max_ingestion_tokens": 1000000,
  "max_chat_tokens": 500000,
  "max_storage_bytes": 1073741824,
  "ingestion_percent": 45.0,
  "chat_percent": 25.0,
  "storage_percent": 48.8
}
```

---

#### GET /usage/history
Récupère l'historique d'utilisation.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `months` | integer | `6` | Nombre de mois d'historique |

**Response:** `200 OK`
```json
[
  {
    "id": "bb0e8400-e29b-41d4-a716-446655440006",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "period": "2026-01-01",
    "ingestion_tokens": 450000,
    "chat_input_tokens": 85000,
    "chat_output_tokens": 40000,
    "storage_bytes": 524288000,
    "documents_count": 15,
    "messages_count": 342
  }
]
```

---

## Codes d'erreur

| Code | Description |
|------|-------------|
| `400` | Requête invalide |
| `401` | Non authentifié |
| `403` | Accès interdit |
| `404` | Ressource non trouvée |
| `409` | Conflit (ex: nom déjà utilisé) |
| `413` | Fichier trop volumineux |
| `415` | Type de fichier non supporté |
| `422` | Données invalides |
| `429` | Quota dépassé |
| `500` | Erreur serveur |

### Exemple d'erreur standard
```json
{
  "detail": "Collection not found"
}
```

### Exemple d'erreur de quota
```json
{
  "detail": "Ingestion token quota exceeded",
  "quota_type": "ingestion",
  "current": 1050000,
  "limit": 1000000
}
```

---

## Types

### UUID
Format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`  
Exemple: `550e8400-e29b-41d4-a716-446655440000`

### DateTime
Format ISO 8601: `YYYY-MM-DDTHH:mm:ssZ`  
Exemple: `2026-01-29T10:00:00Z`

### Date
Format: `YYYY-MM-DD`  
Exemple: `2026-01-29`

---

## Rate Limiting

| Endpoint | Limite |
|----------|--------|
| Chat endpoints | 60 req/min |
| Document upload | 10 req/min |
| Autres endpoints | 120 req/min |

Headers de réponse:
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1706522460
```

---

## Webhooks (à venir)

Configuration des webhooks pour recevoir des notifications:

| Event | Description |
|-------|-------------|
| `document.processed` | Document traité avec succès |
| `document.failed` | Échec du traitement |
| `quota.warning` | Quota à 80% |
| `quota.exceeded` | Quota dépassé |

---

## SDKs

- JavaScript/TypeScript: `@mecano-man/sdk` (à venir)
- Python: `mecano-man` (à venir)

---

## Changelog

### v1.0.0 (2026-01-29)
- Release initiale
- Gestion des tenants, collections, documents
- Assistants avec RAG
- Chat synchrone et streaming
- Suivi des quotas
