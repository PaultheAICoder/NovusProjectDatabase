---
command: "/analyze-issue-completion"
category: "Issue Management"
purpose: "Deep dive investigation of GitHub issues to determine completion status and closure readiness"
---

# Analyze Issue Completion Command

Conduct comprehensive investigation of GitHub issues to determine completion status, identify blockers, and take appropriate closure/follow-up actions.

**Project**: Novus Project Database - FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector) + React 19 + Vite + Azure AD SSO

**Project Root**: `/home/pbrown/Novus-db`

## Usage

```
/analyze-issue-completion [issue-numbers...]
```

**Examples:**
```
/analyze-issue-completion 7
/analyze-issue-completion 7 8 9 10 11
/analyze-issue-completion #7 #8 #9
```

## Investigation Process

For each issue provided, conduct a comprehensive analysis following these steps:

### 1. Current Status Analysis

**GitHub Investigation:**
- Read issue via `gh issue view [number]` to get description, labels, comments, status
- Check issue metadata: assignees, milestones, projects, creation date
- Review all issue comments for status updates, blockers, or completion notes
- Identify linked issues (parent, children, blocking, blocked-by)

**Local Documentation Review:**
- Search `completion-docs/` for completion reports mentioning the issue
- Search `.agents/outputs/` for agent output files related to the issue
- Check git log for commits mentioning the issue number
- Review any related files

**Status Determination:**
- Calculate completion percentage (0-100%)
- Identify current phase: Not Started / In Progress / Blocked / Testing / Complete
- Document blocking issues or dependencies (if any)
- Identify who worked on it last (from git commits or issue comments)

### 2. Implementation Status Review

**Code Changes:**
- Use `git log --grep="#[issue-number]"` to find related commits
- Read modified files to understand what was implemented
- Check if implementation matches issue acceptance criteria
- Identify any TODO comments or incomplete sections

**Test Coverage:**
- Check for test files related to the issue
- Determine test results: Passing / Failing / Not Written
- Review test coverage percentage (if applicable)
- Document any known test failures or gaps

**Quality Assessment:**
- TypeScript compilation status
- Build status
- Linting compliance
- Documentation completeness

### 3. Closure Assessment

**Completion Criteria:**
- Compare implementation against issue acceptance criteria
- Verify all subtasks completed (if issue has checklist)
- Confirm no blocking bugs or regressions
- Validate test coverage adequate

**Closure Decision Matrix:**

| Status | Criteria | Action |
|--------|----------|--------|
| **CLOSE** | 100% complete, all tests passing, no blockers | Close with completion comment |
| **NEEDS_WORK** | 80-99% complete, minor issues remaining | Create follow-up issue(s), close parent |
| **DECOMPOSE** | Large scope, multiple distinct work items | Create phase issues, close parent with links |
| **BLOCKED** | Cannot proceed due to external dependencies | Document blocker, keep open |
| **INCOMPLETE** | <80% complete | Keep open, update with status |

### 4. Deliverables

Create a comprehensive markdown report with the following structure:

```markdown
# Issue Completion Analysis Report

**Analysis Date**: [YYYY-MM-DD]
**Issues Analyzed**: [count]

---

## Issue #[NUMBER]: [Title]

### Summary
- **Status**: [Open/Closed]
- **Labels**: [label1, label2, ...]
- **Created**: [date]
- **Last Updated**: [date]
- **Linked Issues**: [list]

### Completion Assessment
- **Completion Percentage**: [0-100%]
- **Current Phase**: [Not Started / In Progress / Blocked / Testing / Complete]
- **Implementation Status**: [Complete / Partial / Not Started]
- **Test Status**: [All Passing / Some Failing / Not Written / N/A]

### Work Completed
[Detailed summary of what has been implemented]

**Commits:**
- [commit hash]: [commit message]

**Files Modified:**
- [file path] - [description]

**Tests:**
- [test file] - [status]

### Blockers & Dependencies
[List any blocking issues, dependencies, or technical challenges]

### Closure Recommendation

**Decision**: [CLOSE / NEEDS_WORK / DECOMPOSE / BLOCKED / INCOMPLETE]

**Rationale**: [Detailed explanation]

---

## Overall Summary

### Issues Ready to Close
- Issue #[NUMBER]: [Title] - [brief reason]

### Issues Needing Follow-Up Work
- Issue #[NUMBER]: [Title] - [estimated effort remaining]

### Issues to Decompose
- Issue #[NUMBER]: [Title] - [number of child issues needed]

### Issues Blocked
- Issue #[NUMBER]: [Title] - [blocking issue/dependency]

### Issues Incomplete (Keep Open)
- Issue #[NUMBER]: [Title] - [completion percentage]

### Total Effort Remaining
[sum of estimated effort for all incomplete work]
```

