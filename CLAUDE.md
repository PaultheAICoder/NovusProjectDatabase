# novus-database Development Guidelines

Auto-generated from feature plans. Last updated: 2025-12-01

## Overview

Novus Project Database (NPD) — internal web application for project management, document storage, and RAG-assisted search.

## Active Technologies

### Backend (Python 3.11+)
- **Framework**: FastAPI with SQLAlchemy, Pydantic, Alembic
- **Database**: PostgreSQL 15+ with pgvector extension
- **Document Processing**: pdfplumber, python-docx, pandas, Apache Tika (for .doc)
- **RAG/Embeddings**: Ollama (nomic-embed-text)
- **Auth**: Azure AD SSO via fastapi-azure-auth

### Frontend (TypeScript 5.x)
- **Framework**: Vite + React 19
- **UI**: shadcn/ui + Tailwind CSS
- **Forms**: React Hook Form + Zod
- **State**: TanStack Query
- **Tables**: TanStack Table

## Project Structure

```text
backend/
├── app/
│   ├── main.py           # FastAPI entry point
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic schemas
│   ├── api/              # Route handlers
│   ├── services/         # Business logic
│   └── core/             # Auth, storage utilities
├── alembic/              # Database migrations
└── tests/

frontend/
├── src/
│   ├── components/       # UI components
│   ├── pages/            # Route pages
│   ├── hooks/            # Custom hooks
│   └── lib/              # API client, utilities
└── tests/

specs/001-npd-v1-core/    # Feature specification
├── spec.md               # Requirements
├── plan.md               # Implementation plan
├── research.md           # Technology decisions
├── data-model.md         # Entity schema
├── contracts/openapi.yaml # API contract
└── quickstart.md         # Setup guide
```

## Commands

### Backend
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload      # Dev server
pytest                              # Run tests
pytest --cov=app                    # With coverage
alembic upgrade head                # Apply migrations
ruff check app                      # Lint
black app tests                     # Format
```

### Frontend
```bash
cd frontend
pnpm dev                            # Dev server
pnpm test                           # Run tests
pnpm lint                           # Lint
pnpm format                         # Format
pnpm build                          # Production build
```

### Full Stack (Docker)
```bash
docker compose up -d                # Start all services
docker compose logs -f              # View logs
docker compose down -v              # Stop and clean
```

## Code Style

### Python
- Black formatter, 88 char line length
- Ruff linter
- Type hints required
- Async/await for I/O operations

### TypeScript/React
- Prettier formatter
- ESLint with React rules
- Strict TypeScript
- Functional components with hooks

## Key Design Decisions

1. **Hybrid Search**: PostgreSQL ts_vector + pgvector with RRF fusion
2. **File Storage**: Abstracted layer (local v1 → SharePoint v3)
3. **Auth**: Azure AD App Roles for user/admin distinction
4. **Chunking**: 512 tokens, 12% overlap for embeddings

## API Endpoints

- `GET/POST /api/v1/projects` — Project CRUD
- `GET/POST /api/v1/organizations` — Organization management
- `GET/POST /api/v1/contacts` — Contact management
- `POST /api/v1/projects/{id}/documents` — Document upload
- `GET /api/v1/search?q=...` — Hybrid search
- `GET/POST /api/v1/saved-searches` — Saved searches
- `POST /api/v1/import/upload` — Bulk import

See `specs/001-npd-v1-core/contracts/openapi.yaml` for full API spec.

## SharePoint Integration (Optional)

SharePoint Online can be used as the document storage backend instead of local filesystem.

### Configuration

```bash
# Required for SharePoint
SHAREPOINT_ENABLED=true
SHAREPOINT_SITE_URL=https://your-tenant.sharepoint.com/sites/NPD
SHAREPOINT_DRIVE_ID=<from-graph-explorer>

# Optional - falls back to Azure AD credentials if not set
SHAREPOINT_CLIENT_ID=<client-id>
SHAREPOINT_CLIENT_SECRET=<client-secret>
SHAREPOINT_TENANT_ID=<tenant-id>
```

### Migration from Local Storage

```bash
# Preview migration
python -m app.scripts.migrate_to_sharepoint --dry-run

# Run migration
python -m app.scripts.migrate_to_sharepoint --batch-size 50
```

See `specs/002-sharepoint-integration/` for detailed documentation:
- [azure-setup.md](specs/002-sharepoint-integration/azure-setup.md) - Azure AD app registration
- [sharepoint-setup.md](specs/002-sharepoint-integration/sharepoint-setup.md) - Site/library setup
- [configuration.md](specs/002-sharepoint-integration/configuration.md) - All environment variables
- [migration-runbook.md](specs/002-sharepoint-integration/migration-runbook.md) - Production migration steps
- [rollback.md](specs/002-sharepoint-integration/rollback.md) - Rollback procedures

## Legacy DOC Support (Optional)

Apache Tika enables text extraction from legacy Microsoft Word .doc files (Word 97-2003 format).

### Configuration

```bash
# Enable Tika in .env
TIKA_ENABLED=true
TIKA_URL=http://tika:9998   # Default in docker-compose
TIKA_TIMEOUT=60              # Seconds for extraction timeout
```

### Docker Setup

Tika is included in docker-compose.yml and starts automatically. No additional setup required.

```bash
# Verify Tika is running
curl http://localhost:6706/tika
```

See `specs/004-legacy-doc-support/` for detailed documentation:
- [configuration.md](specs/004-legacy-doc-support/configuration.md) - All environment variables
- [operations.md](specs/004-legacy-doc-support/operations.md) - Monitoring and troubleshooting
- [rollback.md](specs/004-legacy-doc-support/rollback.md) - Rollback procedures

## Recent Changes

- 004-legacy-doc-support: Legacy .doc file extraction via Apache Tika (2026-01-07)
- 002-sharepoint-integration: SharePoint storage backend implemented (2026-01-02)
- 001-npd-v1-core: Initial implementation plan created (2025-12-01)

<!-- MANUAL ADDITIONS START -->
<!-- Add project-specific notes here that should persist across updates -->
<!-- MANUAL ADDITIONS END -->
