"""Application configuration.

Settings are read once from the environment (or a local ``.env`` file) and cached.
Import :func:`get_settings` anywhere a value is needed rather than reading
``os.environ`` directly, so configuration has a single, typed source of truth.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase project credentials.
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_anon_key: str = Field(..., alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")
    # Legacy HS256 verification is deliberately opt-in. New projects should
    # use Supabase asymmetric signing keys and the project's JWKS endpoint.
    supabase_jwt_secret: str | None = Field(None, alias="SUPABASE_JWT_SECRET")

    # Application behaviour.
    frontend_base_url: str = Field(
        "http://localhost:5173", alias="FRONTEND_BASE_URL"
    )
    backend_base_url: str = Field(
        "http://localhost:8000", alias="BACKEND_BASE_URL"
    )
    cookie_signing_secret: str = Field(..., alias="COOKIE_SIGNING_SECRET")
    cookie_secure: bool | None = Field(None, alias="COOKIE_SECURE")
    invite_ttl_hours: int = Field(72, alias="INVITE_TTL_HOURS")
    auth_primary_method: str = Field("google", alias="AUTH_PRIMARY_METHOD")
    auth_enabled_methods: str = Field("google,email_password", alias="AUTH_ENABLED_METHODS")
    auth_session_idle_days: int = Field(30, ge=1, le=90, alias="AUTH_SESSION_IDLE_DAYS")
    auth_captcha_enabled: bool = Field(False, alias="AUTH_CAPTCHA_ENABLED")
    auth_email_confirmation_required: bool = Field(
        True, alias="AUTH_EMAIL_CONFIRMATION_REQUIRED"
    )
    auth_provider_timeout_seconds: float = Field(
        8.0, gt=0, alias="AUTH_PROVIDER_TIMEOUT_SECONDS"
    )
    community_search_default_limit: int = Field(10, alias="COMMUNITY_SEARCH_DEFAULT_LIMIT")
    community_search_max_limit: int = Field(20, alias="COMMUNITY_SEARCH_MAX_LIMIT")
    cors_origins: str = Field("http://localhost:5173", alias="CORS_ORIGINS")
    env: str = Field("development", alias="ENV")

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins parsed from the comma-separated env value."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        """True when running with production configuration."""
        return self.env.lower() == "production"

    @property
    def use_secure_cookies(self) -> bool:
        """Whether cookies require HTTPS (always true in production)."""
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def enabled_auth_methods(self) -> list[str]:
        """Configured methods in presentation order, with duplicates removed."""
        methods = [method.strip().lower() for method in self.auth_enabled_methods.split(",")]
        return list(dict.fromkeys(method for method in methods if method))

    def validate_auth_configuration(self) -> None:
        """Fail closed when the provider configuration is unsafe or unknown."""
        enabled = self.enabled_auth_methods
        if not enabled or self.auth_primary_method.lower() not in enabled:
            raise ValueError("AUTH_PRIMARY_METHOD must be one of AUTH_ENABLED_METHODS")
        unsupported = set(enabled) - {"google", "email_password"}
        if unsupported:
            raise ValueError(
                "Unsupported authentication methods configured: "
                + ", ".join(sorted(unsupported))
            )
        if self.is_production and not self.auth_email_confirmation_required:
            raise ValueError("Email confirmation must be enabled in production")


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