Save report to: `.claude/reports/issue-analysis-[YYYY-MM-DD].md`

### 5. Follow-Up Actions

After creating the report, take appropriate actions for each issue:

#### For Issues Ready to Close (CLOSE)

```bash
gh issue close [number] --comment "Issue Analysis Complete - Closing

This issue has been analyzed and determined to be 100% complete.

**Completion Summary:**
[Brief summary of what was accomplished]

**Tests:** [All passing / N/A]

Closing as complete."
```

#### For Issues Needing Follow-Up Work (NEEDS_WORK)

1. Create new follow-up issue(s) for remaining work
2. Comment on parent issue with follow-up link
3. Close parent issue

#### For Issues to Decompose (DECOMPOSE)

1. Create child issues for each work phase
2. Update parent issue with decomposition
3. Close parent issue

#### For Blocked Issues (BLOCKED)

```bash
gh issue comment [number] --body "Issue Analysis - Currently Blocked

This issue cannot proceed due to the following blocker(s):

**Blocking Issue(s):**
- #[blocking-issue]: [description]

Keeping this issue open. Will revisit after blocker is resolved."
```

#### For Incomplete Issues (INCOMPLETE)

```bash
gh issue comment [number] --body "Issue Analysis - Work In Progress

**Current Status:** [completion percentage]% complete

**What's Done:**
- [completed item 1]
- [completed item 2]

**What's Remaining:**
- [remaining item 1]
- [remaining item 2]

Keeping this issue open for continued work."
```

## Critical Rules

1. **DO NOT close issues prematurely**: Only close issues that are 100% complete with all acceptance criteria met
2. **DO NOT make assumptions**: If unclear, read the actual code, tests, and documentation
3. **DO provide evidence**: Include commit hashes, file paths, test results in your analysis
4. **DO create follow-up issues**: Better to have small, tracked issues than leave work undocumented
5. **DO update issue comments**: Always comment on issues before closing to document the decision
6. **DO preserve context**: When creating follow-up issues, include sufficient background from parent issue

## Output Format

After completing all follow-up actions, provide a summary to the user:

```markdown
# Issue Completion Analysis Complete

**Issues Analyzed**: [count]

## Actions Taken

### Closed Issues ([count])
- #[number]: [Title] - [reason]

### Follow-Up Issues Created ([count])
- #[new-number] (from #[parent]): [Title]

### Decomposed Issues ([count])
- #[parent] decomposed into:
  - Phase 1: #[child1]
  - Phase 2: #[child2]

### Issues Kept Open ([count])
- #[number]: [Title] - [reason]

## Summary

- **Issues Closed**: [count]
- **Follow-Up Issues Created**: [count]
- **Total Remaining Effort**: [hours]
- **Report Location**: `.claude/reports/issue-analysis-[date].md`

All actions complete. Issues properly triaged and documented.
```

## Notes

- This command performs read-only analysis first, then takes write actions (closing issues, creating new issues) based on findings
- Always create the analysis report before taking any GitHub actions
- Use the Task tool with `subagent_type: "scout"` for complex investigation work
- This command should be used periodically (weekly/monthly) for issue hygiene
- Prefer decomposition over keeping large issues open indefinitely
