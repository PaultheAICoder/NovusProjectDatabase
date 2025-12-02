# Data Model: Novus Project Database v1 Core

**Branch**: `001-npd-v1-core` | **Date**: 2025-12-01

This document defines the entity schema, relationships, validation rules, and state transitions for NPD v1.

---

## Entity Relationship Diagram

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      User       │       │   Organization  │       │     Contact     │
│─────────────────│       │─────────────────│       │─────────────────│
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ azure_id        │       │ name            │       │ name            │
│ email           │       │ aliases[]       │       │ email           │
│ display_name    │       │ created_at      │       │ organization_id │──┐
│ role            │       │ updated_at      │       │ role_title      │  │
│ is_active       │       └────────┬────────┘       │ phone           │  │
│ created_at      │                │                │ notes           │  │
│ last_login_at   │                │ 1              │ monday_url      │  │
└────────┬────────┘                │                │ created_at      │  │
         │                         │                │ updated_at      │  │
         │                         │                └────────┬────────┘  │
         │                         │                         │           │
         │ 1                       │                         │ N         │ 1
         │                         ▼                         │           │
         │            ┌────────────────────────┐              │           │
         │            │        Project         │◄─────────────┘           │
         │            │────────────────────────│                          │
         └───────────►│ id (PK)                │                          │
           owner_id   │ name                   │                          │
                      │ organization_id (FK)   │◄─────────────────────────┘
                      │ owner_id (FK)          │
                      │ description            │
                      │ status                 │
                      │ start_date             │
                      │ end_date               │
                      │ location               │
                      │ billing_amount         │
                      │ invoice_count          │
                      │ billing_recipient      │
                      │ billing_notes          │
                      │ pm_notes               │
                      │ monday_url             │
                      │ jira_url               │
                      │ gitlab_url             │
                      │ created_at             │
                      │ created_by (FK)        │
                      │ updated_at             │
                      │ updated_by (FK)        │
                      └───────────┬────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼ N                 ▼ N                 ▼ N
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│    Document     │   │  ProjectContact │   │   ProjectTag    │
│─────────────────│   │─────────────────│   │─────────────────│
│ id (PK)         │   │ project_id (FK) │   │ project_id (FK) │
│ project_id (FK) │   │ contact_id (FK) │   │ tag_id (FK)     │
│ file_path       │   │ is_primary      │   │ created_at      │
│ display_name    │   └─────────────────┘   └────────┬────────┘
│ mime_type       │                                  │
│ file_size       │                                  │ N
│ uploaded_by(FK) │                                  ▼
│ uploaded_at     │                         ┌─────────────────┐
│ extracted_text  │                         │       Tag       │
│ created_at      │                         │─────────────────│
└────────┬────────┘                         │ id (PK)         │
         │                                  │ name            │
         │ 1                                │ type            │
         ▼                                  │ created_by (FK) │
┌─────────────────┐                         │ created_at      │
│  DocumentChunk  │                         └─────────────────┘
│─────────────────│
│ id (PK)         │
│ document_id(FK) │
│ chunk_index     │                         ┌─────────────────┐
│ content         │                         │   SavedSearch   │
│ content_tsv     │                         │─────────────────│
│ embedding       │                         │ id (PK)         │
│ metadata        │                         │ name            │
│ created_at      │                         │ query           │
└─────────────────┘                         │ filters (JSON)  │
                                            │ user_id (FK)    │
                                            │ is_global       │
                                            │ created_at      │
                                            │ updated_at      │
                                            └─────────────────┘
