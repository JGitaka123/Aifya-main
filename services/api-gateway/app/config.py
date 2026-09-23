import re
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings

# Sentinel values that must be overridden via environment / .env
_INSECURE_DEFAULTS = {
    "change_me_use_openssl_rand_hex_32",
    "change_me_in_production",
    "replace_with_openssl_rand_hex_32",
    "replace_with_local_dev_password",
    "postgresql+asyncpg://aifya_user:change_me_in_production@localhost:5432/aifya",
    "postgresql+asyncpg://aifya_user:replace_with_local_dev_password@localhost:5432/aifya",
}

# Google shows an app password as four groups of four characters. Users paste
# it with those spaces (often non-breaking ones); Gmail's SMTP server wants the
# sixteen characters without them.
_APP_PASSWORD_RE = re.compile(r"^(?:[A-Za-z0-9]{4}\s+){3}[A-Za-z0-9]{4}$")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://aifya_user:change_me_in_production@localhost:5432/aifya"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"

    # Auth (Keycloak)
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "aifya"
    keycloak_client_id: str = "aifya-api"
    secret_key: str = "change_me_use_openssl_rand_hex_32"

    # Keycloak Admin API (service account) — used to provision users for
    # facility onboarding and staff invites. Leave blank to disable
    # provisioning (endpoints then return 503 with a clear message).
    keycloak_admin_client_id: str = "aifya-admin"
    keycloak_admin_client_secret: str = ""

    # Auth mode. "keycloak" keeps the external Keycloak OIDC flow; "internal"
    # makes Aifya's own login/registration forms authenticate against this
    # database with self-issued HS256 tokens (no Keycloak server required).
    auth_provider: str = "internal"

    # Internal-mode first-run bootstrap (AUTH_PROVIDER=internal). When the
    # password is set and no admin@aifya.health account exists yet, startup
    # creates the platform super-admin facility + account so the first login
    # has somewhere to go. Leave the password blank to skip bootstrap.
    internal_bootstrap_email: str = "admin@aifya.health"
    internal_bootstrap_password: str = ""
    internal_bootstrap_facility_name: str = "Aifya Platform"

    # Keycloak-mode first-run bootstrap. The realm import
    # (infrastructure/keycloak/aifya-realm.json) stamps its seeded users with a
    # facility_id attribute, but that UUID has no row in this database, so a
    # first Keycloak login would resolve to an empty, unlicensed tenant and
    # every module-gated page would come back 403. On startup in Keycloak mode
    # this facility is created once, together with a staff row for
    # INTERNAL_BOOTSTRAP_EMAIL, so the seeded realm users have somewhere usable
    # to land. Leave the email blank to skip the bootstrap.
    keycloak_bootstrap_facility_id: str = "00000000-0000-0000-0000-000000000001"
    # The user id the realm import gives its seeded admin (realm JSON "id"),
    # so the created staff row matches the Keycloak subject claim.
    keycloak_bootstrap_user_id: str = "00000000-0000-0000-0000-000000000011"

    # Facility onboarding. When false (default) a facility sign-up creates a
    # PENDING request that a super-admin must approve before the admin user is
    # provisioned; when true, sign-ups are auto-approved (dev/self-serve).
    facility_signup_auto_approve: bool = False
    # License tier issued automatically to newly approved facilities
    # (community | professional | enterprise | government). Government
    # unlocks every module plus multi-facility features.
    facility_signup_tier: Literal[
        "community", "professional", "enterprise", "government"
    ] = "government"
    # Roles permitted to approve facility sign-ups and see the pending queue.
    super_admin_roles: str = "admin"

    # Public beta access. Keep disabled by default; production beta can opt in
    # with BETA_PUBLIC_ACCESS=true while sign-in is intentionally paused.
    beta_public_access: bool = False
    beta_user_id: str = "00000000-0000-0000-0000-000000000002"
    beta_facility_id: str = "00000000-0000-0000-0000-000000000001"
    beta_user_email: str = "beta@aifyamed.com"
    beta_user_name: str = "Aifya Beta Tester"
    beta_user_roles: str = (
        "admin,facility_admin,doctor,nurse,clinician,pharmacist,billing,hr,"
        "radiologist,rad_tech"
    )

    # AI Service
    ai_service_url: str = "http://localhost:8010"
    vllm_medgemma_url: str = "http://localhost:8004/v1"
    vllm_qwen_72b_url: str = "http://localhost:8002/v1"

    # DeepSeek API (OpenAI-compatible). The in-app help bot uses
    # DEEPSEEK_API_KEY when set, so it can answer general questions
    # (system help, greetings, jokes, education) without a local AI service.
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # M-Pesa Daraja
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    mpesa_passkey: str = ""
    mpesa_callback_url: str = "https://api.aifya.co.ke/api/v1/mpesa/callback"
    mpesa_environment: str = "sandbox"
    # Callback source-IP enforcement. Secure by default: callbacks are
    # rejected unless they originate from Safaricom's ranges (built-in) plus
    # any extra IPs/CIDRs in mpesa_callback_ip_allowlist. Disable only in
    # dev/test where the source is not Safaricom.
    mpesa_callback_ip_enforce: bool = True
    mpesa_callback_ip_allowlist: str = ""

    # SHA (Social Health Authority)
    sha_api_url: str = ""
    sha_api_key: str = ""
    # SHA e-claims submission endpoint (AfyaLink). When unset, submission
    # runs in mock mode and returns a clearly-labelled mock reference.
    sha_eclaims_url: str = ""
    sha_eclaims_api_key: str = ""

    # ClaimFlow rule-engine validator service (SHA claim pre-submission checks).
    claimflow_validator_url: str = ""

    # Africa's Talking Bulk SMS
    at_username: str = ""
    at_api_key: str = ""
    at_sender_id: str = "AIFYA"
    at_sandbox: bool = False

    # WhatsApp patient messaging. Two providers are supported — set the
    # credentials for whichever one the facility uses:
    #   * Green API  -> wa_instance_id + wa_access_token
    #   * Meta Cloud -> wa_access_token + wa_phone_number_id
    wa_instance_id: str = ""

    # WhatsApp patient messaging (Meta WhatsApp Business Cloud API).
    # Leave the token blank to disable real delivery; the channel then
    # reports a clear "not configured" error instead of pretending to send.
    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_business_account_id: str = ""

    # Outbound patient email (SMTP with STARTTLS). Same rule as WhatsApp:
    # blank host means the channel reports "not configured".
    smtp_host: str = ""
    smtp_port: int = 587
    # Gmail and most providers label this "SMTP_USER" in their own UI, so
    # accept both spellings instead of silently leaving email unconfigured.
    smtp_username: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_USERNAME", "SMTP_USER", "smtp_username"),
    )
    smtp_password: str = ""
    # EMAIL_FROM is the name used by most mailer examples; keep it working.
    smtp_from_email: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SMTP_FROM_EMAIL", "EMAIL_FROM", "SMTP_FROM", "smtp_from_email"
        ),
    )
    smtp_from_name: str = "Aifya"
    smtp_use_tls: bool = True

    # Field-level encryption for sensitive columns at rest (Kenya DPA).
    # When blank, a key is derived from SECRET_KEY. Set an explicit,
    # independently-rotatable key in production and document custody.
    field_encryption_key: str = ""

    # Observability — Sentry is enabled only when a DSN is provided.
    sentry_dsn: str = ""
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.1

    # Patient PII read gating (Kenya DPA — minimum-necessary access).
    # Comma-separated roles allowed to READ patient PII / FHIR resources.
    # Blank (default) preserves current behaviour: any authenticated
    # facility user may read. Set it to restrict reads to specific roles
    # (writes are already role-gated at the router level).
    patient_read_roles: str = ""

    # App
    debug: bool = False
    facility_timezone: str = "Africa/Nairobi"
    cors_origins: str = "http://localhost:3000"

    @field_validator("*", mode="before")
    @classmethod
    def _clean_env_value(cls, value: Any, info: ValidationInfo) -> Any:
        """
        Normalise a raw value coming from the environment or ``.env``.

        Credentials pasted into ``.env`` routinely keep a trailing space or a
        non-breaking space (Gmail's app-password UI is the usual culprit). That
        makes an otherwise correct credential fail with an opaque provider
        error, so every string setting is trimmed and Google's app-password
        grouping spaces are dropped.

        @param value: Raw value from the environment or ``.env``
        @param info: Validation context, used to identify the field
        @returns The cleaned value, or the input unchanged when not a string
        """
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if info.field_name == "smtp_password" and _APP_PASSWORD_RE.match(cleaned):
            cleaned = re.sub(r"\s+", "", cleaned)
        return cleaned

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def mpesa_base_url(self) -> str:
        """
        Derive Daraja API base URL from environment.

        @returns Production URL if mpesa_environment is "production", else sandbox
        """
        if self.mpesa_environment == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a comma-separated list."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def patient_read_role_list(self) -> list[str]:
        """Return configured patient-read roles (empty = unrestricted)."""
        return [
            role.strip()
            for role in self.patient_read_roles.split(",")
            if role.strip()
        ]

    @property
    def beta_user_role_list(self) -> list[str]:
        """Return roles granted to the public beta API user."""
        return [
            role.strip()
            for role in self.beta_user_roles.split(",")
            if role.strip()
        ]

    @property
    def super_admin_role_list(self) -> list[str]:
        """Return roles permitted to approve facility sign-ups."""
        return [
            role.strip()
            for role in self.super_admin_roles.split(",")
            if role.strip()
        ]

    @model_validator(mode="after")
    def _reject_insecure_defaults(self) -> "Settings":
        """Crash on startup if critical secrets still use placeholder defaults."""
        if not self.debug:
            if self.secret_key in _INSECURE_DEFAULTS:
                raise ValueError(
                    "SECRET_KEY must be set to a secure random value. "
                    "Generate one with: "
                    "python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if self.database_url in _INSECURE_DEFAULTS:
                raise ValueError(
                    "DATABASE_URL must be set to a real connection string. "
                    "Do not use the placeholder default in production."
                )
        return self


settings = Settings()
