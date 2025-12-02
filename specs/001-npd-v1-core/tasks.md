# Tasks: Novus Project Database v1 Core

**Input**: Design documents from `/specs/001-npd-v1-core/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Not explicitly requested in specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/` with models/, schemas/, api/, services/, core/
- **Frontend**: `frontend/src/` with components/, pages/, hooks/, lib/

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create backend project structure per implementation plan in backend/
- [x] T002 Initialize Python 3.11+ project with pyproject.toml in backend/pyproject.toml
- [x] T003 [P] Create requirements.txt with FastAPI, SQLAlchemy, Pydantic, Alembic, fastapi-azure-auth in backend/requirements.txt
- [x] T004 [P] Create requirements-dev.txt with pytest, pytest-asyncio, black, ruff in backend/requirements-dev.txt
- [x] T005 Create frontend project structure per implementation plan in frontend/
- [x] T006 Initialize Vite + React 19 + TypeScript project in frontend/
- [x] T007 [P] Configure Tailwind CSS in frontend/tailwind.config.ts
- [x] T008 [P] Install and configure shadcn/ui components in frontend/src/components/ui/
- [x] T009 Create docker-compose.yml with PostgreSQL (pgvector), Ollama, backend, frontend services
- [x] T010 [P] Create .env.example files for backend and frontend configuration
- [x] T011 [P] Configure ESLint and Prettier for frontend in frontend/.eslintrc.js and frontend/.prettierrc
- [x] T012 [P] Configure black and ruff for backend in backend/pyproject.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T013 Create PostgreSQL database connection with async SQLAlchemy in backend/app/database.py
- [x] T014 Create settings/config management with Pydantic in backend/app/config.py
- [x] T015 Initialize Alembic migrations framework in backend/alembic/
- [x] T016 Create User SQLAlchemy model in backend/app/models/user.py
- [x] T017 Create Alembic migration 001_create_users.py in backend/alembic/versions/
- [x] T018 Implement Azure AD SSO authentication with fastapi-azure-auth in backend/app/core/auth.py
- [x] T019 Create auth dependency for route protection in backend/app/api/deps.py
- [x] T020 Implement auth routes (login, callback, logout, me) in backend/app/api/auth.py
- [x] T021 Create FastAPI application entry point with router mounts in backend/app/main.py
- [x] T022 [P] Create User Pydantic schema in backend/app/schemas/user.py
- [x] T023 [P] Create base response/error schemas in backend/app/schemas/base.py
- [x] T024 Create file storage abstraction layer in backend/app/core/storage.py
- [x] T025 [P] Create API client with TanStack Query setup in frontend/src/lib/api.ts
- [x] T026 [P] Create auth context and hooks for Azure AD in frontend/src/hooks/useAuth.ts
- [x] T027 Create App.tsx with router and auth provider in frontend/src/App.tsx
- [x] T028 [P] Create layout components (Header, Sidebar) in frontend/src/components/layout/
- [x] T029 [P] Create shared utility functions in frontend/src/lib/utils.ts
- [x] T030 [P] Create TypeScript type definitions matching API schemas in frontend/src/types/

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Create and Manage Projects (Priority: P1) 🎯 MVP

**Goal**: Enable Novus staff to create, view, edit, and archive project records with all required fields

**Independent Test**: Create a project with all required fields, view it in a list, edit it, and archive it

### Backend Models for User Story 1

- [x] T031 [P] [US1] Create Organization model in backend/app/models/organization.py
- [x] T032 [P] [US1] Create Contact model in backend/app/models/contact.py
- [x] T033 [P] [US1] Create Tag model with type enum in backend/app/models/tag.py
- [x] T034 [US1] Create Project model with all fields and relationships in backend/app/models/project.py
- [x] T035 [US1] Create ProjectContact junction model in backend/app/models/project.py
- [x] T036 [US1] Create ProjectTag junction model in backend/app/models/project.py
- [x] T037 [US1] Create Alembic migration 002_create_organizations.py
- [x] T038 [US1] Create Alembic migration 003_create_contacts.py
- [x] T039 [US1] Create Alembic migration 004_create_tags.py
- [x] T040 [US1] Create Alembic migration 005_create_projects.py
- [x] T041 [US1] Create Alembic migration 006_create_project_contacts.py
- [x] T042 [US1] Create Alembic migration 007_create_project_tags.py
- [x] T043 [US1] Create seed script for structured tags in backend/app/scripts/seed_tags.py