```

---

## Entity Definitions

### User

Authenticated users provisioned from Azure AD on first login.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| azure_id | VARCHAR(255) | UNIQUE, NOT NULL | Azure AD object ID |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email from AD |
| display_name | VARCHAR(255) | NOT NULL | Full name from AD |
| role | ENUM | NOT NULL, DEFAULT 'user' | 'user' or 'admin' |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Account status |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | First login timestamp |
| last_login_at | TIMESTAMP | | Most recent login |

**Validation Rules**:
- `email` must be valid email format
- `role` extracted from Azure AD App Roles on login

**Indexes**:
- UNIQUE on `azure_id`
- UNIQUE on `email`

---

### Organization

Client companies that own projects.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| name | VARCHAR(255) | UNIQUE, NOT NULL | Canonical company name |
| aliases | VARCHAR(255)[] | | Alternative names/abbreviations |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last modification |

**Validation Rules**:
- `name` must be unique (case-insensitive)
- `aliases` are optional, used for search matching

**Indexes**:
- UNIQUE on `LOWER(name)`
- GIN on `aliases` for array search

---

### Contact

Individuals at client organizations linked to projects.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| name | VARCHAR(255) | NOT NULL | Contact full name |
| email | VARCHAR(255) | NOT NULL | Contact email |
| organization_id | UUID | FK → Organization, NOT NULL | Parent company |
| role_title | VARCHAR(255) | | Job title |
| phone | VARCHAR(50) | | Phone number |
| notes | TEXT | | Free-form notes |
| monday_url | VARCHAR(500) | | Monday.com contact URL (v2 integration prep) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last modification |

**Validation Rules**:
- `email` must be valid email format
- Unique constraint on (`email`, `organization_id`)

**Indexes**:
- INDEX on `organization_id`
- INDEX on `LOWER(email)`

---

### Project

Central entity tracking client work.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| name | VARCHAR(255) | NOT NULL | Project name |
| organization_id | UUID | FK → Organization, NOT NULL | Client company |
| owner_id | UUID | FK → User, NOT NULL | Internal Novus lead |
| description | TEXT | NOT NULL | Summary/description |
| status | ENUM | NOT NULL | See Status enum below |
| start_date | DATE | NOT NULL | Project start date |
| end_date | DATE | | Actual or expected end date |
| location | VARCHAR(255) | NOT NULL | Lab/site location |
| billing_amount | DECIMAL(12,2) | | Total billed amount |
| invoice_count | INTEGER | | Number of invoices |
| billing_recipient | VARCHAR(255) | | Invoice recipient |
| billing_notes | TEXT | | Billing notes |
| pm_notes | TEXT | | PM learnings/notes |
| monday_url | VARCHAR(500) | | Monday board URL |
| jira_url | VARCHAR(500) | | Jira epic URL |
| gitlab_url | VARCHAR(500) | | GitLab repo URL |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Record creation |
| created_by | UUID | FK → User, NOT NULL | Creating user |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last modification |
| updated_by | UUID | FK → User, NOT NULL | Last modifier |

**Project Status Enum**:
```
approved    -- Approved but not started
active      -- Currently in progress
on_hold     -- Temporarily paused
completed   -- Successfully finished
cancelled   -- Terminated before completion
```

Note: Pipeline states (`prospect`, `quoting`) reserved for v3 but schema supports extension.

**Validation Rules**:
- `name` required (duplicates allowed across orgs per edge case spec)
- `description` required
- At least one tag required (enforced at API level)
- `start_date` must be valid date
- `end_date` must be >= `start_date` if provided
- `billing_amount` must be >= 0 if provided

**Indexes**:
- INDEX on `organization_id`
- INDEX on `owner_id`
- INDEX on `status`
- INDEX on `start_date`
- GIN on full-text search vector (name, description)

---

### ProjectContact

Junction table for Project ↔ Contact (many-to-many).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| project_id | UUID | FK → Project, NOT NULL | Project reference |
| contact_id | UUID | FK → Contact, NOT NULL | Contact reference |
| is_primary | BOOLEAN | NOT NULL, DEFAULT false | Primary contact flag |

**Constraints**:
- PK on (`project_id`, `contact_id`)
- Each project must have exactly one primary contact

---

### Document

Files attached to projects with extracted text for search.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| project_id | UUID | FK → Project, NOT NULL | Parent project |
| file_path | VARCHAR(500) | NOT NULL | Storage path |
| display_name | VARCHAR(255) | NOT NULL | User-visible filename |
| mime_type | VARCHAR(100) | NOT NULL | MIME type |
| file_size | BIGINT | NOT NULL | Size in bytes |
| uploaded_by | UUID | FK → User, NOT NULL | Uploading user |
| uploaded_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Upload timestamp |
| extracted_text | TEXT | | Raw extracted text |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Record creation |

**Supported MIME Types**:
- `application/pdf`
- `application/msword` (.doc)
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (.docx)
- `application/vnd.ms-excel` (.xls)
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (.xlsx)

**Validation Rules**:
- `file_size` must be <= 50 MB (52,428,800 bytes)
- `mime_type` must be in supported list
- File must pass corruption/malware checks

**Indexes**:
- INDEX on `project_id`
- GIN on `to_tsvector('english', extracted_text)`

---

### DocumentChunk

Chunked document content with embeddings for RAG search.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| document_id | UUID | FK → Document, NOT NULL | Parent document |
| chunk_index | INTEGER | NOT NULL | Order within document |
| content | TEXT | NOT NULL | Chunk text content |
| content_tsv | TSVECTOR | GENERATED | Full-text search vector |
| embedding | VECTOR(768) | NOT NULL | nomic-embed-text embedding |
| metadata | JSONB | | Page number, headings, etc. |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Chunk creation |

**Constraints**:
- UNIQUE on (`document_id`, `chunk_index`)

**Indexes**:
- INDEX on `document_id`
- GIN on `content_tsv`
- HNSW on `embedding` using `vector_cosine_ops`

---

### Tag

Classification labels for projects (structured and free-form).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| name | VARCHAR(100) | NOT NULL | Tag display name |
| type | ENUM | NOT NULL | See Tag Type enum |
| created_by | UUID | FK → User | Creating user (NULL for system tags) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |

**Tag Type Enum**:
```
technology   -- Structured: Wi-Fi, Bluetooth, BLE, Zigbee, NFC, Cellular, etc.
domain       -- Structured: Wearable, Smart Home, Automotive, Enterprise, Consumer
test_type    -- Structured: Interop, Performance, Certification, Environmental, Build/Bring-up
freeform     -- User-created tags
```

**Validation Rules**:
- `name` unique within `type` (case-insensitive)
- Structured types (technology, domain, test_type) admin-managed
- Freeform tags can be created by any user

**Indexes**:
- UNIQUE on (`LOWER(name)`, `type`)
- INDEX on `type`

---

### ProjectTag

Junction table for Project ↔ Tag (many-to-many).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| project_id | UUID | FK → Project, NOT NULL | Project reference |
| tag_id | UUID | FK → Tag, NOT NULL | Tag reference |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Assignment timestamp |

**Constraints**:
- PK on (`project_id`, `tag_id`)
- Each project must have at least one tag (enforced at API level)

---

### SavedSearch

Stored search queries for quick re-execution.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| name | VARCHAR(255) | NOT NULL | Search display name |
| query | VARCHAR(500) | | Keyword search text |
| filters | JSONB | NOT NULL | Filter criteria |
| user_id | UUID | FK → User, NOT NULL | Creating user |
| is_global | BOOLEAN | NOT NULL, DEFAULT false | Visible to all users |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last modification |

**Filters JSONB Schema**:
```json
{
  "organization_ids": ["uuid", ...],
  "owner_ids": ["uuid", ...],
  "statuses": ["active", "completed", ...],
  "tag_ids": ["uuid", ...],
  "start_date_from": "2024-01-01",
  "start_date_to": "2024-12-31",
  "technologies": ["uuid", ...],
  "domains": ["uuid", ...],
  "test_types": ["uuid", ...]
}
```

**Validation Rules**:
- Only admins can set `is_global = true`
- Users can only modify their own saved searches

**Indexes**:
- INDEX on `user_id`
- INDEX on `is_global`

---

## State Transitions

### Project Status

```text
                    ┌─────────────┐
                    │   (new)     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌─────│  approved   │─────┐
              │     └──────┬──────┘     │
              │            │            │
              │            ▼            │
              │     ┌─────────────┐     │
              │     │   active    │◄────┤
              │     └──────┬──────┘     │
              │            │            │
              │     ┌──────┴──────┐     │
              │     │             │     │
              │     ▼             ▼     │
              │ ┌─────────┐ ┌─────────┐ │
              │ │ on_hold │ │completed│ │
              │ └────┬────┘ └─────────┘ │
              │      │                  │
              │      └──────────────────┤
              │                         │
              ▼                         ▼
        ┌─────────────┐          ┌─────────────┐
        │  cancelled  │          │  cancelled  │
        └─────────────┘          └─────────────┘

