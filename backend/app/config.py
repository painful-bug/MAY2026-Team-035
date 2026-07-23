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
    supabase_jwt_secret: str = Field(..., alias="SUPABASE_JWT_SECRET")

    # Application behaviour.
    frontend_base_url: str = Field(
        "http://localhost:5173", alias="FRONTEND_BASE_URL"
    )
    invite_ttl_hours: int = Field(72, alias="INVITE_TTL_HOURS")
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


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
