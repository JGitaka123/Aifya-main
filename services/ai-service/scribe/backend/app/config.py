from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, BaseModel, model_validator
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend root
backend_root = Path(__file__).resolve().parent.parent
load_dotenv(backend_root / ".env")

# Sentinel values that must be replaced in non-development environments
_INSECURE_DEFAULTS = {
    "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32",
    "CHANGE_ME_IN_PRODUCTION",
    "miniosupersecret",
    "aifyaadmin",
}

class QAfyaConfig(BaseModel):
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "q-afya-hmis"
    db_user: str = "aifya_service_worker"
    db_password: str = ""
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60

class Settings(BaseSettings):
    # Environment
    app_env: str = Field("development", validation_alias="APP_ENV")
    debug: bool = Field(False, validation_alias="DEBUG")

    # Core API configs
    api_v1_str: str = "/api/v1"
    project_name: str = "Aifya Health Platform"

    # CORS
    cors_origins: str = Field("http://localhost:3000", validation_alias="CORS_ORIGINS")

    # Aifya Internal Database
    database_url: str = Field("postgresql://aifya:password@localhost:5432/aifya", validation_alias="DATABASE_URL")

    # Q-Afya External Database config (Mapped from env vars)
    qafya: QAfyaConfig = Field(default_factory=QAfyaConfig)

    # Auth configuration
    jwt_secret: str = Field("CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32", validation_alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(15, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(7, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # Keycloak SSO — platform (RS256) tokens are accepted alongside local
    # HS256 tokens when keycloak_url is configured. This lets the main
    # Aifya web session use ScribeAI without a second login.
    keycloak_url: str = Field("", validation_alias="KEYCLOAK_URL")
    keycloak_realm: str = Field("aifya", validation_alias="KEYCLOAK_REALM")
    keycloak_audience: str = Field("account", validation_alias="KEYCLOAK_AUDIENCE")

    # PII Encryption Key for PostgreSQL pgcrypto
    encryption_key: str = Field("CHANGE_ME_IN_PRODUCTION", validation_alias="ENCRYPTION_KEY")

    # OpenAI config
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")

    # MinIO Audio storage configs
    minio_endpoint: str = Field("localhost:9000", validation_alias="MINIO_ENDPOINT")
    minio_access_key: str = Field("aifyaadmin", validation_alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field("miniosupersecret", validation_alias="MINIO_SECRET_KEY")
    minio_audio_bucket: str = Field("aifya-audio", validation_alias="MINIO_AUDIO_BUCKET")
    minio_secure: bool = Field(True, validation_alias="MINIO_SECURE")

    # Rate limiting
    rate_limit_per_minute: int = Field(60, validation_alias="RATE_LIMIT_PER_MINUTE")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__"
    )

    def __init__(self, **values):
        super().__init__(**values)
        # Manual mapping for QAFYA_ env vars if they exist
        import os
        if os.getenv("QAFYA_DB_HOST"): self.qafya.db_host = os.getenv("QAFYA_DB_HOST")
        if os.getenv("QAFYA_DB_PORT"): self.qafya.db_port = int(os.getenv("QAFYA_DB_PORT"))
        if os.getenv("QAFYA_DB_NAME"): self.qafya.db_name = os.getenv("QAFYA_DB_NAME")
        if os.getenv("QAFYA_DB_USER"): self.qafya.db_user = os.getenv("QAFYA_DB_USER")
        if os.getenv("QAFYA_DB_PASSWORD"): self.qafya.db_password = os.getenv("QAFYA_DB_PASSWORD")
        if os.getenv("QAFYA_CB_THRESHOLD"): self.qafya.circuit_breaker_failure_threshold = int(os.getenv("QAFYA_CB_THRESHOLD"))
        if os.getenv("QAFYA_CB_TIMEOUT"): self.qafya.circuit_breaker_recovery_timeout = int(os.getenv("QAFYA_CB_TIMEOUT"))

    @model_validator(mode="after")
    def _reject_insecure_defaults(self) -> "Settings":
        """Crash on startup if critical secrets still use placeholder defaults in non-dev environments."""
        if self.app_env != "development":
            if self.jwt_secret in _INSECURE_DEFAULTS:
                raise ValueError(
                    "JWT_SECRET must be set to a secure random value in non-development environments. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if self.encryption_key in _INSECURE_DEFAULTS:
                raise ValueError(
                    "ENCRYPTION_KEY must be set to a secure random value in non-development environments. "
                    "This key protects PII data via pgcrypto."
                )
            if self.minio_access_key in _INSECURE_DEFAULTS or self.minio_secret_key in _INSECURE_DEFAULTS:
                raise ValueError(
                    "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set to secure values in non-development environments."
                )
        return self

@lru_cache()
def get_settings() -> Settings:
    return Settings()
