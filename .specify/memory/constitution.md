<!--
SYNC IMPACT REPORT
==================
Version Change: N/A → 1.0.0 (initial ratification)
Modified Principles: N/A (new constitution)
Added Sections:
  - Core Principles (5 principles)
  - Development Standards
  - Quality Gates
  - Governance
Removed Sections: N/A
Templates Requiring Updates:
  - .specify/templates/plan-template.md ✅ (compatible)
  - .specify/templates/spec-template.md ✅ (compatible)
  - .specify/templates/tasks-template.md ✅ (compatible)
  - .specify/templates/checklist-template.md ✅ (compatible)
  - .specify/templates/agent-file-template.md ✅ (compatible)
Follow-up TODOs: None
-->

# Novus Project Database Constitution

## Core Principles

### I. Iterative Delivery

Development follows an iterative, working-software-first approach. Each iteration MUST
deliver demonstrable functionality that can be tested and validated by stakeholders.

- Features MUST be broken into independently deployable increments
- Working software takes priority over comprehensive documentation
- Feedback from each iteration MUST inform subsequent development
- MVP (Minimum Viable Product) slices MUST be identified for each feature
- Refactoring and improvement happens based on real usage, not speculation

**Rationale**: The PRD emphasizes adoption as a key success metric. Users MUST see value
quickly; waiting for perfect software guarantees failure.

### II. PRD Alignment

All implementation decisions MUST trace back to the Novus Database PRD v1 requirements.
Features not specified in the PRD are out of scope unless explicitly approved.

- v1 scope boundaries (§2.1) define what MUST and MUST NOT be built
- "Out of scope but must not be blocked" items require architectural consideration
  without implementation
- Success metrics (§8) define measurable outcomes that implementations MUST support
- Field requirements (§4.1) define mandatory vs optional data — no additions without
  approval

**Rationale**: Scope creep is the primary risk for internal tools. The PRD represents
stakeholder agreement; deviation wastes resources.

### III. Usability First

Ultra-low friction data entry is more important than feature richness. Every user
interaction MUST be evaluated against the "easier than doing nothing" bar.

- Minimize clicks for core operations: create project, attach docs, add metadata
- Reasonable defaults and auto-suggestions MUST reduce manual entry
- Avoid "SharePoint-style" deep folder navigation and over-complex forms
- Keyboard-friendly interactions where practical (tab-through forms, quick tag entry)
- Chrome and Edge on Windows are the only supported browsers for v1

**Rationale**: Per PRD §1.2 — NPD MUST be "easier and faster than doing nothing or using
SharePoint" or it won't be adopted.

### IV. Internal Security Model

NPD operates under an internal trust model with Active Directory authentication. Security
controls MUST be appropriate for internal-only deployment without over-engineering.

- AD-based SSO is REQUIRED for authentication
- All authenticated Novus users can view all projects (no per-project ACL in v1)
- Application is reachable only over corporate network/VPN
- No public internet exposure
- Architecture MUST support future addition of business-unit scoping and project-level
  access control (v3) without requiring rewrite

**Rationale**: Per PRD §5.1 — internal trust model with AD auth. Over-engineering
security for an internal tool delays delivery without adding value.

### V. Extensible Architecture

Technical decisions MUST preserve the ability to evolve toward v2/v3 capabilities without
major rework. Abstractions are justified only when they enable documented future
requirements.

- File storage layer MUST be abstracted (local v1 → SharePoint/OneDrive v3)
- Data model MUST support pipeline states even if UI doesn't expose them in v1
- RAG infrastructure (embeddings, chunked text) MUST be built for v1 even if semantic
  search UX is v2
- Monday.com/Jira/GitLab URL fields enable future API integration without schema changes
- Database schema MUST support audit fields (created_at, created_by, updated_at,
  updated_by) from day one

**Rationale**: Per PRD §2.2/§2.3 — v2 and v3 features are explicitly documented. Building
a system that blocks these would be a failure, but implementing them prematurely is
equally wasteful.

## Development Standards

### Code Quality

- All code MUST pass linting before merge (language-specific tooling)
- Formatting MUST be automated and consistent (no style debates in reviews)
- Code review is REQUIRED for all changes to main branch
- Self-documenting code preferred; comments explain "why" not "what"

### Testing Strategy

- Integration tests MUST cover critical user journeys (project CRUD, search, document
  upload)
- Unit tests are RECOMMENDED for complex business logic
- Manual testing against acceptance criteria is acceptable for v1 given adoption priority
- Test coverage requirements may increase for v2+ once baseline stability is proven

### Performance Targets

Per PRD §5.3:
- Search queries over 100-1000 projects: < 2-3 seconds perceived latency
- Project detail page load: fast (sub-second target)
- Architecture MUST scale to thousands of projects and many thousands of documents

## Quality Gates

Before any feature is considered complete:

1. **PRD Traceability**: Implementation maps to specific PRD section
2. **User Journey Validation**: At least one end-to-end user flow works
3. **No Regressions**: Existing functionality still works
4. **Browser Compatibility**: Tested in Chrome and Edge on Windows
5. **AD Authentication**: Verified with real AD credentials

## Governance

This constitution supersedes informal practices and ad-hoc decisions. All implementation
choices MUST be justifiable against these principles.

### Amendment Process

1. Propose change with rationale tied to project goals or discovered constraints
2. Document impact on existing work
3. Update constitution version per semantic versioning:
   - MAJOR: Principle removal or redefinition (breaking governance change)
   - MINOR: New principle or material expansion of existing guidance
   - PATCH: Clarifications, wording improvements, non-semantic refinements
4. Update dependent artifacts (templates, plans) as needed

### Compliance

- All PRs/reviews SHOULD verify alignment with principles
- Complexity MUST be justified against the Usability First and PRD Alignment principles
- Deviations require explicit documentation and approval

**Version**: 1.0.0 | **Ratified**: 2025-12-01 | **Last Amended**: 2025-12-01
