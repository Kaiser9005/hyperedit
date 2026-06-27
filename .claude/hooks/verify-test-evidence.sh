#!/bin/bash
# ClipWise — PreToolUse Bash hook (adapted from FOFAL FOF-1197 Phase 0).
# Blocks `git commit` unless a fresh evidence file (< 30 min old) exists for the
# current branch + SHA in .agents/evidence/.
#
# ClipWise LOCAL GATE = pytest (services/test_*.py + pytest in pyproject.toml).
# Write evidence with:   pytest -q services && mkdir -p .agents/evidence && \
#                        echo "$(date) $(git rev-parse --abbrev-ref HEAD) $(git rev-parse --short HEAD)" \
#                        > ".agents/evidence/$(git rev-parse --abbrev-ref HEAD | tr / -)-$(git rev-parse --short HEAD).log"
#
# Wiring: .claude/settings.json PreToolUse Bash matcher.
# Reads tool_input JSON from stdin (Claude Code hook protocol).
# Exit 0 = allow; exit 2 = BLOCK (Claude Code PreToolUse blocking code — stderr shown
# to agent). NOTE: exit 1 is NON-blocking in Claude Code (FOF-1398).
#
# Bypass for emergencies / config-only commits: SKIP_TEST_EVIDENCE=1 (env OR inline
# in the command string; FOF-1398 parity).
#
# Discipline source: F-HOOKIFY-IGNORECASE-FALSE-POSITIVE-1 — split command on shell
# separators BEFORE pattern-matching to avoid quoted-substring false positives.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

# Only enforce on actual `git commit` invocation (not substring inside echo/etc).
if ! printf '%s\n' "$COMMAND" | tr -s '&|;' '\n' | grep -qE '^[[:space:]]*git[[:space:]]+commit([[:space:]]|$)'; then
    exit 0
fi

# Emergency bypass — detected from BOTH the hook env AND the command string.
if [ "${SKIP_TEST_EVIDENCE:-}" = "1" ] \
   || printf '%s' "$COMMAND" | grep -qE '(^|[[:space:]])SKIP_TEST_EVIDENCE=1([[:space:]]|$)'; then
    echo "⚠️  [verify-test-evidence] SKIP_TEST_EVIDENCE=1 — bypass enabled" >&2
    exit 0
fi

EVIDENCE_DIR="${EVIDENCE_DIR:-.agents/evidence}"
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null | tr '/' '-' || echo "nogit")
SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "nogit")
EVIDENCE_FILE="${EVIDENCE_DIR}/${BRANCH}-${SHORT_SHA}.log"

if [ ! -f "$EVIDENCE_FILE" ]; then
    {
        echo ""
        echo "❌ [verify-test-evidence] No test evidence for ${BRANCH}@${SHORT_SHA}."
        echo "   Expected: ${EVIDENCE_FILE}"
        echo "   Run the ClipWise local gate (pytest), then write evidence:"
        echo "       pytest -q services && mkdir -p ${EVIDENCE_DIR} && \\"
        echo "       echo \"\$(date) ${BRANCH} ${SHORT_SHA}\" > ${EVIDENCE_FILE}"
        echo "   Bypass (config-only / emergency): SKIP_TEST_EVIDENCE=1 git commit ..."
        echo ""
    } >&2
    exit 2
fi

# Cross-platform mtime check (macOS BSD stat vs GNU stat)
if stat -f '%m' "$EVIDENCE_FILE" >/dev/null 2>&1; then
    MTIME=$(stat -f '%m' "$EVIDENCE_FILE")
else
    MTIME=$(stat -c '%Y' "$EVIDENCE_FILE")
fi
NOW=$(date +%s)
AGE_SEC=$(( NOW - MTIME ))
MAX_AGE_SEC="${MAX_AGE_SEC:-1800}"  # 30 minutes default; configurable for tests

if [ "$AGE_SEC" -gt "$MAX_AGE_SEC" ]; then
    AGE_MIN=$(( AGE_SEC / 60 ))
    MAX_MIN=$(( MAX_AGE_SEC / 60 ))
    {
        echo ""
        echo "❌ [verify-test-evidence] Test evidence is stale (${AGE_MIN} min old, max ${MAX_MIN} min)."
        echo "   File:   ${EVIDENCE_FILE}"
        echo "   Re-run: pytest -q services  then re-write the evidence file (see no-evidence message)."
        echo "   Bypass: SKIP_TEST_EVIDENCE=1 git commit ...   (emergency only)"
        echo ""
    } >&2
    exit 2
fi

exit 0