### Backend Schemas for User Story 1

- [x] T044 [P] [US1] Create Organization Pydantic schemas in backend/app/schemas/organization.py
- [x] T045 [P] [US1] Create Contact Pydantic schemas in backend/app/schemas/contact.py
- [x] T046 [P] [US1] Create Tag Pydantic schemas in backend/app/schemas/tag.py
- [x] T047 [US1] Create Project Pydantic schemas (Create, Update, Response, Detail) in backend/app/schemas/project.py

### Backend API for User Story 1

- [x] T048 [US1] Implement Organization CRUD endpoints in backend/app/api/organizations.py
- [x] T049 [US1] Implement Contact CRUD endpoints in backend/app/api/contacts.py
- [x] T050 [US1] Implement Tag list and create endpoints in backend/app/api/tags.py
- [x] T051 [US1] Implement Project CRUD endpoints (list, create, get, update, delete) in backend/app/api/projects.py
- [x] T052 [US1] Add project status transition validation in backend/app/api/projects.py
- [x] T053 [US1] Register all routers in main.py

### Frontend for User Story 1

- [x] T054 [P] [US1] Create Organization TypeScript types in frontend/src/types/organization.ts
- [x] T055 [P] [US1] Create Contact TypeScript types in frontend/src/types/contact.ts
- [x] T056 [P] [US1] Create Tag TypeScript types in frontend/src/types/tag.ts
- [x] T057 [P] [US1] Create Project TypeScript types in frontend/src/types/project.ts
- [x] T058 [US1] Create useProjects hook with TanStack Query in frontend/src/hooks/useProjects.ts
- [x] T059 [P] [US1] Create useOrganizations hook in frontend/src/hooks/useOrganizations.ts
- [x] T060 [P] [US1] Create useContacts hook in frontend/src/hooks/useContacts.ts
- [x] T061 [P] [US1] Create useTags hook in frontend/src/hooks/useTags.ts
- [x] T062 [US1] Create ProjectForm component with React Hook Form + Zod in frontend/src/components/forms/ProjectForm.tsx
- [x] T063 [US1] Create Projects list page with TanStack Table in frontend/src/pages/ProjectsPage.tsx
- [x] T064 [US1] Create ProjectDetail page in frontend/src/pages/ProjectDetailPage.tsx
- [x] T065 [US1] Create ProjectForm page (new/edit) in frontend/src/pages/ProjectFormPage.tsx
- [x] T066 [US1] Create Dashboard page with project overview in frontend/src/pages/DashboardPage.tsx
- [x] T067 [US1] Add routes for project pages in frontend/src/App.tsx

**Checkpoint**: At this point, User Story 1 should be fully functional - users can create, view, edit, and archive projects

---

## Phase 4: User Story 2 - Search and Filter Projects (Priority: P1)

**Goal**: Enable users to search projects by keyword and filter by various criteria

**Independent Test**: Create several projects, search by keyword, apply filters, verify correct results appear

### Backend for User Story 2

- [ ] T068 [US2] Create full-text search index on Project fields in new migration
- [ ] T069 [US2] Implement SearchService with PostgreSQL ts_vector in backend/app/services/search_service.py
- [ ] T070 [US2] Create search Pydantic schemas (request, response) in backend/app/schemas/search.py
- [ ] T071 [US2] Implement search endpoint with filters in backend/app/api/search.py
- [ ] T072 [US2] Add sorting by relevance and recency in search_service.py

### Frontend for User Story 2

