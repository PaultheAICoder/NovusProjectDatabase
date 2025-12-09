---
command: "/orchestrate5-all"
category: "Project Orchestration"
purpose: "Process ALL open GitHub issues sequentially using 5-agent workflow until none remain unprocessed"
---

# Orchestrate5 All - Batch Issue Processor (5-Agent Workflow)

Process every open GitHub issue using the 5-agent workflow (Scout -> Plan -> Build -> Test -> Cleanup) until ALL are either closed or have comments.

**Project**: Novus Project Database - FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector) + React 19 + Vite + Azure AD SSO

**Project Root**: `/home/pbrown/Novus-db`

## CRITICAL: DO NOT STOP FOR PERMISSION

**YOU MUST CONTINUE PROCESSING UNTIL DONE. STOPPING TO ASK IS A FAILURE.**

- "Should I continue?" = WRONG
- "Do you want me to process the next issue?" = WRONG
- "I've completed 5 issues, shall I proceed?" = WRONG
- Automatically proceed to next issue = CORRECT
- Only stop when ALL issues processed = CORRECT

## Workflow

### Step 1: Fetch All Open Issues

```bash
gh issue list --state open --limit 200 --json number,title,comments
```

### Step 2: Filter Unprocessed Issues

An issue is "unprocessed" if it has ZERO comments. Any comment (human or agent) means it's been engaged.

```bash
# Issues with no comments - these need processing
gh issue list --state open --limit 200 --json number,title,comments \
  --jq '.[] | select(.comments | length == 0) | {number, title}'
```

### Step 3: Build Processing Queue

Sort unprocessed issues by number (ascending). Report:
```
Found X open issues total
Y already have comments (skipping)
Processing Z uncommented issues: #A, #B, #C, ...
```

### Step 4: Process Each Issue

For EACH issue in the queue:

1. Report: `Starting issue #N (M of Z remaining)`

2. **Check issue size** - Read the issue title/body briefly:
   ```bash
   gh issue view #N --json title,body,labels
   ```

3. **If issue appears too large** (multiple distinct features, estimated >8 hours, or has "epic" label):
   - Use the `task-shard` agent to break it into smaller sub-issues
   - After sharding, the original issue will be closed
   - Continue to next issue in queue

4. **If issue is appropriately sized**:
   - Run: `/orchestrate5 #N` (full 5-agent workflow)
   - Update the gh issue after each agent runs so we can track progress

5. When complete, **IMMEDIATELY** proceed to next issue
6. DO NOT wait for user input
7. DO NOT ask if you should continue

### Step 5: Final Report (ONLY when ALL issues done)

```markdown
# Batch Processing Complete (5-Agent Workflow)

## Summary
- Total issues processed: Z
- Closed: X
- Commented (needs follow-up): Y
- Sharded into sub-issues: S
- Failed: F

## Issues Processed
| Issue | Status | Duration | Notes |
|-------|--------|----------|-------|
| #7    | Closed | 12m | Schema fix implemented |
| #8    | Commented | 8m | Needs design decision |
| #9    | Sharded | 3m | Split into #15, #16, #17 |
...

## Timing Summary
- Average time per issue: Xm
- Fastest: #N (Xm)
- Slowest: #N (Xm)

## Next Steps
[Any remaining work or issues that need manual attention]
```

## Task-Shard Agent Usage

Use the `task-shard` agent when an issue:
- Contains multiple unrelated features
- Would take more than 8 hours to complete
- Has an "epic" or "large" label
- Scout agent recommends phasing

```
Task({
  subagent_type: "task-shard",
  description: "Shard issue #N into sub-issues",
  prompt: `Analyze GitHub issue #N in this repository.

**Instructions**:
1. Read the issue details via: gh issue view #N
2. Determine optimal decomposition strategy
3. Create smaller, focused sub-issues (each should be completable in 2-4 hours)
4. Link sub-issues to original
5. Close the original issue with a comment listing the sub-issues

**Success**: Original issue closed, sub-issues created and linked`
})
```

## Exit Conditions (ONLY these are acceptable)

1. **All issues processed** - Queue empty (no uncommented open issues remain)
2. **Context limit warning** - Proactively warn at 80% usage, complete current issue, then stop
3. **Critical unrecoverable error** - Document and continue to next issue if possible

## Anti-Patterns (NEVER DO THESE)

1. Stop after arbitrary number of issues
2. Ask "should I continue?"
3. Wait for user confirmation between issues
4. Summarize progress and pause
5. "I've made good progress, let me know if..."
6. Process issues that already have comments (for 5-agent, we skip commented issues)

## The Prime Directive

**Your job is not done until all open issues have at least one comment.**

```bash
# Success = this returns nothing
gh issue list --state open --limit 200 --json number,comments \
  --jq '.[] | select(.comments | length == 0) | .number'
```

Process. Continue. Repeat. Only stop when finished.

## Comparison: orchestrate3-all vs orchestrate5-all

| Aspect | orchestrate3-all | orchestrate5-all |
|--------|------------------|------------------|
| Workflow | 3-agent (Scout-and-Plan, Build, Test-and-Cleanup) | 5-agent (Scout, Plan, Build, Test, Cleanup) |
| Speed | Faster (fewer handoffs) | More thorough |
| Use when | Standard issues, faster iteration | Complex issues needing detailed audit trail |
| Skips commented | No (processes all) | Yes (only uncommented) |
| Task-shard | Supported | Supported |
