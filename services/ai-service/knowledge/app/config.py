"""
Configuration for Aifya Knowledge RAG service.
Uses pydantic-settings for env-based configuration.
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_backend_root = Path(__file__).resolve().parent.parent
load_dotenv(_backend_root / ".env")

_TRUE_VALUES = {"1", "true", "yes", "on", "dev", "development"}
_FALSE_VALUES = {
    "0",
    "false",
    "no",
    "off",
    "",
    "release",
    "production",
    "prod",
}

_INSECURE_DEFAULTS = {
    "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32",
    "CHANGE_ME_IN_PRODUCTION",
    "miniosupersecret",
    "aifyaadmin",
}


class Settings(BaseSettings):
    """
    Knowledge RAG service settings.
    All secrets MUST be overridden via env vars in production.
    """

    # --- Environment ---
    app_env: str = Field("development", validation_alias="APP_ENV")
    debug: bool = Field(False, validation_alias="DEBUG")

    # --- API ---
    api_v1_str: str = "/api/v1"
    project_name: str = "Aifya Knowledge RAG"
    host: str = Field("0.0.0.0", validation_alias="HOST")
    port: int = Field(8025, validation_alias="PORT")

    # --- Auth ---
    # "internal" verifies the HS256 tokens the api-gateway issues for
    # Aifya's own login/registration forms, which is what the web app's
    # /api/knowledge proxy forwards. "keycloak" verifies RS256 tokens
    # against the realm JWKS instead. This MUST match the api-gateway's
    # AUTH_PROVIDER and SECRET_KEY or every proxied request returns 401.
    auth_provider: str = Field("internal", validation_alias="AUTH_PROVIDER")
    secret_key: str = Field("", validation_alias="SECRET_KEY")

    # --- Auth (Keycloak JWKS, only used when auth_provider == "keycloak") ---
    keycloak_url: str = Field(
        "http://localhost:8080", validation_alias="KEYCLOAK_URL"
    )
    keycloak_realm: str = Field("aifya", validation_alias="KEYCLOAK_REALM")
    jwt_algorithm: str = "RS256"

    # --- Database (document metadata) ---
    database_url: str = Field(
        "postgresql+asyncpg://aifya_user:change_me_in_production@localhost:5432/aifya",
        validation_alias="DATABASE_URL",
    )

    # --- Qdrant (vector store) ---
    qdrant_endpoint: str = Field(
        "http://localhost:6333", validation_alias="QDRANT_ENDPOINT"
    )
    qdrant_api_key: str | None = Field(None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(
        "aifya_knowledge", validation_alias="QDRANT_COLLECTION"
    )

    # --- Embedding ---
    embedding_model: str = Field(
        "BAAI/bge-m3", validation_alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(1024, validation_alias="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(32, validation_alias="EMBEDDING_BATCH_SIZE")

    # --- MinIO (document storage) ---
    minio_endpoint: str = Field(
        "localhost:9000", validation_alias="MINIO_ENDPOINT"
    )
    minio_access_key: str = Field(
        "aifyaadmin", validation_alias="MINIO_ACCESS_KEY"
    )
    minio_secret_key: str = Field(
        "miniosupersecret", validation_alias="MINIO_SECRET_KEY"
    )
    minio_bucket: str = Field(
        "aifya-knowledge", validation_alias="MINIO_KNOWLEDGE_BUCKET"
    )
    minio_secure: bool = Field(False, validation_alias="MINIO_SECURE")

    # --- Storage backend ---
    # "minio" -> S3-compatible object storage (the docker-compose stack).
    # "local" -> plain files under local_storage_path. Needs no Docker, which
    #            is what lets the Knowledge tab work on a single machine.
    # Left blank it resolves to "minio" in production and "local" in
    # development, so the service boots without an object store.
    storage_backend: str = Field("", validation_alias="STORAGE_BACKEND")
    local_storage_path: str = Field(
        "", validation_alias="KNOWLEDGE_STORAGE_PATH"
    )

    # --- Vector store backend ---
    # "postgres" -> chunk embeddings live in knowledge_chunks.embedding and
    #               similarity is a SQL dot product. No extra service and no
    #               extra Python wheel, which is why it is the default.
    # "qdrant"   -> an external Qdrant server (the docker-compose stack).
    # "local"    -> qdrant-client's embedded on-disk mode. Needs no Docker,
    #               but holds an exclusive lock on qdrant_local_path, so it
    #               must be paired with INGEST_MODE=inline.
    vector_backend: str = Field("", validation_alias="VECTOR_BACKEND")
    qdrant_local_path: str = Field("", validation_alias="QDRANT_LOCAL_PATH")

    # --- Ingestion ---
    # "celery" -> hand parsing/embedding to the Redis-backed worker.
    # "inline" -> run the pipeline inside the upload request. Needs no Redis.
    ingest_mode: str = Field("", validation_alias="INGEST_MODE")

    # --- Embeddings ---
    # "auto" -> sentence-transformers when torch is importable, otherwise a
    #           deterministic hashed bag-of-words fallback so documents still
    #           ingest and keyword retrieval still returns hits.
    embedding_backend: str = Field(
        "auto", validation_alias="EMBEDDING_BACKEND"
    )

    # --- vLLM (generation) ---
    vllm_base_url: str = Field(
        "http://localhost:8002/v1", validation_alias="VLLM_BASE_URL"
    )
    generation_model: str = Field(
        "Qwen/Qwen2.5-72B-Instruct", validation_alias="GENERATION_MODEL"
    )
    generation_max_tokens: int = Field(
        2048, validation_alias="GENERATION_MAX_TOKENS"
    )
    generation_temperature: float = Field(
        0.1, validation_alias="GENERATION_TEMPERATURE"
    )
    # Any OpenAI-compatible endpoint works: vLLM, DeepSeek, OpenAI, Ollama.
    generation_api_key: str = Field(
        "", validation_alias="GENERATION_API_KEY"
    )

    # --- RAG settings ---
    chunk_size: int = Field(512, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(64, validation_alias="CHUNK_OVERLAP")
    retrieval_top_k: int = Field(8, validation_alias="RETRIEVAL_TOP_K")
    rerank_top_k: int = Field(4, validation_alias="RERANK_TOP_K")
    similarity_threshold: float = Field(
        0.45, validation_alias="SIMILARITY_THRESHOLD"
    )

    # --- Celery ---
    celery_broker_url: str = Field(
        "redis://localhost:6379/3", validation_alias="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        "redis://localhost:6379/4", validation_alias="CELERY_RESULT_BACKEND"
    )

    # --- Rate limiting ---
    rate_limit_per_minute: int = Field(
        60, validation_alias="RATE_LIMIT_PER_MINUTE"
    )

    # --- Upload limits ---
    # 0 (the default) means no size limit: Aifya accepts documents of any
    # size. Set MAX_FILE_SIZE_MB to a positive number to re-impose a cap.
    max_file_size_mb: int = Field(0, validation_alias="MAX_FILE_SIZE_MB")
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".doc", ".txt", ".md", ".rtf"],
    )

    # --- CORS ---
    # Held as the raw comma-separated string. pydantic-settings decodes any
    # list-typed field as JSON, which rejects the plain "a,b" form that both
    # .env and docker-compose use, and crashed startup as soon as CORS_ORIGINS
    # was set at all. cors_origin_list does the splitting.
    cors_origins: str = Field(
        "http://localhost:3000", validation_alias="CORS_ORIGINS"
    )

    @field_validator("debug", mode="before")
    @classmethod
    def _coerce_debug(cls, value: object) -> object:
        """
        Interpret DEBUG leniently.

        DEBUG is an extremely common variable name, so an unrelated tool
        exporting something like DEBUG=release must not stop the service from
        booting. Anything unrecognised is treated as off.

        @param value: Raw value from the environment
        @returns True/False for strings, otherwise the value unchanged
        """
        if not isinstance(value, str):
            return value
        lowered = value.strip().lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
        return False

    @property
    def cors_origin_list(self) -> list[str]:
        """
        Allowed browser origins.

        @returns Origins parsed from the comma-separated CORS_ORIGINS value
        """
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def knowledge_root(self) -> Path:
        """
        Directory holding this service's on-disk state.

        @returns Absolute path to the knowledge service package root
        """
        return _backend_root

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def _resolve_backends_and_reject_insecure_defaults(self) -> "Settings":
        """
        Resolve the backend defaults, then crash on startup if critical
        secrets still use placeholder values outside development.

        Development resolves to the Docker-free backends (local files,
        embedded Qdrant, inline ingestion) so the Knowledge tab runs with
        nothing but PostgreSQL. Production keeps the compose-stack defaults.

        @returns The resolved Settings instance
        """
        is_dev = self.app_env == "development"
        if not self.storage_backend:
            self.storage_backend = "local" if is_dev else "minio"
        if not self.vector_backend:
            self.vector_backend = "postgres" if is_dev else "qdrant"
        if not self.ingest_mode:
            self.ingest_mode = "inline" if is_dev else "celery"
        if not self.local_storage_path:
            self.local_storage_path = str(_backend_root / "data" / "files")
        if not self.qdrant_local_path:
            self.qdrant_local_path = str(_backend_root / "data" / "qdrant")

        allowed = {
            "storage_backend": (self.storage_backend, {"minio", "local"}),
            "vector_backend": (
                self.vector_backend,
                {"postgres", "qdrant", "local"},
            ),
            "ingest_mode": (self.ingest_mode, {"inline", "celery"}),
            "embedding_backend": (
                self.embedding_backend,
                {"auto", "sentence-transformers", "hashing"},
            ),
        }
        for name, (value, choices) in allowed.items():
            if value not in choices:
                raise ValueError(
                    f"{name} must be one of {sorted(choices)}, got '{value}'"
                )

        if not is_dev:
            if self.storage_backend == "minio":
                if self.minio_access_key in _INSECURE_DEFAULTS:
                    raise ValueError(
                        "MINIO_ACCESS_KEY must be set to a secure value in non-development environments."
                    )
                if self.minio_secret_key in _INSECURE_DEFAULTS:
                    raise ValueError(
                        "MINIO_SECRET_KEY must be set to a secure value in non-development environments."
                    )
            if "change_me" in self.database_url.lower():
                raise ValueError(
                    "DATABASE_URL must be set to a real connection string in non-development environments."
                )
            if self.auth_provider == "internal" and not self.secret_key:
                raise ValueError(
                    "SECRET_KEY must be set when AUTH_PROVIDER=internal, or the knowledge service cannot verify any token."
                )
        return self


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.

    @returns Settings instance
    """
    return Settings()