- [ ] T073 [P] [US2] Create SearchResult TypeScript types in frontend/src/types/search.ts
- [ ] T074 [US2] Create useSearch hook with TanStack Query in frontend/src/hooks/useSearch.ts
- [ ] T075 [US2] Create SearchFilters component in frontend/src/components/forms/SearchFilters.tsx
- [ ] T076 [US2] Create SearchResults component in frontend/src/components/tables/SearchResults.tsx
- [ ] T077 [US2] Create Search page with search bar and filters in frontend/src/pages/Search.tsx
- [ ] T078 [US2] Add search page route in frontend/src/App.tsx

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - projects can be created and searched

---

## Phase 5: User Story 3 - Upload and Manage Documents (Priority: P2)

**Goal**: Enable users to upload documents to projects and have them indexed for search

**Independent Test**: Upload PDF, Word, and Excel files to a project, verify they appear and content is searchable

### Backend Models for User Story 3

- [ ] T079 [US3] Create Document model in backend/app/models/document.py
- [ ] T080 [US3] Create DocumentChunk model with pgvector embedding in backend/app/models/document.py
- [ ] T081 [US3] Create Alembic migration 008_create_documents.py
- [ ] T082 [US3] Create Alembic migration 009_create_document_chunks.py with pgvector

### Backend Services for User Story 3

- [ ] T083 [US3] Implement DocumentProcessor for text extraction in backend/app/services/document_processor.py
- [ ] T084 [US3] Implement PDF extraction with pdfplumber in document_processor.py
- [ ] T085 [US3] Implement DOCX extraction with python-docx in document_processor.py
- [ ] T086 [US3] Implement XLSX extraction with pandas + calamine in document_processor.py
- [ ] T087 [US3] Implement EmbeddingService with Ollama integration in backend/app/services/embedding_service.py
- [ ] T088 [US3] Implement text chunking (512 tokens, 12% overlap) in embedding_service.py

### Backend API for User Story 3

- [ ] T089 [P] [US3] Create Document Pydantic schemas in backend/app/schemas/document.py
- [ ] T090 [US3] Implement document upload endpoint with file validation in backend/app/api/documents.py
- [ ] T091 [US3] Implement document list endpoint in backend/app/api/documents.py
- [ ] T092 [US3] Implement document download endpoint in backend/app/api/documents.py
- [ ] T093 [US3] Implement document delete endpoint in backend/app/api/documents.py

### Backend Search Update for User Story 3

- [ ] T094 [US3] Update SearchService to include document content search in search_service.py
- [ ] T095 [US3] Implement hybrid search (ts_vector + pgvector + RRF fusion) in search_service.py

### Frontend for User Story 3

- [ ] T096 [P] [US3] Create Document TypeScript types in frontend/src/types/document.ts
- [ ] T097 [US3] Create useDocuments hook in frontend/src/hooks/useDocuments.ts
- [ ] T098 [US3] Create DocumentUpload component with drag-drop in frontend/src/components/forms/DocumentUpload.tsx
- [ ] T099 [US3] Create DocumentList component in frontend/src/components/tables/DocumentList.tsx
- [ ] T100 [US3] Add document section to ProjectDetail page in frontend/src/pages/ProjectDetail.tsx

**Checkpoint**: Documents can be uploaded, viewed, and their content is searchable

---

## Phase 6: User Story 4 - Classify with Tags and Categories (Priority: P2)

**Goal**: Enable users to classify projects with structured and free-form tags

**Independent Test**: Create a project with various tags, filter by those tags to find the project

### Backend for User Story 4

- [ ] T101 [US4] Implement tag suggestion endpoint with fuzzy matching in backend/app/api/tags.py
- [ ] T102 [US4] Implement TagSuggester service for deduplication in backend/app/services/tag_suggester.py
- [ ] T103 [US4] Add structured tag management endpoints for admins in backend/app/api/admin.py

### Frontend for User Story 4

