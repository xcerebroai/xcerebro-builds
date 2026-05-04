#!/bin/bash
# ============================================================
# PostToolUse.sh — runs AFTER each tool call completes
# ============================================================
# Use for: audit logging, post-write linting, success notifications
# ============================================================

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | grep -oP '"tool_name":\s*"\K[^"]+' | head -1)
EXIT_CODE=$(echo "$INPUT" | grep -oP '"exit_code":\s*\K[0-9]+' | head -1)

LOG_DIR="$HOME/.openclaw/logs"
mkdir -p "$LOG_DIR"
echo "[$(date -Iseconds)] $TOOL_NAME completed exit=$EXIT_CODE" >> "$LOG_DIR/posttooluse.log"

# ============================================================
# Note failures for the agent to see
# ============================================================
if [ "$EXIT_CODE" != "0" ] && [ -n "$EXIT_CODE" ]; then
    echo "[FAIL] $(date -Iseconds) $TOOL_NAME exit=$EXIT_CODE" >> "$LOG_DIR/failures.log"
fi

exit 0
