"""Application configuration using Pydantic settings."""

from functools import lru_cache
from secrets import token_urlsafe
from typing import Literal

from pydantic import field_validator, model_validator
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
    database_url: str = ""  # Required - validated in model_validator

    # Azure AD Authentication
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""
    azure_ad_client_secret: str = ""
    azure_ad_redirect_uri: str = "http://localhost:6701/api/v1/auth/callback"

    # Application
    secret_key: str = ""  # Will be validated and set default in model_validator
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

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

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_storage_uri: str = (
        "memory://"  # Use "redis://localhost:6379" for production
    )
    rate_limit_search: str = "100/minute"
    rate_limit_crud: str = "60/minute"
    rate_limit_upload: str = "10/minute"
    rate_limit_admin: str = "30/minute"
    rate_limit_auth: str = "20/minute"
    rate_limit_default: str = "60/minute"
    rate_limit_feedback: str = "5/hour"  # Feedback submission limit

    # Embedding Cache (Redis - Optional)
    redis_url: str = ""  # Optional - falls back to in-memory if not set
    embedding_cache_ttl: int = 86400  # 24 hours in seconds
    embedding_cache_maxsize: int = 10000  # Max entries (for in-memory fallback)

    # Search Cache (Redis - Optional)
    search_cache_ttl: int = 300  # 5 minutes in seconds
    search_cache_enabled: bool = True  # Allow disabling cache

    # ClamAV Antivirus (optional)
    clamav_enabled: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    clamav_timeout: int = 30  # seconds
    clamav_scan_on_upload: bool = True  # When enabled, scan files during upload
    clamav_fail_open: bool = True  # If True, allow upload when scan fails/unavailable

    # Logging
    log_level: str = "INFO"

    # Anthropic/Claude Integration
    anthropic_api_key: str = ""
    claude_code_path: str = "claude"  # Path to Claude Code CLI

    # GitHub Integration (for issue creation)
    github_api_token: str = ""
    github_owner: str = "PaultheAICoder"
    github_repo: str = "NovusProjectDatabase"
    github_webhook_secret: str = ""  # For webhook signature verification

    # Feedback Email Integration
    feedback_email: str = ""  # e.g., ai-coder@vital-enterprises.com

    # Cron Job Security
    cron_secret: str = ""  # Bearer token for cron endpoint authentication

    # Monday.com Integration
    monday_api_key: str = ""  # API key from Monday.com admin
    monday_api_version: str = "2024-10"  # API version
    monday_contacts_board_id: str = ""  # Board ID containing contacts
    monday_organizations_board_id: str = ""  # Board ID containing organizations

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase."""
        return v.upper() if isinstance(v, str) else "INFO"

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

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """Validate security-critical settings based on environment."""
        import warnings

        # Generate secure secret_key if not provided
        if not self.secret_key:
            self.secret_key = token_urlsafe(32)
            if self.environment != "development":
                warnings.warn(
                    "SECRET_KEY not set - using auto-generated key. "
                    "Set SECRET_KEY environment variable for production.",
                    stacklevel=2,
                )

        # Validate secret_key length
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")

        # Production environment requires explicit configuration
        if self.environment == "production":
            errors = []

            if not self.database_url:
                errors.append("DATABASE_URL is required in production")

            if not self.azure_ad_tenant_id or self.azure_ad_tenant_id.startswith(
                "your-"
            ):
                errors.append("AZURE_AD_TENANT_ID is required in production")

            if not self.azure_ad_client_id or self.azure_ad_client_id.startswith(
                "your-"
            ):
                errors.append("AZURE_AD_CLIENT_ID is required in production")

            if (
                not self.azure_ad_client_secret
                or self.azure_ad_client_secret.startswith("your-")
            ):
                errors.append("AZURE_AD_CLIENT_SECRET is required in production")

            if errors:
                raise ValueError(
                    "Production configuration errors:\n"
                    + "\n".join(f"  - {e}" for e in errors)
                )

        # Development/staging: provide sensible defaults and warnings
        if self.environment == "development" and not self.database_url:
            self.database_url = "postgresql+asyncpg://npd:npd@localhost:6702/npd"

        return self

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_ai_configured(self) -> bool:
        """Check if AI enhancement is available."""
        return bool(self.anthropic_api_key)

    @property
    def is_graph_email_configured(self) -> bool:
        """Check if Graph email is configured."""
        return bool(
            self.azure_ad_tenant_id
            and self.azure_ad_client_id
            and self.azure_ad_client_secret
            and self.feedback_email
        )

    @property
    def is_monday_configured(self) -> bool:
        """Check if Monday.com integration is configured."""
        return bool(self.monday_api_key)

    @property
    def is_redis_configured(self) -> bool:
        """Check if Redis is configured for embedding cache."""
        return bool(self.redis_url)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
