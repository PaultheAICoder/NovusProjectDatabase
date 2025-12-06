"""Application configuration using Pydantic settings."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://npd:npd@localhost:6702/npd"

    # Azure AD Authentication
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""
    azure_ad_client_secret: str = ""
    azure_ad_redirect_uri: str = "http://localhost:6701/api/v1/auth/callback"

    # Application
    secret_key: str = "change-me-in-production-min-32-chars"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # Ollama
    ollama_base_url: str = "http://localhost:6703"
    ollama_embedding_model: str = "nomic-embed-text"

    # File Storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50

    # CORS
    cors_origins: list[str] = ["http://localhost:6700"]

    # Allowed email domains (empty = allow all from tenant)
    allowed_email_domains: list[str] = ["novuslabs.com"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle JSON-like string from env var
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("allowed_email_domains", mode="before")
    @classmethod
    def parse_allowed_email_domains(cls, v: str | list[str]) -> list[str]:
        """Parse allowed email domains from string or list."""
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [domain.strip().lower() for domain in v.split(",")]
        return [d.lower() for d in v]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
