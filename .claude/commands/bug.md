# Bug Command - Create GitHub Issue

Automatically create a GitHub issue for bug reports with intelligent input parsing.

**Project**: Novus Project Database - FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector) + React 19 + Vite + Azure AD SSO

## Bug Philosophy

**What is a Bug?**
- Something is broken or not working as expected
- User-facing issue that impacts functionality
- Requires investigation to find root cause
- Should be fixed with minimal, surgical changes
- More detailed than chores, less complex than features

## Usage

```bash
# Simple bug description
/bug Users cannot search projects - API returns 500 error

# Browser console error
/bug TypeError: Cannot read properties of undefined (reading 'embedding')
at SearchPage.tsx:45

# API error
/bug POST /api/v1/projects returns "column owner_id does not exist"
in backend/app/api/projects.py:73

# Link to GitHub issue
/bug #7
```

## Smart Input Detection

The command intelligently parses different input types:

- **Simple Description**: Natural language description of the issue
- **Error Logs**: Browser console errors with file/line information
- **API Errors**: SQLAlchemy errors, FastAPI errors, TypeScript errors
- **GitHub Issues**: Links to existing issues for reference

## Issue Creation Process

When you call `/bug`, this command will:

1. **Parse your input** - Detect error type or description
2. **Extract details** - Get error messages, file locations, routes
3. **Create GitHub issue** with:
   - **Title**: Clear bug summary
   - **Label**: `bug` (automatically added)
   - **Body**: Detailed issue with error information and investigation guide
4. **Display confirmation** - Show the created issue URL

## GitHub Issue Format

Bug issues include important details to help with investigation:

```markdown
# <Bug summary>

## Reported Issue
**What's broken**: <What the user sees>
**Expected behavior**: <What should happen>
**Severity**: <Critical/High/Medium/Low>

## Error Details
**Error Type**: <TypeError, SQLAlchemy Error, API Error, etc.>
**Error Message**: <Exact error>
**Location**: <file.py:123 or Component.tsx:456>
**URL/Route**: <Affected endpoint>

## How to Reproduce
1. <Step-by-step reproduction>
2. <Include specific test data or conditions>
3. <Result: error, crash, incorrect data, etc.>

## Investigation Notes
- Error pattern detected: <description>
- Likely affected components: <list>
- Related files to check: <list>

## Next Steps
- Investigate root cause (not just symptom)
- Add regression test to prevent recurrence
- Ensure minimal, surgical fix
```

## Severity Guidelines

- **Critical**: App crashes, data loss, security issue, authentication bypass
- **High**: Core feature broken, user cannot complete primary tasks
- **Medium**: Workaround exists, but feature partially broken
- **Low**: Edge case, cosmetic issue, minor inconvenience

## Workflow

1. **Report Bug**: `/bug <description or error>`
2. **Issue Created**: GitHub issue appears with label `bug`
3. **Investigate**: Use `/orchestrate3 gh issue #N` to diagnose and fix
4. **Complete**: Cleanup agent closes issue and commits

---

## Implementation

This command creates a GitHub issue with the `bug` label.

## Bug
$ARGV

When executed, this command will create an issue using:

```bash
gh issue create \
  --title "$ARGV" \
  --body "## Reported Issue
**What's broken**: <What the user sees>
**Expected behavior**: <What should happen>
**Severity**: <Critical/High/Medium/Low>

## Error Details
**Error Type**: <TypeError, SQLAlchemy Error, API Error, etc.>
**Error Message**: <Exact error>
**Location**: <file.py:123 or Component.tsx:456>
**URL/Route**: <Affected endpoint>

## Input/Error Log
$ARGV

## How to Reproduce
1. <Step-by-step reproduction>
2. <Include specific test data or conditions>
3. <Result: error, crash, incorrect data, etc.>

## Investigation Notes
- Error pattern detected: <description>
- Likely affected components: <list>
- Related files to check: <list>

## Next Steps
- Investigate root cause (not just symptom)
- Add regression test to prevent recurrence
- Ensure minimal, surgical fix" \
  --label bug
```
