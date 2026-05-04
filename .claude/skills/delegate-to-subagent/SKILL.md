---
name: delegate-to-subagent
description: Use when a task is well-defined, has a clear deliverable, and would generate a lot of context noise in the main session. Examples: exploring an unfamiliar codebase, running a test suite and reporting failures, doing extensive web research on a specific topic, reviewing a large diff, or building a feature end-to-end while the main session works on something else. Do NOT use for small tasks that can be done inline, or tasks that need ongoing user input.
---

# Skill: Delegate to Subagent

## When this skill fires

The agent (Jarvis) loads this skill when it recognizes a task that should be delegated rather than handled inline. The signal is:

- Task is well-defined with a clear deliverable
- Task would create context-window noise (large file inspection, web research, codebase exploration)
- Task is independent and can run without ongoing user input
- Main session benefits from staying focused on something else

## When NOT to delegate

- Task is small (< 3 tool calls). Just do it inline.
- Task requires deep project context that would have to be re-explained every time.
- Task requires user approval mid-flight.
- Task is ambiguous — clarify with user FIRST.

## Available subagent types

These are defined in `.claude/subagents/`. Use the right one for the job:

| Subagent | Use for |
|----------|---------|
| `code-reviewer` | Reviewing diffs against repo conventions before commit |
| `test-runner` | Running test suite, reporting failures |
| `explorer` | Mapping unknown codebases, returning structural findings |
| `feature-dev` | Designing and implementing end-to-end features |

## How to delegate

### 1. Define the task contract
Before spawning, write out:
- **Goal:** what success looks like
- **Inputs:** which files / data the subagent needs
- **Output:** what it returns to the main session (always ONE message)
- **Constraints:** what it must NOT do

### 2. Spawn with minimum context
Subagents have their own context windows. They should NOT receive the full project history. Give them:
- The relevant CLAUDE.md (always)
- The specific task contract
- Only the files they need

### 3. Wait for the single return message
Subagents return ONE message. Not a stream. Not a conversation. One result.

If the result is incomplete, that's a sign the task wasn't well-scoped. Re-define and retry — don't keep nagging the subagent.

### 4. Integrate findings
The main session integrates the subagent's findings into the current work. The user only ever sees the main session.

## Routing rules for subagent models

Most subagents should run on **Tier 1 (DeepSeek V4 Pro)** — they're doing focused, narrow work where DeepSeek excels.

Exceptions:
- `code-reviewer` runs on **Tier 2 (Claude Sonnet 4.5)** — review quality matters
- `feature-dev` for production-critical features runs on **Tier 3 (Opus 4.7)** — but only with explicit user approval

## Anti-patterns

- **Recursive delegation** — subagents must NOT spawn other subagents. No infinite loops.
- **Chatty subagents** — subagents do not converse with the user. The main session does.
- **Over-delegation** — if 80% of your tasks are spawning subagents, you're avoiding the work. Just do it.
- **Under-scoping** — vague task contracts produce vague results. Define the deliverable first.

## Example

**Bad (no delegation needed):**
> Read `package.json` and tell me the version of `react`.

This is one tool call. Just do it.

**Good (delegate):**
> Explore the entire `projects/some-existing-project/` codebase, identify the main entry points, list every file that touches the database layer, and summarize the data flow from scraper to dashboard.

This is 50+ tool calls. Spawn an `explorer` subagent. Main session stays clean.

---

⚡