- [ ] T104 [US4] Create TagSelector component with autocomplete in frontend/src/components/forms/TagSelector.tsx
- [ ] T105 [US4] Add tag suggestion "Did you mean?" UI in TagSelector.tsx
- [ ] T106 [US4] Update SearchFilters to include tag filtering in SearchFilters.tsx
- [ ] T107 [US4] Create Tags management page for admins in frontend/src/pages/Admin.tsx

**Checkpoint**: Projects can be classified with tags and filtered by tags in search

---

## Phase 7: User Story 5 - Bulk Import with RAG Assistance (Priority: P3)

**Goal**: Enable admins to bulk import projects from CSV with AI-suggested field values

**Independent Test**: Prepare CSV with project data, run import, verify suggested fields and created projects

### Backend for User Story 5

- [ ] T108 [US5] Create ImportService for CSV parsing and validation in backend/app/services/import_service.py
- [ ] T109 [US5] Implement RAG-based field suggestion in import_service.py using embeddings
- [ ] T110 [US5] Create import preview endpoint in backend/app/api/admin.py
- [ ] T111 [US5] Create import commit endpoint in backend/app/api/admin.py
- [ ] T112 [US5] Implement autofill endpoint for single project in backend/app/api/projects.py
- [ ] T113 [P] [US5] Create Import Pydantic schemas in backend/app/schemas/import_.py

### Frontend for User Story 5

- [ ] T114 [P] [US5] Create Import TypeScript types in frontend/src/types/import.ts
- [ ] T115 [US5] Create useImport hook in frontend/src/hooks/useImport.ts
- [ ] T116 [US5] Create ImportUpload component in frontend/src/components/forms/ImportUpload.tsx
- [ ] T117 [US5] Create ImportPreview component with editable rows in frontend/src/components/tables/ImportPreview.tsx
- [ ] T118 [US5] Create Import page in frontend/src/pages/Import.tsx
- [ ] T119 [US5] Add autofill button to ProjectForm in ProjectForm.tsx

**Checkpoint**: Bulk import works with AI suggestions, autofill works for single projects

---

## Phase 8: User Story 6 - Save and Share Searches (Priority: P3)

**Goal**: Enable users to save searches and admins to create global searches

**Independent Test**: Create a search with filters, save it, navigate away, load it to verify same results

### Backend for User Story 6

- [ ] T120 [US6] Create SavedSearch model in backend/app/models/saved_search.py
- [ ] T121 [US6] Create Alembic migration 010_create_saved_searches.py
- [ ] T122 [P] [US6] Create SavedSearch Pydantic schemas in backend/app/schemas/search.py
- [ ] T123 [US6] Implement saved search CRUD endpoints in backend/app/api/search.py
- [ ] T124 [US6] Implement admin toggle global endpoint in backend/app/api/admin.py

### Frontend for User Story 6

- [ ] T125 [P] [US6] Create SavedSearch TypeScript types in frontend/src/types/search.ts
- [ ] T126 [US6] Create useSavedSearches hook in frontend/src/hooks/useSavedSearches.ts
- [ ] T127 [US6] Create SavedSearchList component in frontend/src/components/SavedSearchList.tsx
- [ ] T128 [US6] Add save search button to Search page in Search.tsx
- [ ] T129 [US6] Add saved search sidebar/dropdown in Search.tsx

**Checkpoint**: Searches can be saved, loaded, and shared globally by admins

---

## Phase 9: User Story 7 - Track Basic Financial Metadata (Priority: P4)

**Goal**: Enable recording billing information on projects

**Independent Test**: Enter billing data on a project, verify it displays correctly

### Implementation for User Story 7

- [ ] T130 [US7] Add billing fields to Project model if not already present (verify in backend/app/models/project.py)
- [ ] T131 [US7] Update ProjectForm to include billing fields in frontend/src/components/forms/ProjectForm.tsx
- [ ] T132 [US7] Update ProjectDetail to display billing information in frontend/src/pages/ProjectDetail.tsx

