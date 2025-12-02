# novus-database Development Guidelines

Auto-generated from feature plans. Last updated: 2025-12-01

## Overview

Novus Project Database (NPD) — internal web application for project management, document storage, and RAG-assisted search.

## Active Technologies

### Backend (Python 3.11+)
- **Framework**: FastAPI with SQLAlchemy, Pydantic, Alembic
- **Database**: PostgreSQL 15+ with pgvector extension
- **Document Processing**: pdfplumber, python-docx, pandas
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

## Recent Changes

- 001-npd-v1-core: Initial implementation plan created (2025-12-01)

<!-- MANUAL ADDITIONS START -->
<!-- Add project-specific notes here that should persist across updates -->
<!-- MANUAL ADDITIONS END -->
