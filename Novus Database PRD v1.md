# **Novus Project Database (NPD) – Product Requirements Document**

## **1\. Overview**

### **1.1 Problem**

Today, Novus project knowledge is scattered:

* Project history lives in people’s heads, personal OneDrive folders, SharePoint, certification drives, email threads, Jira, Monday, etc.

* There’s no consistent way to see **what we did, for whom, with what devices, and where the artifacts are**.

* Sales and engineers regularly ask each other:

  * “What did we do around roaming for \<client\>?”

  * “Do we have a test plan for X?”

  * “Can you send me some example projects for this proposal?”

* Inventory, financials, and project artifacts are hard to connect, which makes reporting, reuse, and new quoting painful.

### **1.2 Vision**

Build an internal **Novus Project Database (NPD)**:  
 A **central, relational project database \+ simple web UI** where Novus staff can:

* Create and update project records with a small set of **required fields** (W’s: who/what/where/when, etc.).

* Attach and search **key documents** (SOWs, test plans, reports, spreadsheets).

* Use **full-text search \+ RAG-backed ingestion** to find projects and content across docs.

* Over time, integrate with Monday, Jira, inventory, and other systems without redoing the core data model.

NPD must be **easier and faster** than “doing nothing” or using SharePoint / the current inventory DB, or it won’t be adopted.

### **1.3 Goals (v1)**

Within 3–6 months of v1 launch:

* ≥ **75% of active projects** in the system by 3 months; **100%** by 6 months.

* At least **10 search queries per week** across the org.

* NPD is stable and compelling enough to demo to ETS/Omnia as a potential shared solution (no requirement they adopt it yet).

* Architecture and data model allow **v2 and v3** features (Monday/Jira integration, pipeline tracking, mobile, etc.) without major rework.

---

## **2\. Scope & Phasing**

### **2.1 v1 Scope – “Core Project Tracker \+ RAG Ingestion”**

**In scope (must-have):**

* Internal web app: **Novus-only**, company-wide visibility.

* **Relational backend** for projects, organizations, contacts, documents, tags.

* **Project CRUD**:

  * Create, edit, delete, archive project records.

  * Capture required fields (see §4.1).

* **Document handling**:

  * Local file storage on the NPD server (PDF, DOC/DOCX, XLS/XLSX as core types).

  * Attach multiple docs to a project.

  * Full-text indexing of supported doc types.

* **Search**:

  * Keyword search across core project fields and full-text doc contents.

  * Basic filters (client, date, tags, internal owner, status).

* **RAG / ingestion**:

  * Tools to import existing projects (bulk) and use content from docs to **help populate fields** (e.g., suggested summary, tags).

  * RAG infrastructure (embeddings \+ chunked text store) to support:

    * Better relevance for full-text search.

    * Future natural-language / semantic search and generation features.

* **Saved searches / views**:

  * Per-user saved searches.

  * Admin-configurable “global” saved views.

* **Basic financial metadata**:

  * Structured fields for total billing, invoice count, invoice recipient, plus free-form notes.

* **Tags & classification**:

  * Mix of structured fields (e.g., Tech, Domain, Test Type) and free-form tags.

  * Anyone can create tags in v1, with AI-based suggestions to reduce duplicates.

* **Authentication & access**:

  * Internal-only, corp network/VPN.

  * SSO via **Active Directory** (AD) – v1 requirement.

  * Simple roles: User and Admin.

* **Import & population strategy**:

  * **Bulk import tools** and workflows (e.g., CSV \+ file ingestion).

  * Aim to onboard \~**100 projects** in v1.

* **Supported platforms**:

  * Desktop web only.

  * **Chrome and Edge on Windows** supported.

**Out of scope for v1 (but must not be blocked):**

* Pre-contract / quoting pipeline tracking (phase 3).

* Fine-grained per-project access control (phase 3).

* Monday.com, Jira, GitLab, inventory DB integrations (beyond manual URLs).

* Natural-language / semantic search UX (v2).

* Auto-generated one-pagers / slide decks (v3).

* Mobile / responsive UX (v3).

### **2.2 v2 (for context)**

* Natural-language / semantic search over projects and documents.

* Tag synonym handling / fuzzy search (e.g., BLE vs Bluetooth LE).

* **Monday.com integration**:

  * Search/link existing contacts.

  * Create/update contacts from NPD.

  * (Potentially) connect projects to Monday boards.

* **Jira integration**:

  * Store Jira links per project.

  * (Optionally) pull high-level status/summary via Jira API.

* **Audit logs**: who created/edited what, and when.

* Scale to \~**1000 projects**.

### **2.3 v3 (for context)**

* Full support for **pre-contract / quoting** work (pipeline states).

* Fine-grained access control (project-level restrictions; ETS/Omnia multi-tenant options).

