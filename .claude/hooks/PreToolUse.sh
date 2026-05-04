#!/bin/bash
# ============================================================
# PreToolUse.sh — Xcerebro workspace safety guardrail
# ============================================================
# Fires before any tool call the agent attempts.
# Blocks dangerous commands. Logs everything.
#
# Exit codes:
#   0  = allow the tool call
#   2  = block the tool call (non-zero stops execution)
# ============================================================

# Read the tool call from stdin (OpenClaw passes JSON)
INPUT=$(cat)

# Pull the command being run
TOOL_NAME=$(echo "$INPUT" | grep -oP '"tool_name":\s*"\K[^"]+' | head -1)
COMMAND=$(echo "$INPUT" | grep -oP '"command":\s*"\K[^"]+' | head -1)

# ============================================================
# AUDIT LOG — every tool call gets recorded
# ============================================================
LOG_DIR="$HOME/.openclaw/logs"
mkdir -p "$LOG_DIR"
echo "[$(date -Iseconds)] $TOOL_NAME :: $COMMAND" >> "$LOG_DIR/pretooluse.log"

# ============================================================
# BLOCKED PATTERNS — never allow these to run
# ============================================================

# rm -rf on root or user home
if echo "$COMMAND" | grep -qE 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+(/|\$HOME|~|/home|/Users|C:|C:\\)'; then
    echo "BLOCKED: rm -rf targeting protected path. Refusing." >&2
    exit 2
fi

# Disk format / wipe commands
if echo "$COMMAND" | grep -qE '(mkfs|dd\s+if=.*of=/dev|format\s+[A-Za-z]:|del\s+/[sS])'; then
    echo "BLOCKED: disk-destructive command refused." >&2
    exit 2
fi

# Modifying system directories on Windows
if echo "$COMMAND" | grep -qE '(C:\\Windows|C:\\Program Files|C:/Windows|C:/Program Files)'; then
    echo "BLOCKED: modification of Windows system directory refused." >&2
    exit 2
fi

# Touching the .openclaw config directly (bypasses approvals)
if echo "$COMMAND" | grep -qE '\.openclaw/openclaw\.json' && echo "$COMMAND" | grep -qE '(>|>>|sed -i|rm)'; then
    echo "BLOCKED: direct edit of openclaw.json. Use 'openclaw config set' instead." >&2
    exit 2
fi

# Reading or transmitting .env files
if echo "$COMMAND" | grep -qE '(cat|less|more|tail|head|curl.*--data|curl.*-d).*\.env\b'; then
    echo "BLOCKED: .env files contain secrets. Refusing read/transmit." >&2
    exit 2
fi

# Force pushing to main
if echo "$COMMAND" | grep -qE 'git\s+push.*-(-force|f).*\b(main|master)\b'; then
    echo "BLOCKED: force push to main/master requires manual approval." >&2
    exit 2
fi

# ============================================================
# WARN PATTERNS — log a warning but allow
# ============================================================

# Global package install
if echo "$COMMAND" | grep -qE '(npm\s+install\s+-g|npm\s+i\s+-g|pip\s+install.*--user|pip\s+install\s+--break-system-packages)'; then
    echo "[WARN] $(date -Iseconds) global install: $COMMAND" >> "$LOG_DIR/pretooluse.log"
fi

# Pushing to remote
if echo "$COMMAND" | grep -qE 'git\s+push'; then
    echo "[INFO] $(date -Iseconds) git push: $COMMAND" >> "$LOG_DIR/pretooluse.log"
fi

# ============================================================
# Allow the tool call
# ============================================================
exit 0
