"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import (
    admin,
    audit,
    auth,
    contacts,
    cron,
    documents,
    feedback,
    jobs,
    organizations,
    projects,
    search,
    tags,
    tokens,
    webhooks,
)
from app.config import get_settings
from app.core.auth import azure_scheme
from app.core.logging import (
    configure_logging,
    generate_request_id,
    get_logger,
    request_id_ctx,
)
from app.core.rate_limit import limiter
from app.services.antivirus import close_clamav_pool, init_clamav_pool

settings = get_settings()

# Configure structured logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Log environment info
    logger.info(
        "application_starting",
        environment=settings.environment,
        debug=settings.debug,
    )

    # Startup - only load Azure AD config if valid credentials are provided
    has_valid_azure_config = bool(
        settings.azure_ad_client_id
        and settings.azure_ad_tenant_id
        and settings.azure_ad_client_secret
    )

    if has_valid_azure_config:
        await azure_scheme.openid_config.load_config()
        logger.info("azure_ad_configured")
    else:
        logger.warning(
            "azure_ad_not_configured",
            message="Authentication endpoints will fail. "
            "Set AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID, and AZURE_AD_CLIENT_SECRET.",
        )

    # Initialize ClamAV connection pool (if enabled)
    await init_clamav_pool()

    yield

    # Shutdown
    # Close ClamAV connection pool
    await close_clamav_pool()

    logger.info("application_shutdown")


app = FastAPI(
    title="Novus Project Database API",
    description=(
        "Internal REST API for the Novus Project Database (NPD) v1. "
        "Provides project management, document storage, search, and "
        "RAG-assisted import capabilities."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Request correlation ID middleware
@app.middleware("http")
async def add_request_id_middleware(request, call_next):
    """Add correlation ID to each request."""
    request_id = generate_request_id()
    request_id_ctx.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(cron.router, prefix="/api/v1")
app.include_router(tokens.router, prefix="/api/v1")
app.include_router(tokens.admin_router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": "Novus Project Database API",
        "version": "1.0.0",
        "docs": "/docs" if settings.debug else "disabled",
    }
