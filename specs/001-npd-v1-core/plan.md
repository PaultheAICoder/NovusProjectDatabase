# Implementation Plan: Novus Project Database v1 Core

**Branch**: `001-npd-v1-core` | **Date**: 2025-12-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-npd-v1-core/spec.md`
**PRD**: [Novus Database PRD v1.md](../../Novus%20Database%20PRD%20v1.md)

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build Novus Project Database v1 — an internal web application for Novus staff to manage project records, attach and search documents, classify with tags, and leverage RAG-assisted import. Core capabilities include project CRUD, document storage with full-text indexing, keyword search with filters, AD SSO authentication, saved searches, and bulk import with AI-suggested field values.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend), React 19
**Backend Framework**: FastAPI with SQLAlchemy, Pydantic, Alembic migrations
**Frontend Framework**: Vite + React 19 + TypeScript
**UI Library**: shadcn/ui + Tailwind CSS + React Hook Form + Zod + TanStack Query + TanStack Table
**Storage**: PostgreSQL 15+ with pgvector extension + local file system (documents)
**Document Extraction**: pdfplumber (PDF), python-docx (DOCX), pandas + calamine (XLSX)
**RAG/Embeddings**: Ollama (nomic-embed-text) + hybrid search (ts_vector + pgvector + RRF)
**Authentication**: fastapi-azure-auth (Azure AD/Entra ID SSO via OIDC)
**Testing**: Backend: pytest + pytest-asyncio; Frontend: Vitest + React Testing Library; E2E: Playwright
**Target Platform**: Linux server (Docker recommended); Chrome/Edge on Windows desktop
**Project Type**: web (frontend + backend)
**Performance Goals**: Search queries <3s over 100-1000 projects; project detail pages <1s load time
**Constraints**: Internal network/VPN only; AD SSO required; 50MB max file upload; Chrome/Edge Windows only
**Scale/Scope**: ~100 projects v1, scaling to 1000+ v2; ~10-20 concurrent users; ~8 core screens

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Gate Evaluation

| Principle | Requirement | Status | Notes |
|-----------|-------------|--------|-------|
| I. Iterative Delivery | Features broken into independently deployable increments | ✅ PASS | User stories prioritized P1-P4; MVP slice is project CRUD + search |
| I. Iterative Delivery | MVP slices identified | ✅ PASS | P1: Project CRUD + Search; P2: Documents + Tags; P3: RAG import + Saved searches; P4: Billing + Export |
| II. PRD Alignment | All features trace to PRD | ✅ PASS | All FR-001 through FR-040 map to PRD §4-5 |
| II. PRD Alignment | v1 scope boundaries respected | ✅ PASS | No v2/v3 features (semantic search UX, Monday API, pipeline states) in scope |
| III. Usability First | Minimize clicks for core operations | ⏳ PENDING | Design phase will validate |
| III. Usability First | Reasonable defaults and auto-suggestions | ⏳ PENDING | RAG-assisted suggestions in scope |
| IV. Internal Security | AD-based SSO required | ✅ PASS | FR-001 requires AD SSO |
| IV. Internal Security | All users view all projects | ✅ PASS | FR-004 confirms no per-project ACL in v1 |
| IV. Internal Security | Corp network/VPN only | ✅ PASS | FR-039 requires internal-only access |
| V. Extensible Architecture | File storage abstracted | ⏳ PENDING | Design phase will define abstraction layer |
| V. Extensible Architecture | RAG infrastructure built for v1 | ✅ PASS | FR-028 requires chunking/embedding |
| V. Extensible Architecture | Audit fields from day one | ✅ PASS | FR-009 requires created_at/by, updated_at/by |

**Gate Result**: ✅ PASS — No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-npd-v1-core/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output - technology decisions
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - developer setup guide
├── contracts/           # Phase 1 output - API contracts
│   └── openapi.yaml     # OpenAPI 3.1 specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings and environment config
│   ├── database.py          # SQLAlchemy engine and session
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── contact.py
│   │   ├── project.py
│   │   ├── document.py
│   │   ├── tag.py
│   │   └── saved_search.py
│   ├── schemas/             # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── contact.py
│   │   ├── project.py
│   │   ├── document.py
│   │   ├── tag.py
│   │   └── search.py
│   ├── api/                 # FastAPI routers
│   │   ├── __init__.py
│   │   ├── deps.py          # Dependencies (auth, db session)
│   │   ├── auth.py          # Azure AD SSO endpoints
│   │   ├── projects.py
│   │   ├── organizations.py
│   │   ├── contacts.py
│   │   ├── documents.py
│   │   ├── tags.py
│   │   ├── search.py
│   │   └── admin.py
│   ├── services/            # Business logic layer
│   │   ├── __init__.py
│   │   ├── document_processor.py  # Text extraction
│   │   ├── embedding_service.py   # Ollama embeddings
│   │   ├── search_service.py      # Hybrid search
│   │   ├── import_service.py      # Bulk import + RAG suggestions
│   │   └── tag_suggester.py       # Tag deduplication
│   └── core/                # Shared utilities
│       ├── __init__.py
│       ├── auth.py          # Azure AD integration
│       └── storage.py       # File storage abstraction
├── alembic/                 # Database migrations
│   ├── versions/
│   └── env.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── api/
├── pyproject.toml
├── requirements.txt
└── Dockerfile

frontend/
├── src/
│   ├── main.tsx             # React entry point
│   ├── App.tsx              # Root component with router
│   ├── components/          # Reusable UI components
│   │   ├── ui/              # shadcn/ui components
│   │   ├── layout/          # Header, sidebar, etc.
│   │   ├── forms/           # Form components
│   │   └── tables/          # Data table components
│   ├── pages/               # Route pages
│   │   ├── Dashboard.tsx
│   │   ├── Projects.tsx
│   │   ├── ProjectDetail.tsx
│   │   ├── ProjectForm.tsx
│   │   ├── Organizations.tsx
│   │   ├── Contacts.tsx
│   │   ├── Search.tsx
│   │   ├── Import.tsx
│   │   └── Admin.tsx
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # Utilities and API client
│   │   ├── api.ts           # TanStack Query + fetch wrapper
│   │   └── utils.ts
│   └── types/               # TypeScript type definitions
├── tests/
│   ├── unit/
│   └── e2e/                 # Playwright tests
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json

docker-compose.yml           # PostgreSQL + Ollama + app services
uploads/                     # Document storage (mounted volume)
```