Valid Transitions:
- approved → active, cancelled
- active → on_hold, completed, cancelled
- on_hold → active, cancelled
- completed → (terminal)
- cancelled → (terminal)
```

---

## Audit Fields

All mutable entities include standard audit fields per Constitution Principle V:

| Field | Applied To | Description |
|-------|------------|-------------|
| created_at | All entities | Record creation timestamp |
| created_by | Project | User who created the record |
| updated_at | Organization, Contact, Project, SavedSearch | Last modification timestamp |
| updated_by | Project | User who last modified the record |

---

## Database Extensions Required

```sql
-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgvector";     -- Vector embeddings
```

---

## Migration Strategy

Alembic migrations should be created in this order:

1. `001_create_users.py` - User table
2. `002_create_organizations.py` - Organization table
3. `003_create_contacts.py` - Contact table with org FK
4. `004_create_tags.py` - Tag table with initial structured values
5. `005_create_projects.py` - Project table with all FKs
6. `006_create_project_contacts.py` - ProjectContact junction
7. `007_create_project_tags.py` - ProjectTag junction
8. `008_create_documents.py` - Document table
9. `009_create_document_chunks.py` - DocumentChunk with pgvector
10. `010_create_saved_searches.py` - SavedSearch table
11. `011_seed_structured_tags.py` - Populate initial Technology/Domain/Test Type tags