**Checkpoint**: Billing metadata can be recorded and displayed on projects

---

## Phase 10: User Story 8 - Export Project Lists (Priority: P4)

**Goal**: Enable users to export filtered project lists to CSV

**Independent Test**: Search, filter, export to CSV, open file to verify fields

### Backend for User Story 8

- [ ] T133 [US8] Implement CSV export endpoint in backend/app/api/projects.py
- [ ] T134 [US8] Include all required fields (name, org, owner, status, dates, tags, billing) in export

### Frontend for User Story 8

- [ ] T135 [US8] Create useExport hook in frontend/src/hooks/useExport.ts
- [ ] T136 [US8] Add Export button to Projects list page in Projects.tsx
- [ ] T137 [US8] Add Export button to Search results in Search.tsx

**Checkpoint**: Project lists can be exported to CSV from both project list and search results

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T138 [P] Implement overview statistics endpoint in backend/app/api/admin.py
- [ ] T139 Add overview statistics to Dashboard in frontend/src/pages/Dashboard.tsx
- [ ] T140 [P] Create Organizations list page in frontend/src/pages/Organizations.tsx
- [ ] T141 [P] Create Contacts list page in frontend/src/pages/Contacts.tsx
- [ ] T142 Add error handling and loading states across all pages
- [ ] T143 [P] Add responsive design for all pages
- [ ] T144 Security audit: Validate all inputs, prevent injection attacks
- [ ] T145 [P] Add rate limiting to API endpoints
- [ ] T146 Run quickstart.md validation end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - US1 (Phase 3) and US2 (Phase 4) are both P1 priority
  - US2 (Search) can start before US1 is complete but full search needs documents from US3
  - US3-US8 can proceed sequentially or in parallel
- **Polish (Phase 11)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Basic search works without US3, full hybrid search needs US3 documents
- **User Story 3 (P2)**: Can start after Foundational - Enhances US2 search
- **User Story 4 (P2)**: Can start after US1 (needs tags infrastructure)
- **User Story 5 (P3)**: Requires US1 (projects) and US3 (documents) to be complete
- **User Story 6 (P3)**: Requires US2 (search) to be complete
- **User Story 7 (P4)**: Requires US1 (projects) to be complete
- **User Story 8 (P4)**: Requires US1 (projects) and US2 (search) to be complete

### Within Each User Story

- Models before schemas
- Schemas before API endpoints
- API endpoints before frontend hooks
- Frontend hooks before UI components
- Core implementation before integration

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Backend models marked [P] can be created in parallel
- Frontend TypeScript types and hooks marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1 Backend Models

```bash
# Launch all independent models together:
Task: "Create Organization model in backend/app/models/organization.py"
Task: "Create Contact model in backend/app/models/contact.py"
Task: "Create Tag model with type enum in backend/app/models/tag.py"

# Then Project model (depends on above):
Task: "Create Project model with all fields and relationships in backend/app/models/project.py"
```

---

## Parallel Example: User Story 1 Frontend Types

```bash
# Launch all independent types together:
Task: "Create Organization TypeScript types in frontend/src/types/organization.ts"
Task: "Create Contact TypeScript types in frontend/src/types/contact.ts"
Task: "Create Tag TypeScript types in frontend/src/types/tag.ts"
Task: "Create Project TypeScript types in frontend/src/types/project.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 - Project CRUD
4. Complete Phase 4: User Story 2 - Basic Search
5. **STOP and VALIDATE**: Test project creation and search independently
6. Deploy/demo if ready - this is the MVP

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP core
3. Add User Story 2 → Test independently → Search works
4. Add User Story 3 → Test independently → Documents searchable
5. Add User Story 4 → Test independently → Tags work
6. Add User Story 5-8 → Each adds value incrementally
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Backend)
   - Developer B: User Story 1 (Frontend)
   - Or split by user story if more developers
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total: 146 tasks across 11 phases
- MVP scope: Setup + Foundational + US1 + US2 (67 tasks)