**Structure Decision**: Web application with separate frontend and backend. FastAPI backend serves REST API; Vite/React frontend is a standalone SPA. Services deployed via Docker Compose with PostgreSQL (+ pgvector) and Ollama as infrastructure dependencies.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations requiring justification.*

---

## Post-Design Constitution Check

*Re-evaluated after Phase 1 design completion.*

| Principle | Requirement | Status | Design Validation |
|-----------|-------------|--------|-------------------|
| I. Iterative Delivery | MVP slices deliverable independently | ✅ PASS | API contracts support incremental feature delivery; P1 (CRUD+Search) can ship without P2-P4 |
| II. PRD Alignment | No scope creep | ✅ PASS | All entities map to PRD §4; no v2/v3 features (semantic search UX, Monday API) in data model |
| III. Usability First | Minimize clicks for core ops | ✅ PASS | API supports batch operations; frontend pages designed for minimal navigation |
| III. Usability First | Reasonable defaults | ✅ PASS | Tag suggestions, auto-fill from documents included in API |
| IV. Internal Security | AD SSO required | ✅ PASS | fastapi-azure-auth with cookie-based sessions in API contract |
| IV. Internal Security | All users view all projects | ✅ PASS | No per-project ACL in data model; ready for v3 extension |
| V. Extensible Architecture | File storage abstracted | ✅ PASS | `core/storage.py` abstraction layer in project structure |
| V. Extensible Architecture | RAG infrastructure for v1 | ✅ PASS | DocumentChunk entity with pgvector embeddings; hybrid search in API |
| V. Extensible Architecture | Audit fields | ✅ PASS | created_at/by, updated_at/by on Project entity |
| V. Extensible Architecture | Pipeline states supportable | ✅ PASS | Status enum extensible; schema supports future states |

**Gate Result**: ✅ PASS — Design aligns with all Constitution principles.
