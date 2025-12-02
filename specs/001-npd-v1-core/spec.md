# Feature Specification: Novus Project Database v1 Core

**Feature Branch**: `001-npd-v1-core`
**Created**: 2025-12-01
**Status**: Draft
**Input**: Build Novus Project Database v1 as defined in the PRD - internal web app with project CRUD, document storage, full-text search, RAG ingestion, tags/classification, AD SSO, and saved searches
**PRD Reference**: `Novus Database PRD v1.md`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and Manage Projects (Priority: P1)

A Novus staff member needs to create a new project record to track work for a client. They log in via Active Directory, click "New Project", fill in required fields (project name, client, contact, owner, description, tags, status, start date, location), and save. Later they can edit or archive the project.

**Why this priority**: Without project CRUD, no other features have meaning. This is the foundational capability that all other features build upon.

**Independent Test**: Can be fully tested by creating a project with all required fields, viewing it in a list, editing it, and archiving it. Delivers immediate value as a project registry.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the home page, **When** they click "New Project" and fill all required fields, **Then** the project is saved and appears in the project list
2. **Given** an existing project, **When** a user edits any field and saves, **Then** the changes persist and display correctly
3. **Given** an existing project, **When** a user archives it, **Then** it no longer appears in the default project list but can be found via filters
4. **Given** a user attempting to save a project, **When** required fields are missing, **Then** the system displays clear validation errors

---

### User Story 2 - Search and Filter Projects (Priority: P1)

A sales manager needs to find projects related to "Bluetooth" for a client named "Meta" to reference in a proposal. They enter keywords in the search bar, apply filters for client and technology, and quickly find relevant projects with matching document content.

**Why this priority**: Search is the primary way users will retrieve value from the system. Per PRD, at least 10 search queries per week is a success metric.

**Independent Test**: Can be fully tested by creating several projects with documents, then searching by keyword and filters to verify correct results appear.

**Acceptance Scenarios**:

1. **Given** projects exist in the system, **When** a user enters a keyword, **Then** matching projects appear ranked by relevance
2. **Given** search results displayed, **When** a user applies filters (client, date range, technology, domain, test type, owner, status), **Then** results narrow accordingly
3. **Given** projects with attached documents, **When** a user searches for text within documents, **Then** projects with matching document content appear in results
4. **Given** search results, **When** a user clicks a project, **Then** they see the full project details and associated documents

---

### User Story 3 - Upload and Manage Documents (Priority: P2)

A test engineer completes a project and needs to attach the test plan, final report, and certification documents. They open the project, drag-and-drop files, and the system indexes them for search.

**Why this priority**: Documents are where institutional knowledge lives. Without document storage and indexing, NPD is just a project list without the valuable content.

**Independent Test**: Can be fully tested by uploading PDF, Word, and Excel files to a project, then verifying they appear in the project view and their content is searchable.

**Acceptance Scenarios**:

1. **Given** an existing project, **When** a user uploads a PDF/Word/Excel file, **Then** the file is stored and appears in the project's document list
2. **Given** an uploaded document, **When** a user searches for text contained in that document, **Then** the parent project appears in search results
3. **Given** a project with documents, **When** a user views the project, **Then** they can see all attached documents with name, type, size, and upload date
4. **Given** multiple files to upload, **When** a user drags and drops them together, **Then** all files upload and appear in the document list

---

### User Story 4 - Classify with Tags and Categories (Priority: P2)

A program manager creating a project wants to categorize it by technology (Wi-Fi, Bluetooth), domain (Wearable), and test type (Interop). They select from structured dropdowns and add free-form tags like "Roku" for easy discovery later.

**Why this priority**: Classification enables filtering and discovery. Without tags, search relies only on text matching which misses conceptual relationships.

**Independent Test**: Can be fully tested by creating a project with various tags, then filtering by those tags to find the project.

**Acceptance Scenarios**:

1. **Given** a project form, **When** a user selects Technology/Domain/Test Type values, **Then** these structured classifications are saved and filterable
2. **Given** a user typing a new free-form tag, **When** similar tags exist, **Then** the system suggests existing tags to reduce duplicates
3. **Given** projects with tags, **When** a user filters by a specific tag, **Then** only projects with that tag appear
4. **Given** a misspelled or variant tag entry, **When** similar tags exist, **Then** the system suggests "Did you mean...?" alternatives

---

### User Story 5 - Bulk Import with RAG Assistance (Priority: P3)

An admin needs to import 50 historical projects from a CSV file with associated document folders. They upload the CSV and point to document locations. The system extracts text, suggests project names, summaries, clients, and tags based on document content.

