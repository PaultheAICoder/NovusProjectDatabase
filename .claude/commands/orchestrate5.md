---
command: "/orchestrate5"
category: "Project Orchestration"
purpose: "Execute complete 5-agent workflow (Scout -> Plan -> Build -> Test -> Cleanup)"
---

# Orchestrate5 Command - 5-Agent Workflow

Execute the complete 5-agent workflow for implementing features, fixing bugs, or completing chores. This command orchestrates all agents sequentially without doing any work itself.

**Project**: Novus Project Database - FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector) + React 19 + Vite + Azure AD SSO

**Project Root**: `/home/pbrown/Novus-db`

## CRITICAL: ORCHESTRATION ONLY

**WHEN THE USER TYPES `/orchestrate5`, YOU ARE A CONDUCTOR, NOT A PERFORMER.**

**YOU MUST:**
- Call agents directly via Task tool
- Report agent progress to user
- Read agent outputs
- Summarize results
- Coordinate workflow

**YOU MUST NEVER:**
- Read code files yourself
- Write or edit any code
- Run tests directly
- Create or modify files
- Execute bash commands (except for timing)
- Investigate bugs yourself
- Do ANY implementation work

## Usage

```
/orchestrate5 [input]
```

**Input can be:**
- Plain text description: `/orchestrate5 Add dark mode toggle to settings`
- Github issue: `/orchestrate5 gh issue #17`
- Bug description: `/orchestrate5 Fix null pointer in search service`
- Multiple items: `/orchestrate5 Implement OAuth2 + Add user management`

## Workflow Process

### Phase 1: Scout Agent

**Purpose**: Investigation and analysis

1. Call Scout agent directly
2. Pass input exactly as provided by user
3. Report: "Scout Agent starting..."
4. Wait for Scout agent to complete
5. **Extract AGENT_RETURN**: Scout will end with `AGENT_RETURN: scout-[ISSUE_NUMBER]-[MMDDYY]`

### Phase 2: Plan Agent

**Purpose**: Create detailed implementation plan

1. Use Scout's AGENT_RETURN filename (from Phase 1)
2. Call Plan agent via Task tool
3. Report: "Plan Agent starting..."
4. Wait for Plan agent to complete
5. **Extract AGENT_RETURN**: Plan will end with `AGENT_RETURN: plan-[ISSUE_NUMBER]-[MMDDYY]`

### Phase 3: Build Agent

**Purpose**: Execute implementation

1. Use Plan's AGENT_RETURN filename (from Phase 2)
2. Call Build agent via Task tool
3. Report: "Build Agent starting..."
4. Wait for Build agent to complete
5. **Extract AGENT_RETURN**: Build will end with `AGENT_RETURN: build-[ISSUE_NUMBER]-[MMDDYY]`

### Phase 4: Test Agent

**Purpose**: Validate and fix issues

1. Use Build's AGENT_RETURN filename (from Phase 3)
2. Call Test agent via Task tool
3. Report: "Test Agent starting..."
4. Wait for Test agent to complete
5. **Extract AGENT_RETURN**: Test will end with `AGENT_RETURN: test-[ISSUE_NUMBER]-[MMDDYY]`

### Phase 5: Cleanup Agent

**Purpose**: Document completion, detect future work, finalize

1. Use all AGENT_RETURN filenames (from Phases 1-4)
2. Call Cleanup agent via Task tool
3. Report: "Cleanup Agent starting..."
4. Wait for Cleanup agent to complete
5. **Extract AGENT_RETURN**: Cleanup will end with `AGENT_RETURN: cleanup-[ISSUE_NUMBER]-[MMDDYY]`

### Phase 6: Final Report

