# Feature Command - Create GitHub Issue

Automatically create comprehensive GitHub issue for new features with intelligent questions.

**Project**: Novus Project Database - FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector) + React 19 + Vite + Azure AD SSO

## Feature Philosophy

**What is a Feature?**
- New functionality that adds value to the system
- User-facing capability that wasn't previously available
- May involve database changes, backend APIs, and frontend UI
- Should follow existing patterns in the codebase
- Most complex category requiring detailed planning

## Usage

```bash
# Interactive feature creation (with questions)
/feature

# Quick feature creation from description
/feature Add bulk document re-indexing with embedding regeneration
```

## Interactive Feature Creation

When you call `/feature` without arguments, you'll be asked clarifying questions to create a comprehensive issue:

1. **What's the feature about?** - Brief summary
2. **Who benefits?** - Novus staff users or admins
3. **What's the main action?** - What can users do?
4. **Why does it matter?** - Business value
5. **What data is involved?** - New tables, modifications, or just UI?
6. **Any dependencies?** - Other features that must complete first?

## GitHub Issue Format

Feature issues are the most comprehensive, including user stories and technical context:

```markdown
# <Feature name>

## Feature Description
<Purpose and value to users>

## User Stories

### Primary User Story
**As a** Novus staff member
**I want to** <action>
**So that** <business value>

### Additional User Stories (if applicable)
**As a** <role>
**I want to** <action>
**So that** <business value>

## Requirements

### Functional Requirements
- [ ] <Specific capability needed>
- [ ] <Data to be captured/displayed>
- [ ] <Workflow or process>

### Non-Functional Requirements
- [ ] Performance: <Specific targets if applicable>
- [ ] Privacy: <Data handling requirements>
- [ ] Reliability: <Error handling, fallbacks>

## Technical Context

### Affected Areas
- **Database**: <New tables or migrations>
- **Backend**: <API routes, services>
- **Frontend**: <Pages, components, tables>
- **External APIs**: <External services if any>

### Related Features
<Any existing features this builds on or connects to>

### Data Involved
- **New Tables**: <List if applicable>
- **Modified Tables**: <List if applicable>
- **Relationships**: <How data connects>

### Dependencies
- **Prerequisites**: <Must complete first>
- **Blocks**: <What work this enables>

## Acceptance Criteria
- [ ] <Specific capability working>
- [ ] <User can perform action>
- [ ] <Data persists and displays correctly>
- [ ] <Proper authentication enforced>
- [ ] <All tests passing>

## Notes
- Estimated complexity: <Small/Medium/Large>
- May require phasing: <Yes/No>
- Design pattern to follow: <Similar feature reference>
```

## Feature Complexity Guidelines

### Small Feature (4-8 hours)
- UI-only changes (new widget, display tweaks)
- Single table modifications (new column, validation)
- Simple calculations or filtering
- **Examples**: Add field to project form, new dashboard widget, simple API endpoint

### Medium Feature (8-16 hours)
- New service implementation
- New API route with database integration
- Frontend + Backend + Database work
- **Examples**: New search filter type, export to new format, tag management improvements

### Large Feature (16+ hours - should be phased)
- Complex workflows with multiple steps
- Multiple related resources
- Significant UI changes
- External API integrations
- **Examples**: Full RAG pipeline upgrade, multi-document comparison, external ERP integration

## Workflow

1. **Create Feature**: `/feature` or `/feature <description>`
2. **Answer Questions**: Clarify feature scope and details (if interactive)
3. **Issue Created**: GitHub issue appears with label `enhancement`
4. **Plan & Build**: Use `/orchestrate3 gh issue #N` to implement
5. **Complete**: Cleanup agent closes issue and commits

---

## Implementation

This command creates a GitHub issue with the `enhancement` label.

## Feature
$ARGV

When executed, this command will create an issue using:

```bash
gh issue create \
  --title "$ARGV" \
  --body "## Feature Description
$ARGV

## User Stories

### Primary User Story
**As a** Novus staff member
**I want to** <action>
**So that** <business value>

## Requirements

### Functional Requirements
- [ ] <Specific capability needed>
- [ ] <Data to be captured/displayed>
- [ ] <Workflow or process>

### Non-Functional Requirements
- [ ] Performance: <Specific targets if applicable>
- [ ] Privacy: <Data handling requirements>
- [ ] Reliability: <Error handling, fallbacks>

## Technical Context

### Affected Areas
- **Database**: <New tables or migrations>
- **Backend**: <API routes, services>
- **Frontend**: <Pages, components, tables>
- **External APIs**: <External services if any>

### Data Involved
- **New Tables**: <List if applicable>
- **Modified Tables**: <List if applicable>
- **Relationships**: <How data connects>

### Dependencies
- **Prerequisites**: <Must complete first>
- **Blocks**: <What work this enables>

## Acceptance Criteria
- [ ] <Specific capability working>
- [ ] <User can perform action>
- [ ] <Data persists and displays correctly>
- [ ] <Proper authentication enforced>
- [ ] <All tests passing>

## Notes
- Estimated complexity: <Small/Medium/Large>
- May require phasing: <Yes/No>
- Design pattern to follow: <Similar feature reference>" \
  --label enhancement
```
