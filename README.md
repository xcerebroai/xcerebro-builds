# Xcerebro Builds Workspace

Autonomous AI development workspace. This is where Jarvis (and spawned subagents) build software, scrapers, dashboards, and apps for real estate intelligence and Xcerebro AI workforce products.

This workspace is operated by [Quentin Flores](https://github.com/xcerebroai) under the Xcerebro AI organization.

---

## What lives here

```
xcerebro-builds/
├── CLAUDE.md                ← Agent constitution. Read first. Always.
├── README.md                ← This file
├── .gitignore               ← What never gets committed
│
├── .claude/                 ← Agent infrastructure (the harness)
│   ├── skills/              ← Reusable patterns the agent loads on demand
│   ├── hooks/               ← Deterministic guardrails (shell scripts)
│   └── subagents/           ← Specialist agent definitions
│
├── projects/                ← Active builds. Each project gets its own folder.
│
├── shared/                  ← Code shared across projects
│   └── lib/                 ← Common utilities (scoring, exports, etc.)
│
└── reference/               ← Reference docs informing all builds
    ├── FRAMEWORK_SPEC.md    ← County intel dashboard framework
    └── SURPLUSIQ_FRAMEWORK.md  ← Surplus business framework
```

---

## How to use this workspace

### Starting a new project

1. Tell Jarvis what to build. Be specific about scope.
2. Jarvis creates `projects/<project-name>/` with its own `CLAUDE.md` (project-level rules)
3. Jarvis builds, tests, commits, and reports back

### Watching autonomous work

- Telegram bot streams real-time activity
- Web UI dashboard at `http://127.0.0.1:18789/` shows live agent state
- Command logger writes audit trail to `~/.openclaw/logs/`

### Adding a new skill

Skills are reusable patterns the agent pulls from on demand. To add one:

1. Create `.claude/skills/<skill-name>/SKILL.md`
2. Write a clear `description` in the frontmatter — that's what the agent matches against
3. Add supporting scripts/templates if needed

Once added, the skill is available to every project automatically.

---

## Multi-model setup

This workspace runs through OpenClaw with OpenRouter as the model provider.

- **Default:** `openrouter/deepseek/deepseek-chat` (DeepSeek V4 Pro) — workhorse for 70-80% of work
- **Escalate to:** `openrouter/anthropic/claude-sonnet-4.5` when DeepSeek fails
- **Last resort:** `openrouter/anthropic/claude-opus-4.7` or `openrouter/openai/gpt-5.5` for production-critical fixes

See `CLAUDE.md` section 5 for the routing rules.

---

## Stack

- **OS:** Windows 11 on AMD Ryzen 7 9800X3D, 124GB RAM, 4TB NVMe
- **Runtime:** Node.js 24, Python 3.12, Git 2.54
- **Harness:** OpenClaw 2026.5.3+
- **Model gateway:** OpenRouter (one API key, all major models)
- **Search:** Tavily (1,000 free searches/month, agent-optimized)
- **Messaging:** Telegram bot
- **Hosting:** GitHub Pages for static dashboards
- **Version control:** GitHub (xcerebroai org)

---

## Operating principles (full list in CLAUDE.md)

- Direct, no fluff
- Push back hard before agreeing
- Stay locked to scope until told to pivot
- Set up right, not fast — there is no rush
- Real sample data before writing parsers
- Single source of truth for filters and counts
- Commit working code immediately, group by concept

---

⚡ — Xcerebro AI