* Switch file storage backing to **SharePoint/OneDrive or other robust storage**, using abstractions designed in v1.

* GitLab integration.

* Mobile / responsive UI.

---

## **3\. Users & Roles**

### **3.1 Primary Users (v1)**

* **Lab / test engineers**

* **Program / project managers**

* **Sales / account managers**

* **Leadership** (Shad & execs) – primarily consumers, not daily editors.

* **Ops / finance** – for billing and reporting metadata.

### **3.2 Roles & Permissions (v1)**

* **User (default)**:

  * Authenticated via AD.

  * Can **view all projects**.

  * Can **create** new projects.

  * Can **edit** any project (until future role model).

  * Can upload documents and add tags.

  * Can create and manage their **own** saved searches.

* **Admin (5–10 trusted users)**:

  * All User capabilities.

  * Can configure:

    * Structured field vocabularies (e.g., Tech/Domain/Test Type lists).

    * Global saved searches/views.

  * Can manage system settings (tag-merge tools, cleanup scripts, etc.).

Future (post-v1): move toward “only admins can create new tags/projects”, with users proposing changes.

---

## **4\. Functional Requirements (v1)**

### **4.1 Project Entity & Fields**

Each **Project** record must contain:

**Required fields at creation:**

1. **Project Name**

2. **Client Company** (Organization)

3. **Primary Client Contact** (link to a Contact record)

4. **Internal Owner / Primary Novus Lead** (linked to AD user)

5. **Short Description / Summary**

6. **Tags** (at least one, using structured \+ free-form model)

7. **Project Status**

   * Enum, including at least: `Approved`, `Active`, `On Hold`, `Completed`, `Cancelled`

   * (Pipeline states like `Prospect` / `Quoting` reserved for v3, but supported in DB schema.)

8. **Start Date**

9. **Location / Lab** (e.g., main lab, remote, client site)

**Optional / structured fields (v1):**

* **End Date** (actual or expected)

* **Additional Internal Contacts** (other Novus staff involved)

* **Key Devices / Inventory Notes** (simple text list in v1; full linkage in future)

* **Billing / Financials:**

  * `total_billed_amount` (numeric \+ currency)

  * `invoice_count` (integer)

  * `billing_recipient` (free text or link to Contact)

  * `billing_notes` (free-form text)

* **PM Notes / Learnings** (free-form, e.g., “quoted 4 weeks, ran 6; reason…”)

* **Links**:

  * Monday board URL (manual for v1)

  * Jira epic URL(s) (manual in v1, API in v2)

  * GitLab repo URL(s) (manual; future automation v3)

  * Other external storage URLs if needed

**Document-derived content:**

* For each project, NPD should maintain:

  * **Short description** (user-entered).

  * **Extended content snippets** auto-suggested from attached docs (e.g., SOW/project overview extracted text) to enrich search and future RAG Q\&A.

### **4.2 Organizations & Contacts**

**Organization (Client):**

* Name (canonical)

* Aliases / short names (optional)

* Basic metadata (e.g., region, segment – optional v1)

* Relationship to projects: 1-to-many (Org → Projects)

**Contact:**

* Name

* Email

* Company (link to Org)

* Role / title

* Phone (optional)

* Notes

**Behavior (v1):**

* Contacts stored locally in NPD.

* Optional field for **Monday contact ID/URL** (no API integration yet).

* From a Contact page: show all related projects.

**v2 (for context):**

* Monday API integration to:

  * Look up contacts.

  * Create/update them when added/edited in NPD.

### **4.3 Documents & File Storage**

**Supported document types (v1):**

* PDF (`.pdf`)

* Word (`.doc`, `.docx`)

* Excel (`.xls`, `.xlsx`)

* (Potential to extend to others later.)

**Storage model (v1):**

* Files are stored **locally** on an internal NPD file repository (e.g., file system or blob store on same server).

* Database stores:

  * File path / ID

  * Display name

  * Type / MIME

  * Size

  * Uploading user \+ timestamp

  * Associated project

**Requirements:**

* Attach multiple documents per project.

* Upload UI must be simple (drag-and-drop or minimal clicks).

* NPD extracts text from supported docs for full-text index and RAG store.

* Future-proof: storage layer abstracted so backing store can be swapped (e.g., to SharePoint/OneDrive in v3) without changing the product’s logical behavior.

### **4.4 Tags & Classification**

**Structured classification fields (v1):**

* **Technology** (multi-select list; e.g., Wi‑Fi, Bluetooth, BLE, Zigbee, NFC, Cellular, etc.)

* **Domain** (Wearable, Smart Home, Automotive, Enterprise, Consumer, etc.)

* **Test Type** (Interop, Performance, Certification, Environmental, Build/Bring-up, etc.)

