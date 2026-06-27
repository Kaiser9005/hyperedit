#!/bin/bash
# Insights-gap-audit Tier-1 #3 — PreToolUse Bash hook.
# Guards package-lock.json regeneration. The /insights report (2026-05-31) cites a
# bare-regeneration that pruned 817 lines and broke `npm ci`.
#
# Two tiers (per the "gate the dangerous op, advise the routine one" decision):
#   - BARE `npm install` / `npm i` (no package arg) and `rm … && npm install`
#     → FULL regeneration → SOFT-GATE: block first attempt, proceed on confirm.
#   - `npm install <pkg>` (targeted add) → low-risk → ADVISORY: warn + PROCEED (exit 0).
#
# Allowed SILENTLY (never gated, never warned): `npm ci` (lock-respecting),
# `npm install -g/--global/--location=global` (no project lock), `--help`/`-h`,
# `--dry-run`, and anything that isn't a real `npm install`/`npm i`.
#
# The classifier errs toward ADVISORY when ambiguous (e.g. a flag value that looks
# like a package) so a routine targeted add is NEVER mis-gated.
#
# Reads tool_input JSON from stdin. Exit 0 = allow (silent or advisory); exit 2 = soft-block.
# Confirm token (for the bare gate): CONFIRM_NPM_INSTALL=1  (also: SKIP_NPM_INSTALL_GUARD=1).
# Detected from BOTH the hook env AND the command string, so the inline form works reliably.

set -uo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

# Is any segment a real `npm install`/`npm i`? (split on separators, anchored)
echo "$COMMAND" | tr -s '&|;' '\n' \
  | grep -qE '^[[:space:]]*npm[[:space:]]+(install|i)([[:space:]]|$)' || exit 0

# Confirmed / bypassed (env OR inline in the command string) → allow silently.
if [ "${CONFIRM_NPM_INSTALL:-}" = "1" ] || [ "${SKIP_NPM_INSTALL_GUARD:-}" = "1" ] \
   || echo "$COMMAND" | grep -qE '(^|[[:space:]])(CONFIRM_NPM_INSTALL|SKIP_NPM_INSTALL_GUARD)=1([[:space:]]|$)'; then
    exit 0
fi

SEG=$(echo "$COMMAND" | tr -s '&|;' '\n' | grep -E '^[[:space:]]*npm[[:space:]]+(install|i)([[:space:]]|$)' | head -1 | sed 's/^[[:space:]]*//')

# Safe / non-lock-mutating variants → allow silently.
if echo "$SEG" | grep -qE '(^|[[:space:]])(-g|--global|--location=global|--help|-h|--dry-run)([[:space:]]|$)'; then
    exit 0
fi

# Classify BARE (full regen) vs PKG (targeted add). Errs toward PKG when ambiguous.
MODE=$(python3 - "$SEG" <<'PY'
import sys, shlex
try:
    toks = shlex.split(sys.argv[1])
except Exception:
    print("PKG"); sys.exit(0)   # unparseable → advise (never mis-gate)
rest = []
for j in range(len(toks) - 1):
    if toks[j] == 'npm' and toks[j + 1] in ('install', 'i'):
        rest = toks[j + 2:]; break
mode = "BARE"
for t in rest:
    if not t.startswith('-'):     # any positional token → a package spec
        mode = "PKG"; break
print(mode)
PY
)

if [ "$MODE" = "PKG" ]; then
    {
        echo ""
        echo "ℹ️  [guard-package-lock] '${SEG}' updates package-lock.json."
        echo "   After it lands: review 'git diff --stat package-lock.json' before committing the lock."
        echo "   (advisory; proceeding)"
        echo ""
    } >&2
    exit 0
fi

# BARE → full regeneration → soft-gate.
{
    echo ""
    echo "⚠️  [guard-package-lock] '${SEG}' is a BARE install — it FULLY regenerates package-lock.json."
    echo "   A bad regeneration once pruned 817 lines and broke 'npm ci' (insights report 2026-05-31)."
    echo "   If you intend this, re-run with the confirm token:"
    echo "       CONFIRM_NPM_INSTALL=1 ${SEG}"
    echo "   After it completes: review 'git diff --stat package-lock.json' and confirm"
    echo "   'npm ci' still resolves BEFORE committing the lock. Never auto-regenerate."
    echo "   Not gated: 'npm ci', 'npm install <pkg>' (advisory), 'npm install -g …', '--dry-run'."
    echo ""
} >&2
exit 2
