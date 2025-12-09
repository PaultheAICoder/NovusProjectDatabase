---
command: "/orchestrate3-all"
category: "Project Orchestration"
purpose: "Process ALL open GitHub issues sequentially using 3-agent workflow until none remain unprocessed"
---

# Orchestrate3 All - Batch Issue Processor (3-Agent Workflow)

Process every open GitHub issue using the 3-agent workflow (Scout-and-Plan -> Build -> Test-and-Cleanup) until ALL are either closed or have comments.

**Project**: Novus Project Database - FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector) + React 19 + Vite + Azure AD SSO

**Project Root**: `/home/pbrown/Novus-db`

## CRITICAL: ORCHESTRATION ONLY

**YOU ARE A CONDUCTOR, NOT A PERFORMER.**

**YOU MUST:**
- Run `/orchestrate3 #N` for each issue via SlashCommand tool
- Use `task-shard` agent for issues that are too large
- Update GitHub issues with brief progress comments
- Track timing for each issue
- Report progress between issues

**YOU MUST NEVER:**
- Read code files yourself
- Write or edit any code
- Run tests directly
- Create or modify source files
- Execute implementation commands
- Investigate bugs yourself
- Do ANY implementation work

**Your ONLY job is to call `/orchestrate3` for each issue and use `task-shard` when needed. Nothing more.**

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
gh issue list --state open --limit 200 --json number,title,labels
```

### Step 2: Build Processing Queue

Process ALL open issues regardless of comment status. The scout-and-plan agent reads the full issue including all comments via `gh issue view`, so existing comments provide helpful context.

Sort issues by number (ascending). Report:
```
Found X open issues to process: #A, #B, #C, ...
```

### Step 3: Process Each Issue

For EACH issue in the queue:

1. Report: `Starting issue #N (M of Z remaining)`

2. **Check issue size** - Read the issue title/body briefly:
   ```bash
   gh issue view #N --json title,body,labels
   ```

3. **If issue appears too large** (multiple distinct features, estimated >8 hours, or has "epic" label):
   - Use the `task-shard` agent to break it into smaller sub-issues:
   ```
   Task({
     subagent_type: "task-shard",
     description: "Shard large issue #N",
     prompt: "Analyze GitHub issue #N and break it into smaller, manageable sub-issues. Create the sub-issues and close the original."
   })
   ```
   - After sharding, the original issue will be closed
   - Continue to next issue in queue (new sub-issues will be picked up in future runs)

4. **If issue is appropriately sized**:
   - Run: `/orchestrate3 #N` (3-agent workflow)
   - The orchestrate3 command will:
     - Run Scout-and-Plan agent
     - Run Build agent
     - Run Test-and-Cleanup agent
     - Post brief comments to GitHub issue after each agent
     - Track timing in `.agents/timing/`

5. When `/orchestrate3` completes, **IMMEDIATELY** proceed to next issue
6. DO NOT wait for user input
7. DO NOT ask if you should continue

### Step 4: Final Report (ONLY when ALL issues done)

```markdown
# Batch Processing Complete (3-Agent Workflow)

## Summary
- Total issues processed: Z
- Closed: X
- Sharded into sub-issues: S
- Blocked (needs manual intervention): Y
- Failed: F

## Issues Processed
| Issue | Status | Duration | Notes |
|-------|--------|----------|-------|
| #7    | Closed | 12m | Schema fix implemented |
| #8    | Sharded | 2m | Split into #15, #16, #17 |
| #9    | Blocked | 8m | Needs design decision from user |
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
- Scout-and-Plan recommends phasing

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

1. **All issues processed** - Queue empty (no open issues remain)
2. **Context limit warning** - Proactively warn at 80% usage, complete current issue, then stop
3. **Critical unrecoverable error** - Document and continue to next issue if possible

## Anti-Patterns (NEVER DO THESE)

1. Stop after arbitrary number of issues
2. Ask "should I continue?"
3. Wait for user confirmation between issues
4. Summarize progress and pause
5. "I've made good progress, let me know if..."
6. Read code files directly (let agents do it)
7. Write any code yourself
8. Run tests directly (let agents do it)

## The Prime Directive

**Your job is not done until all open issues are closed.**

```bash
# Success = this returns nothing
gh issue list --state open --limit 200 --json number
```

Process. Continue. Repeat. Only stop when finished.

## Comparison: orchestrate3-all vs orchestrate5-all

| Aspect | orchestrate3-all | orchestrate5-all |
|--------|------------------|------------------|
| Workflow | 3-agent (Scout-and-Plan, Build, Test-and-Cleanup) | 5-agent (Scout, Plan, Build, Test, Cleanup) |
| Speed | Faster (fewer handoffs) | More thorough |
| Use when | Standard issues, faster iteration | Complex issues needing detailed audit trail |
| Task-shard | Supported | Supported |
