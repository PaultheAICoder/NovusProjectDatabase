"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, contacts, documents, organizations, projects, search, tags
from app.config import get_settings
from app.core.auth import azure_scheme

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    if settings.azure_ad_client_id and settings.azure_ad_tenant_id:
        await azure_scheme.openid_config.load_config()
    yield
    # Shutdown


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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


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
