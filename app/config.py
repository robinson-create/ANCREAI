"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://mecano:mecano@localhost:5432/mecano"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "mecano_chunks"

    # S3 / MinIO
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "mecano-documents"
    s3_region: str = "us-east-1"

    # OpenAI
    openai_api_key: str = ""

    # Embeddings
    embedding_provider: str = "mistral"  # openai | mistral
    embedding_model: str = "mistral-embed"
    embedding_dimensions: int = 1024

    # LLM
    llm_model: str = "mistral-medium-latest"
    llm_slide_model: str = "mistral-large-latest"  # Mistral Large for slide generation
    llm_max_tokens: int = 4096

    # Chunking
    chunk_size: int = 800  # tokens
    chunk_overlap: int = 100  # tokens

    # App
    debug: bool = False
    log_level: str = "INFO"

    # Clerk Authentication
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwks_url: str = ""  # https://<clerk-domain>/.well-known/jwks.json

    # Stripe Billing
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""  # price_xxx for 15€/month

    # Free tier quotas
    free_daily_chat_limit: int = 100
    free_max_files: int = 5

    # Dev mode: bypass Clerk auth
    dev_auth_bypass: bool = False

    # Nango (OAuth connector management)
    nango_url: str = "http://localhost:3003"
    nango_secret_key: str = ""
    nango_public_key: str = ""

    # SMTP (password encryption for smtp_config)
    smtp_encryption_key: str = ""  # 32-byte base64 (Fernet key)

    # CopilotKit
    copilotkit_runtime_url: str = "http://localhost:4000"

    # --- Transcription (Mistral Voxtral) ---
    transcription_model: str = "mistral-stt-latest"

    # --- Document parsing (Docling) ---
    use_docling: bool = True  # Use Docling as primary parser for uploads
    docling_ocr_engine: str = "easyocr"  # easyocr | tesseract | rapidocr

    # --- Mistral OCR (fallback) ---
    mistral_api_key: str = ""
    mistral_ocr_model: str = "mistral-ocr-latest"
    use_mistral_ocr: bool = True
    ocr_only_for_pdf: bool = True
    ocr_heuristic_min_text_chars: int = 500

    # --- Hybrid retrieval ---
    hybrid_keyword_topk: int = 40
    hybrid_vector_topk: int = 40
    hybrid_rrf_k: int = 60
    postgres_fts_config: str = "simple"

    # Minimum relevance score for chunks to be included in context.
    # Chunks below this threshold are discarded to avoid polluting
    # the LLM with irrelevant documents (e.g. bike parts for a salary question).
    # Uses rerank_score > fused_score > score, whichever is available.
    rag_min_relevance_score: float = 0.15

    # --- Rerank (remote) ---
    rerank_enabled: bool = True
    rerank_provider: str = "hf_endpoint"  # hf_endpoint | mistral
    rerank_fallback_provider: str = "mistral"  # mistral | none

    # HF Inference Endpoint (primary reranker)
    hf_rerank_url: str = ""
    hf_rerank_token: str = ""
    rerank_timeout_seconds: int = 5
    rerank_retry_max: int = 1

    # Mistral LLM rerank (fallback)
    rerank_mistral_model: str = "mistral-small-latest"
    rerank_temperature: float = 0.0
    rerank_mistral_timeout_seconds: int = 8

    # Rerank behavior
    rerank_max_candidates: int = 40
    rerank_final_topn: int = 10
    rerank_max_passage_chars: int = 1500

    # --- Web search ---
    web_search_enabled: bool = False
    web_search_provider: str = "brave"  # brave | serper | tavily
    web_search_api_key: str = ""
    web_search_topk: int = 5
    web_search_timeout_seconds: int = 8
    web_cache_ttl_hours: int = 24  # TTL for cached web results

    # --- Presentations ---
    pptx_exporter_url: str = "http://localhost:4100"

    # --- Agent runtime ---
    agent_stream_ttl: int = 600  # Redis stream TTL in seconds
    agent_stream_maxlen: int = 2000  # XTRIM approximate maxlen
    agent_sse_heartbeat_interval: float = 15.0  # seconds between heartbeats
    agent_sse_hard_timeout: float = 180.0  # max SSE duration (seconds)
    agent_stuck_run_threshold: int = 600  # seconds before a run is considered stuck
    agent_delta_batch_ms: int = 300  # batch delta events every N ms


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
