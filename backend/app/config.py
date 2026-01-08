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

    # Database Connection Pool (optimized for 1000+ projects scale)
    db_pool_size: int = 10  # Increased from 5 for concurrent user handling
    db_max_overflow: int = 20  # Increased from 10 for burst handling
    db_pool_timeout: int = 30  # Seconds to wait for connection from pool
    db_pool_recycle: int = 1800  # Recycle connections after 30 minutes

    # Azure AD Authentication
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""
    azure_ad_client_secret: str = ""
    azure_ad_redirect_uri: str = "http://localhost:6701/api/v1/auth/callback"

    # Azure AD Role Mapping
    # The Azure AD role name that maps to UserRole.ADMIN
    # Case-insensitive comparison is performed
    azure_ad_admin_role: str = "admin"

    # Application
    secret_key: str = ""  # Will be validated and set default in model_validator
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Ollama
    ollama_base_url: str = "http://localhost:6703"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_chat_model: str = "mistral"  # LLM for NL query parsing

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
    rate_limit_webhook: str = "100/minute"  # Webhook endpoint limit (external systems)

    # Embedding Cache (Redis - Optional)
    redis_url: str = ""  # Optional - falls back to in-memory if not set
    embedding_cache_ttl: int = 86400  # 24 hours in seconds
    embedding_cache_maxsize: int = 10000  # Max entries (for in-memory fallback)

    # Search Cache (Redis - Optional)
    search_cache_ttl: int = 300  # 5 minutes in seconds
    search_cache_enabled: bool = True  # Allow disabling cache

    # Tag/Organization Cache (Redis - Optional)
    tag_cache_ttl: int = 3600  # 1 hour in seconds
    tag_cache_enabled: bool = True
    org_cache_ttl: int = 900  # 15 minutes in seconds
    org_cache_enabled: bool = True
    dashboard_cache_ttl: int = 300  # 5 minutes in seconds
    dashboard_cache_enabled: bool = True

    # ClamAV Antivirus (optional)
    clamav_enabled: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    clamav_timeout: int = 30  # seconds
    clamav_scan_on_upload: bool = True  # When enabled, scan files during upload
    clamav_fail_open: bool = True  # If True, allow upload when scan fails/unavailable

    # ClamAV Connection Pool
    clamav_pool_size: int = 5  # Number of pooled connections
    clamav_pool_timeout: int = 10  # Seconds to wait for connection from pool
    clamav_connection_max_age: int = 300  # Max connection age in seconds (5 min)

    # ClamAV Streaming Settings
    clamav_chunk_size: int = 8192  # Bytes per chunk for INSTREAM protocol
    clamav_max_stream_size: int = 26214400  # Max file size for scanning (25MB default)

    # Apache Tika (legacy .doc file extraction)
    tika_enabled: bool = False  # Feature flag - disabled by default
    tika_url: str = "http://localhost:9998"
    tika_timeout: int = 60  # seconds - longer timeout for large files

    # OCR (Optical Character Recognition)
    ocr_enabled: bool = False  # Feature flag - disabled by default
    ocr_language: str = "eng"  # Tesseract language pack
    ocr_dpi: int = 300  # Resolution for page rendering
    ocr_timeout_seconds: int = 60  # Per-page timeout
    ocr_max_pages: int = 200  # Maximum pages to OCR
    ocr_confidence_threshold: float = 0.3  # Below this, mark as low quality
    ocr_preprocess_enabled: bool = True  # Image enhancement before OCR

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

    # Monday.com Webhook Settings
    monday_webhook_secret: str = ""  # Signing secret for webhook JWT verification
    monday_webhook_enabled: bool = True  # Enable/disable webhook processing

    # Jira Integration
    jira_base_url: str = ""  # e.g., "https://company.atlassian.net"
    jira_user_email: str = ""  # User email for basic auth
    jira_api_token: str = ""  # API token from Atlassian account
    jira_cache_ttl: int = 3600  # Cache TTL for Jira status in seconds (default: 1 hour)

    # SharePoint Integration
    sharepoint_enabled: bool = False  # Feature flag to enable SharePoint storage
    sharepoint_site_url: str = ""  # e.g., "https://contoso.sharepoint.com/sites/NPD"
    sharepoint_drive_id: str = ""  # Document library drive ID from Graph API
    sharepoint_base_folder: str = "/NPD/projects"  # Base folder path in SharePoint
    sharepoint_client_id: str = ""  # Can reuse Azure AD client or use separate app
    sharepoint_client_secret: str = ""  # Client secret for SharePoint app
    sharepoint_tenant_id: str = ""  # Can default to azure_ad_tenant_id if not set

    # E2E Testing (only enable in test environment)
    # SECURITY: These settings have defense-in-depth protections:
    # 1. e2e_test_mode is blocked in production environment (validated below)
    # 2. e2e_test_secret is required in non-development environments
    e2e_test_mode: bool = False
    e2e_test_secret: str = ""  # Required when e2e_test_mode is True (except in dev)

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

            # Check for localhost in CORS origins
            if any("localhost" in origin.lower() for origin in self.cors_origins):
                errors.append(
                    "CORS_ORIGINS contains localhost - use production domain(s)"
                )

            # Check for in-memory rate limit storage (doesn't work across workers)
            if self.rate_limit_enabled and self.rate_limit_storage_uri == "memory://":
                errors.append(
                    "RATE_LIMIT_STORAGE_URI is 'memory://' - use Redis "
                    "(e.g., 'redis://localhost:6379') for rate limiting to work "
                    "across multiple workers"
                )

            if errors:
                raise ValueError(
                    "Production configuration errors:\n"
                    + "\n".join(f"  - {e}" for e in errors)
                )

        # E2E test mode security validation (defense-in-depth)
        # Layer 1: Block E2E test mode in production entirely
        if self.environment == "production" and self.e2e_test_mode:
            raise ValueError(
                "E2E_TEST_MODE cannot be enabled in production environment. "
                "This is a security protection against accidental misconfiguration."
            )

        # Layer 2: Require secret in non-development environments
        if (
            self.e2e_test_mode
            and not self.e2e_test_secret
            and self.environment != "development"
        ):
            raise ValueError(
                "E2E_TEST_SECRET is required when E2E_TEST_MODE is enabled "
                "outside of development environment."
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
    def is_monday_webhook_configured(self) -> bool:
        """Check if Monday.com webhook is configured."""
        return bool(self.monday_webhook_secret and self.monday_webhook_enabled)

    @property
    def is_jira_configured(self) -> bool:
        """Check if Jira integration is configured."""
        return bool(self.jira_base_url and self.jira_user_email and self.jira_api_token)

    @property
    def is_sharepoint_configured(self) -> bool:
        """Check if SharePoint integration is configured."""
        return bool(
            self.sharepoint_enabled
            and self.sharepoint_site_url
            and self.sharepoint_drive_id
            and (self.sharepoint_client_id or self.azure_ad_client_id)
            and (self.sharepoint_client_secret or self.azure_ad_client_secret)
        )

    @property
    def is_redis_configured(self) -> bool:
        """Check if Redis is configured for embedding cache."""
        return bool(self.redis_url)

    @property
    def is_tika_configured(self) -> bool:
        """Check if Tika is enabled and configured."""
        return self.tika_enabled

    @property
    def is_ocr_configured(self) -> bool:
        """Check if OCR is enabled."""
        return self.ocr_enabled


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