**Why this priority**: Populating the system with historical data is critical for adoption, but the system must work for new projects first.

**Independent Test**: Can be fully tested by preparing a CSV with project data and a folder of documents, running import, and verifying suggested fields and final created projects.

**Acceptance Scenarios**:

1. **Given** a CSV with project data, **When** an admin uploads it with document folders, **Then** the system creates draft project records with suggested field values
2. **Given** draft projects from import, **When** an admin reviews suggestions, **Then** they can accept, edit, or reject each suggested value before committing
3. **Given** imported documents, **When** the import completes, **Then** document text is indexed for search and RAG features
4. **Given** existing organizations and tags, **When** import suggests a client or tag, **Then** it matches existing records rather than creating duplicates

---

### User Story 6 - Save and Share Searches (Priority: P3)

A lab manager frequently searches for "Bluetooth IOP projects in the last 2 years". They want to save this search as a personal view. Admins can also create global saved searches visible to all users.

**Why this priority**: Saved searches improve efficiency for repeat queries but require search to work first.

**Independent Test**: Can be fully tested by creating a search with filters, saving it, navigating away, then loading it to verify the same results appear.

**Acceptance Scenarios**:

1. **Given** a search with filters applied, **When** a user saves it with a name, **Then** it appears in their personal saved searches
2. **Given** saved searches exist, **When** a user selects one, **Then** the search executes with all saved filters and displays results
3. **Given** admin privileges, **When** an admin marks a saved search as "global", **Then** all users can see and use it
4. **Given** a personal saved search, **When** the creating user deletes it, **Then** it no longer appears in their list

---

### User Story 7 - Track Basic Financial Metadata (Priority: P4)

A finance team member needs to record that a project billed $150,000 across 3 invoices to a specific contact. They enter billing amount, invoice count, recipient, and notes on the project.

**Why this priority**: Financial metadata is useful for reporting but not core to project tracking or search.

**Independent Test**: Can be fully tested by entering billing data on a project and verifying it displays correctly and exports to CSV.

**Acceptance Scenarios**:

1. **Given** a project, **When** a user enters total billed amount and invoice count, **Then** the financial data saves and displays on the project
2. **Given** projects with billing data, **When** a user exports to CSV, **Then** billing fields are included in the export
3. **Given** a project with billing notes, **When** another user views the project, **Then** they can see the billing notes

---

### User Story 8 - Export Project Lists (Priority: P4)

A program manager needs to create a report of all Bluetooth projects for leadership. They run a search, filter results, and export to CSV with core fields for use in Excel or presentations.

**Why this priority**: Export enables external reporting but core functionality must work first.

**Independent Test**: Can be fully tested by searching, filtering, exporting to CSV, and opening the file to verify all expected fields are present.

**Acceptance Scenarios**:

1. **Given** search results displayed, **When** a user clicks "Export to CSV", **Then** a CSV file downloads with project data
2. **Given** exported CSV, **When** opened in Excel, **Then** it contains: name, org, owner, status, dates, Tech/Domain/Test Type, billing totals
3. **Given** filtered results, **When** exporting, **Then** only the filtered projects appear in the export (not all projects)

---

### Edge Cases

- What happens when a user uploads a corrupted or password-protected document? System should reject with clear error message.
- What happens when AD is unavailable? Users cannot log in; system displays maintenance message.
- What happens when a user tries to create a project with a duplicate name for the same client? System should warn but allow (projects can share names).
- What happens when search returns no results? Display helpful message with suggestions to broaden search.
- What happens when bulk import CSV has malformed data? System should report which rows failed and why, allowing partial import of valid rows.
- What happens when a document exceeds size limits? System should reject files over 50 MB with clear error message.

## Requirements *(mandatory)*

### Functional Requirements

**Authentication & Access**
- **FR-001**: System MUST authenticate users via Active Directory SSO
- **FR-002**: System MUST auto-provision user accounts on first AD login
- **FR-003**: System MUST support two roles: User (default) and Admin
- **FR-004**: All authenticated users MUST be able to view all projects (no per-project ACL in v1)

**Project Management**
- **FR-005**: Users MUST be able to create projects with required fields: name, client company, primary contact, internal owner, description, tags (at least one), status, start date, location
- **FR-006**: Users MUST be able to edit any project
- **FR-007**: Users MUST be able to archive/delete projects
- **FR-008**: System MUST support project statuses: Approved, Active, On Hold, Completed, Cancelled
- **FR-009**: System MUST track created_at, created_by, updated_at, updated_by for all projects

