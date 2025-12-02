# Research: Novus Project Database v1 Core

**Branch**: `001-npd-v1-core` | **Date**: 2025-12-01

This document captures technology decisions and research findings to resolve NEEDS CLARIFICATION items from the implementation plan.

---

## 1. Backend Framework

**Decision**: Python 3.11+ with FastAPI

**Rationale**:
1. **Superior document processing ecosystem** — Python dominates with mature libraries (PyMuPDF, python-docx, openpyxl) that have 10+ years of refinement vs. less mature Node.js alternatives
2. **Excellent PostgreSQL + pgvector integration** — SQLAlchemy with pgvector provides native async support for I/O-intensive vector similarity searches
3. **Strong Azure AD SSO support** — fastapi-azure-auth, fastapi-msal, and fastapi-microsoft-identity are actively maintained and purpose-built for enterprise scenarios

**Alternatives considered**:
- **Django REST Framework**: Slower synchronous architecture, more boilerplate for simple REST APIs, overkill for a project-focused API without need for Django admin
- **Next.js API routes (TypeScript/Node.js)**: Inferior document processing libraries (officeparser/office-text-extractor lack maturity), pgvector requires raw SQL with Prisma

---

## 2. Frontend Framework

**Decision**: Vite + React 19 + TypeScript

**Rationale**:
1. **Fast development velocity** — 390ms startup vs 4.5s for Create React App; lightning-fast HMR
2. **Production-optimized** — Rollup generates optimized bundles with automatic code splitting
3. **Appropriate complexity** — SPA without SSR complexity (no SEO requirements for internal app)

**Alternatives considered**:
- **Create React App**: Effectively deprecated, slow build times, no longer recommended by React team
- **Next.js static export**: Adds framework complexity without benefits for internal SPA

---

## 3. UI Component Library

**Decision**: shadcn/ui + Tailwind CSS

**Rationale**:
1. **Full customization control** — Components copied into codebase, no vendor lock-in
2. **Bundle efficiency** — Only install what you use, no monolithic dependency
3. **Accessibility** — Built on Radix UI primitives (WAI-ARIA compliant)
4. **Ecosystem integration** — Official support for React Hook Form and TanStack libraries

**Alternatives considered**:
- **MUI**: Restrictive Material Design paradigm, 92KB bundle
- **Ant Design**: Limited customization, requires global CSS overrides
- **Chakra UI**: Less mature advanced components

---

## 4. Form Handling

**Decision**: React Hook Form + Zod

**Rationale**:
1. **Performance** — Uncontrolled components minimize re-renders (32% fewer than Formik)
2. **Type safety** — Excellent TypeScript inference with Zod schemas
3. **Bundle size** — 12KB vs Formik's 44KB
4. **Integration** — Native shadcn/ui form components built on React Hook Form

**Alternatives considered**:
- **Formik**: Unmaintained (no commits in 1+ year), slower, larger bundle

---

## 5. State Management

**Decision**: TanStack Query (React Query)

**Rationale**:
1. **CRUD-optimized** — Built-in mutations with cache invalidation
2. **Developer experience** — Excellent devtools, automatic background refetching
3. **Memory efficient** — Garbage collection prevents bloat from dynamic endpoints

**Alternatives considered**:
- **SWR**: Minimal API lacks garbage collection and advanced features
- **Redux**: Overkill for server state in CRUD apps, excessive boilerplate

---

## 6. Data Tables

**Decision**: TanStack Table + shadcn/ui table components

**Rationale**:
1. **Headless architecture** — Complete styling control, integrates with shadcn/ui
2. **Virtualization support** — react-window integration for large datasets
3. **No licensing costs** — MIT licensed vs AG Grid Enterprise pricing
4. **TypeScript** — Excellent type safety for column definitions

**Alternatives considered**:
- **AG Grid Community**: Missing critical features (row grouping, pinning)
- **AG Grid Enterprise**: Expensive licensing, vendor lock-in

---

## 7. Document Text Extraction

**Decision**: Mixed library stack
- **PDF**: pdfplumber (primary) + PyMuPDF (OCR fallback)
- **Word (.docx)**: python-docx
- **Word (.doc legacy)**: Apache Tika
- **Excel (.xlsx)**: pandas with python-calamine engine
- **Excel (.xls legacy)**: pandas with xlrd

**Rationale**:
1. **PDF strategy** — pdfplumber has BSD license (enterprise-friendly), excellent table extraction; PyMuPDF reserved for OCR only (AGPL license)
2. **Office documents** — python-docx is pure Python with no dependencies; pandas + calamine is 10x faster than openpyxl for large Excel files
3. **Legacy formats** — Apache Tika handles binary .doc/.xls formats that pure Python libraries cannot