Admins manage initial vocabularies and can add/edit values.

**Free-form tags:**

* Users can add arbitrary text tags (e.g., “Roku”, “IoT gateway”, “PCIe”, “battery-charging”).

* Tags are case-insensitive in search.

**AI-based dedup (v1):**

* When a user types a new tag, NPD should:

  * Suggest **existing similar tags** (“Did you mean Bluetooth IOP?”).

  * Encourage reuse of existing tags while still allowing free creation.

**Future (v2+):**

* Synonym dictionaries and fuzzy search so “BLE”, “Bluetooth LE”, “Bluetooth” can be treated as related.

* Governance changes so only admins can create new tags (users propose tags for approval).

### **4.5 Search & Retrieval**

**Search scope (v1):**

* Projects (via name, description, structured fields, tags).

* Organizations & Contacts (as part of project search, not separate directory UI in v1).

* Attached documents (via **full-text content** \+ metadata).

**Baseline search behavior (v1):**

* **Keyword search** bar:

  * Searches project fields (name, description, tags, organization, contacts).

  * Searches full-text contents of attached docs.

* **Filters / facets:**

  * Client org

  * Date range (by project start/end date)

  * Technology

  * Domain

  * Test Type

  * Internal owner

  * Status

* **Sorting**:

  * Default: relevance to query.

  * Secondary: recency (start or completion date).

* **Result UI:**

  * List of projects with key fields and a small snippet (pulled from description or doc content).

  * Click project to see full details and associated documents.

**RAG aspects (v1):**

* All indexed text (from docs \+ long fields) is:

  * Chunked and stored with **embeddings**.

  * Used to improve relevance ranking of full-text searches and to support:

    * Auto-suggested tags/summary on import.

    * Future natural-language Q\&A (v2).

**Saved searches / views:**

* Any search \+ filter combo can be saved as:

  * **Personal view** (visible only to creator).

  * **Global view** (admins can designate; visible to all).

* Examples:

  * “Wearables – last 2 years”

  * “Meta projects – in the last year”

  * “Bluetooth IOP projects with \> 3 invoices”

**Future (v2):**

* **Natural-language / semantic search**:

  * Accept queries like “show me IoT Bluetooth projects in the last 2 years with performance testing”.

  * Use embeddings to interpret queries semantically, not just keyword-based.

* Summarized responses (LLM answering over retrieved content).

### **4.6 RAG-based Import & Population**

Population strategy is **critical** for v1.

**Scale assumptions:**

* **v1:** \~100 projects ingested (mix of active and historical).

* **v2:** design to comfortably handle at least 1000 projects (and grow beyond).

**Import sources:**

* CSV/Excel lists of projects (if any exist).

* Manually selected folders or file sets per project (from:

  * Certification drives

  * OneDrive/SharePoint

  * Other shared folders).

**Import workflow (v1):**

1. **Admin selects import source**:

   * E.g., upload a CSV with basic fields \+ attach a zip/folder of documents.

2. **Extraction & analysis**:

   * NPD:

     * Extracts text from supported docs.

     * Generates a proposed:

       * Project name

       * Short summary (1–2 sentences)

       * Client organization (if detectable)

       * Primary contacts (email/name detection)

       * Candidate tags (Tech/Domain/Test Type \+ free tags)

   * Uses RAG/embedding search internally to find similar existing orgs/tags to avoid duplication.

3. **Review screen**:

   * Shows suggested fields and tags per project.

   * Admin (or designated user) can accept/edit suggestions before committing.

4. **Commit**:

   * Creates project records and attaches docs.

   * Indexes everything into full-text and embedding stores.

**Ongoing usage:**

* When creating or editing a project:

  * User can upload docs and request **“auto-fill from documents”**, which:

    * Suggests tags, updates summary, and optionally adds notes based on doc contents.

### **4.7 Basic Reporting & Views**

v1 is not a full reporting system, but NPD should support:

* Export of project lists to CSV with:

  * Core fields (name, org, owner, status, dates, Tech/Domain/Test Type, billing totals).

* A simple “Projects overview” page:

  * Count of projects by status.

  * Recent projects.

  * Top clients by project count.

Future versions can include leadership-focused financial and utilization rollups.

### **4.8 Integrations**

**v1 (must-have):**

* **Active Directory**:

  * AD-backed SSO (e.g., Azure AD).

  * Users auto-provisioned on first login where possible.

* **File storage**:

  * Local repository on NPD server as described in §4.3.

**v1 (manual-only references):**

* Monday.com, Jira, GitLab:

  * URL fields on projects where users can paste links (no API, no sync).

**v2 (planned):**

* Monday.com:

  * Search and link contacts from Monday.

  * Create/update contacts in Monday when modified within NPD.

  * Optional project ↔ board linkage.