```markdown
# 5-Agent Workflow Complete

## Status
Scout -> Plan -> Build -> Test -> Cleanup

## Performance Metrics
- **Total Duration**: [calculated from workflow_start to workflow_end]
- **Scout**: [duration]
- **Plan**: [duration]
- **Build**: [duration]
- **Test**: [duration]
- **Cleanup**: [duration]

## What Was Accomplished
[From cleanup output: summary]

## Files Changed
- Created: [count]
- Modified: [count]

## Testing
- pytest: [X/X tests passed]
- TypeScript Build: [status]

## Documentation
- Completion Report: `completion-docs/[YYYY-MM-DD]-[name].md`

## Future Work Detected
[If any issues created, list them]

## Git Status
- Commit: [hash]
- Pushed: [status]

## Next Steps
1. Review completion report
2. Test locally with docker compose
3. Review future work issues (if any)
4. Decide on next task

**Workflow Complete - Awaiting Your Review**
```

## Special Cases

### GitHub Issue Input

If user provides a GitHub issue (e.g., `/orchestrate5 gh issue #17` or `/orchestrate5 #17`):

1. **Extract issue number**: Parse issue number from input
2. **Pass to Scout**: Scout reads issue via `gh issue view #[number]`
3. **Pass to Cleanup**: Cleanup updates issue with results
4. **Cleanup closes issue**: Only if work is 100% complete and verified
5. **Create related issues**: For significant future work detected (>4 hours)
6. **Report in final output**: Note issue status and links

### Phased Work

If Plan agent detects work is too large and recommends phasing:

1. **Report to user**: "Plan Agent recommends phasing this work"
2. **Show phases**: Display phase breakdown from plan output
3. **Ask user**: "Proceed with Phase 1 only? (yes/no)"
4. **If yes**: Continue with Build/Test/Cleanup for Phase 1 only
5. **If no**: Stop and wait for user decision

### Blocker Scenarios

If any agent encounters a blocker:

1. **Report immediately**: "[Agent] encountered blocker: [description]"
2. **Show blocker details**: From agent's output
3. **Continue if possible**: Other agents may still proceed
4. **Final report shows blockers**: Clearly documented in completion report

## GitHub Issue Progress Updates

When processing a GitHub issue (`/orchestrate5 gh issue #N`), post brief progress comments after each agent completes:

1. **Scout**: What was discovered about the issue (2-3 sentences)
2. **Plan**: Number of tasks, estimated effort, key changes
3. **Build**: What was implemented, files created/modified, build status
4. **Test**: Test results, any fixes made
5. **Cleanup**: Completion report location, future work detected, commit info

## Critical Rules

1. **ORCHESTRATION ONLY - NO DIRECT WORK**
2. **SEQUENTIAL EXECUTION**: Each agent must complete before next starts
3. **REPORT PROGRESS**: Update user on each agent's start/completion
4. **PASS CONTEXT**: Each agent gets exactly what it needs from previous agents
5. **DETECT FUTURE WORK**: Ensure Cleanup creates issues for significant items
6. **VERIFY OUTPUTS**: Check each agent created its output file before proceeding
7. **FINAL REPORT**: Always provide comprehensive summary at end

## Success Criteria

- All 5 agents executed successfully
- All output files created (.agents/outputs/)
- Completion report in completion-docs/
- Future work issues created (if found)
- GitHub issue updated with results (if provided)
- GitHub issue closed if appropriate (if provided and work complete)
- Git committed and pushed
- User receives clear final report
- Workflow stopped, awaiting user review

## Example Usage

```bash
# Bug fix from GitHub issue
/orchestrate5 gh issue #7
/orchestrate5 #7

# Bug fix from description
/orchestrate5 Fix type mismatch in backend/app/services/search_service.py

# Feature from plain text
/orchestrate5 Add CSV export functionality for project search results

# Multiple related items
/orchestrate5 Fix project queries + Add bulk update + Update audit logging
```

## Comparison: 3-Agent vs 5-Agent Workflow

| Aspect | 3-Agent (orchestrate3) | 5-Agent (orchestrate5) |
|--------|------------------------|------------------------|
| Agents | Scout-and-Plan, Build, Test-and-Cleanup | Scout, Plan, Build, Test, Cleanup |
| Handoffs | 2 | 4 |
| Output files | 2 (plan, cleanup) | 4 (scout, plan, build, test, cleanup) |
| Best for | Simpler projects, faster iteration | Complex projects needing detailed audit trail |