**Alternatives considered**:
- **PyMuPDF as primary**: AGPL license requires open-sourcing or commercial license
- **Apache Tika everywhere**: Java runtime overhead, horizontal scaling complexity
- **textract**: Unmaintained since March 2022

---

## 8. Authentication (AD SSO)

**Decision**: fastapi-azure-auth with OIDC/OAuth2 (Azure AD/Entra ID)

**Rationale**:
1. **Hybrid compatibility** — Works with on-premises AD (via Azure AD Connect) and cloud Azure AD
2. **FastAPI-native** — Proper dependency injection, automatic OpenAPI integration
3. **Modern authentication** — OAuth2/OIDC standards with MFA and conditional access support
4. **Auto-provisioning** — JWT tokens contain user attributes for first-login provisioning

**Implementation notes**:
- Register app in Azure AD portal with redirect URI
- Configure App Roles (Admin, User) rather than raw group claims
- Store JWT in HttpOnly cookies with CSRF protection
- Extract user attributes from JWT claims on authentication

**Alternatives considered**:
- **MSAL (fastapi-msal)**: More complex setup, designed for Microsoft Graph API calls
- **python-ldap**: Requires C library compilation, exposes domain controllers, no modern auth features
- **Authlib**: Generic OAuth library requiring significant custom configuration

---

## 9. RAG Infrastructure (Embeddings + Search)

**Decision**: Hybrid search architecture
- **Embedding model**: nomic-embed-text via Ollama (local)
- **Chunking**: Recursive text splitter, 512 tokens, 12% overlap
- **Search**: PostgreSQL ts_vector (full-text) + pgvector (semantic) + RRF fusion

**Rationale**:
1. **Embedding model** — nomic-embed-text achieves 95.2 MTEB score (outperforms OpenAI ada-002), zero recurring costs, documents stay on-premises
2. **Chunking strategy** — 400-512 tokens achieves 85-90% recall; simpler than semantic chunking for v1
3. **Hybrid search** — Combines lexical precision with semantic understanding; RRF fusion requires no tuning
4. **Single database** — pgvector in PostgreSQL eliminates sync complexity with separate vector DB

**Implementation notes**:
- HNSW index for vector similarity (recommended over IVFFlat for <10M vectors)
- RRF formula: `score = 1/(rank + 60)` for each result set
- Ollama deployment: ~274MB for embedding model, 4-7GB for LLM (summarization)
- Batch embedding generation for bulk imports

**Alternatives considered**:
- **OpenAI embeddings**: API costs, latency, privacy concerns for internal docs
- **Pure vector search**: Misses exact keyword matches users expect
- **Standalone vector DB (Pinecone, Weaviate)**: Operational overhead, sync complexity, overkill for 10K chunks

---

## 10. Testing Strategy

**Decision**: Vitest + React Testing Library + Playwright

**Rationale**:
1. **Vitest** — Built for Vite (shared config), 10x faster than Jest, browser mode support
2. **React Testing Library** — User-centric testing approach, excellent shadcn/ui compatibility
3. **Playwright** — E2E testing for critical user journeys, trace viewer for debugging

**Testing pyramid**:
- **Unit**: Vitest for business logic and utilities
- **Component**: Vitest + React Testing Library
- **Integration**: Vitest Browser Mode with Playwright
- **E2E**: Playwright for critical flows (create project, search, upload)

**Alternatives considered**:
- **Jest**: Slower, requires separate configuration from Vite
- **Cypress**: Slower than Playwright, less mature component testing

---

## 11. File Upload Handling

**Decision**: react-dropzone + Uppy (for large files)

**Rationale**:
1. **react-dropzone** — Simple drag-drop for standard files (<10MB)
2. **Uppy + Tus protocol** — Resumable uploads for 50MB files with chunking, progress tracking, pause/resume

**Alternatives considered**:
- **Native file input**: Poor UX for drag-drop and progress tracking
- **Fine Uploader**: Less actively maintained than Uppy

---

## Summary: Resolved Technical Context

| Item | Resolution |
|------|------------|
| Language/Version | Python 3.11+ (backend), TypeScript (frontend) |
| Backend Framework | FastAPI |
| Frontend Framework | Vite + React 19 + TypeScript |
| UI Library | shadcn/ui + Tailwind CSS |
| Forms | React Hook Form + Zod |
| State Management | TanStack Query |
| Data Tables | TanStack Table |
| Storage | PostgreSQL + pgvector + local file system |
| Document Extraction | pdfplumber, python-docx, pandas |
| Authentication | fastapi-azure-auth (Azure AD SSO) |
| RAG/Embeddings | Ollama (nomic-embed-text) + hybrid search |
| Testing | Vitest + React Testing Library + Playwright |