* Jira:

  * Store Jira keys and URLs.

  * Optionally fetch high-level status/summary for display.

* Audit logs (see §5.2).

**v3 (planned):**

* GitLab (repos, pipelines).

* Deeper financial/inventory integrations.

* Switch to external file stores (SharePoint/OneDrive or similar).

---

## **5\. Non-Functional Requirements**

### **5.1 Security & Access**

* **Internal-only web app**:

  * Deployed on internal Novus server.

  * Reachable only over corporate network/VPN.

  * No public internet exposure.

* **Authentication**:

  * AD-based SSO required for v1.

* **Authorization / visibility**:

  * All authenticated Novus users can see all projects (no ETS or other BUs).

  * Architecture must support adding:

    * Business-unit scoping.

    * Project-level access control in v3.

* **Data protection**:

  * Server and file store must follow Novus internal best practices for backups and security.

  * All access assumes internal trust model; no explicit encryption requirements beyond what infra provides (can be revisited in later phases).

### **5.2 Audit & Compliance**

* **v1**:

  * Basic “created\_at, created\_by, updated\_at, updated\_by” on core records.

* **v2**:

  * Full audit logging:

    * Project field changes (what changed, who changed it, when).

    * Document uploads/deletions.

    * Tag creation/merge operations.

### **5.3 Performance & Scalability**

* No hard numeric SLAs for v1, but **design targets**:

  * Typical search queries over \~100–1000 projects should feel snappy (\<2–3s perceived).

  * Project detail page load with metadata \+ doc list should be fast.

* Architecture must scale to:

  * Thousands of projects.

  * Many thousands of documents.

  * Larger doc corpus reused by RAG (embedding store should be maintainable).

### **5.4 UX & Usability**

Core UX principle: **ultra low friction data entry is more important than rich search in v1**.

* Minimize clicks to:

  * Create a project.

  * Attach docs.

  * Add core metadata (Tech/Domain/Test Type, etc.).

* Reasonable defaults and auto-suggestions (from RAG) where possible.

* Avoid “SharePoint-style” deep folder navigation and over-complex forms.

* Keyboard-friendly where possible (e.g., tab-through forms, quick tag entry).

### **5.5 Platforms & Devices**

* v1:

  * Desktop web only.

  * Chrome & Edge on Windows officially supported.

* v3:

  * Responsive/mobile support.

* Architecture:

  * Separate backend services and UI so additional frontends (e.g., mobile, browser extension) can be added later.

---

## **6\. High-Level Data Model & Architecture (Conceptual)**

**Core entities (v1):**

* `User` (from AD)

* `Organization` (Client)

* `Contact`

* `Project`

* `Document`

* `Tag` \+ mapping tables

* `SavedSearch` (user & global)

* `BillingInfo` (or fields on Project)

**Relationships:**

* Organization 1–N Projects.

* Project N–M Contacts.

* Project N–1 Internal Owner (User).

* Project 1–N Documents.

* Project N–M Tags (including structured classification tags).

* User 1–N SavedSearch.

**Logical components:**

* **Relational DB** (e.g., SQL Server/PostgreSQL) for metadata.

* **File Store** on internal server for docs.

* **Indexing / RAG layer**:

  * Full-text index over docs \+ selected fields.

  * Embedding store for semantic similarity (v1 infra, v2 UX).

---

## **7\. Roadmap Summary**

**v1 (0–3 months post dev start, then rollout):**

* Core project CRUD.

* Local file storage \+ full-text indexing.

* Classification (structured \+ tags) with AI dedup suggestions.

* AD SSO.

* Bulk import \+ RAG-assisted field suggestions.

* Keyword \+ full-text search with filters.

* Personal \+ global saved searches.

* Basic billing fields.

* Internal-only deployment.

**v2:**

* Natural-language / semantic search UX.

* Tag synonyms / fuzzy searching.

* Monday.com \+ Jira integrations (as described).

* Audit logs.

* Scale to \~1000 projects.

**v3:**

* Pipeline / quoting support.

* Project-level permissions and multi-BU support (ETS, Omnia).

* GitLab integration and richer external tool hooks.

* Migration to robust file storage (SharePoint/OneDrive).

* Mobile / responsive UI.

* Advanced content generation (one-pagers, slide decks).

---

## **8\. Success Metrics**

* **Adoption:**

  * ≥75% of active projects in NPD within 3 months of launch.

  * 100% of active projects within 6 months.

* **Usage:**

  * At least **10 search queries per week** across the system in the first 6 months.

* **Feature delivery:**

  * v1, v2, v3 feature sets (as scoped above) implemented within \~6 months of initial launch.

* **Strategic:**

  * System is robust enough to present to ETS and Omnia as a credible candidate for their needs (even if they don’t adopt it yet).