**Organizations & Contacts**
- **FR-010**: System MUST maintain Organization records with name and optional aliases
- **FR-011**: System MUST maintain Contact records with name, email, company link, role/title, optional phone and notes
- **FR-012**: Projects MUST link to one Organization (client) and one or more Contacts
- **FR-013**: Contact pages MUST show all related projects

**Documents**
- **FR-014**: System MUST support PDF, DOC/DOCX, XLS/XLSX file uploads (max 50 MB per file)
- **FR-015**: System MUST store files locally on the NPD server
- **FR-016**: System MUST extract text from supported document types for indexing
- **FR-017**: Users MUST be able to attach multiple documents to a project
- **FR-018**: Document uploads MUST support drag-and-drop
- **FR-019**: System MUST track file metadata: path, display name, type, size, uploader, timestamp, associated project

**Tags & Classification**
- **FR-020**: System MUST support structured classification fields: Technology, Domain, Test Type (admin-managed vocabularies)
- **FR-021**: System MUST support free-form tags created by any user
- **FR-022**: System MUST suggest existing similar tags when users create new ones
- **FR-023**: Tags MUST be case-insensitive for search purposes

**Search**
- **FR-024**: System MUST provide keyword search across project fields and full-text document content
- **FR-025**: System MUST support filters: client org, date range, technology, domain, test type, internal owner, status
- **FR-026**: Search results MUST be sortable by relevance (default) or recency
- **FR-027**: Search results MUST display project summary with snippet from matching content

**RAG & Ingestion**
- **FR-028**: System MUST chunk and embed all indexed text for improved relevance
- **FR-029**: System MUST provide bulk import from CSV with document folder references
- **FR-030**: Bulk import MUST suggest: project name, summary, client, contacts, tags based on document content
- **FR-031**: Users MUST be able to review and edit suggestions before committing import
- **FR-032**: Single-project document upload MUST offer "auto-fill from documents" option

**Saved Searches**
- **FR-033**: Users MUST be able to save search + filter combinations as personal views
- **FR-034**: Admins MUST be able to designate saved searches as global (visible to all)
- **FR-035**: Saved searches MUST be loadable to re-execute with original parameters

**Financial Metadata**
- **FR-036**: Projects MUST support optional fields: total_billed_amount, invoice_count, billing_recipient, billing_notes

**Reporting**
- **FR-037**: Users MUST be able to export project lists to CSV with core fields
- **FR-038**: System MUST provide a simple overview page: project count by status, recent projects, top clients

**Platform**
- **FR-039**: System MUST be accessible only on corporate network/VPN
- **FR-040**: System MUST support Chrome and Edge on Windows (desktop only)

### Key Entities

- **User**: Authenticated via AD; has role (User or Admin), can own projects and create saved searches
- **Organization**: Client company; has name, aliases; linked to multiple projects
- **Contact**: Individual at a client company; has name, email, role; linked to organization and projects
- **Project**: Central entity with required/optional fields, linked to organization, contacts, owner, documents, tags
- **Document**: File attached to project; has metadata and extracted text for indexing
- **Tag**: Classification label; either structured (Technology/Domain/Test Type) or free-form
- **SavedSearch**: Stored query with filters; personal or global scope

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Adoption**
- **SC-001**: 75% of active Novus projects entered in NPD within 3 months of launch
- **SC-002**: 100% of active projects in NPD within 6 months of launch

**Usage**
- **SC-003**: At least 10 search queries per week across the organization within 6 months
- **SC-004**: At least 100 projects populated in v1 (mix of active and historical)

**Usability**
- **SC-005**: Users can create a new project with all required fields in under 3 minutes
- **SC-006**: Users can find a relevant project via search in under 30 seconds
- **SC-007**: Document upload (drag-and-drop) completes in under 10 seconds for typical files

**Performance**
- **SC-008**: Search queries over 100-1000 projects return results in under 3 seconds
- **SC-009**: Project detail pages load in under 1 second

**Quality**
- **SC-010**: System is stable enough to demo to ETS/Omnia as potential shared solution
- **SC-011**: Zero data loss incidents in first 6 months

## Clarifications

### Session 2025-12-01

- Q: What is the maximum file size for uploaded documents? → A: 50 MB per file

## Assumptions

- Active Directory infrastructure exists and is accessible from the NPD server
- Corporate network/VPN is reliable and provides adequate access control
- Initial population of ~100 projects is achievable with bulk import tooling
- Users have Chrome or Edge browsers on Windows desktops
- Document sizes are reasonable (typical office documents, not multi-GB files)
- Admin users will manage structured vocabularies (Technology/Domain/Test Type lists)
