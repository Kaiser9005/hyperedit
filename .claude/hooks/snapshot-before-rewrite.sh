#!/bin/bash
# Insights-gap-audit Tier-1 #4 — PreToolUse Bash hook (SNAPSHOT-ONLY, never blocks).
# Before a history-rewriting / destructive git op, capture a recoverable snapshot so a
# bad rebase/cherry-pick/checkout/switch/reset can be undone. The /insights report
# (2026-05-31) cites a catastrophic rebase that dropped stream-lock rows + a
# detached-HEAD recovery.
#
# Mechanism (NON-INTRUSIVE — does NOT touch the working tree or the stash stack):
#   `git stash create` builds a commit object capturing the current dirty state without
#   modifying anything; we park it under refs/snapshots/<ts>-<op>. The pre-op HEAD is
#   also reported (reflog preserves committed positions; what reflog CANNOT recover is
#   discarded UNCOMMITTED work — exactly what `git stash create` captures).
#
# Scope (Option 1):
#   rebase, cherry-pick, reset --hard → snapshot ALWAYS (note HEAD; + worktree ref if dirty)
#   checkout, switch                  → snapshot ONLY if the tree is dirty (clean switch is reflog-safe)
#   `git reset` WITHOUT --hard         → ignored (not destructive to the working tree)
#   cd-redirected commands             → skipped (would snapshot the wrong repo)
#
# Exit 0 always. No auto-rollback this pass (snapshot primitive only).
# Bypass: SKIP_GIT_SNAPSHOT=1 (env OR inline in the command string).

set -uo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

if [ "${SKIP_GIT_SNAPSHOT:-}" = "1" ] \
   || echo "$COMMAND" | grep -qE '(^|[[:space:]])SKIP_GIT_SNAPSHOT=1([[:space:]]|$)'; then
    exit 0
fi

SEG=$(printf '%s\n' "$COMMAND" | tr -s '&|;' '\n' \
  | grep -E '^[[:space:]]*git[[:space:]]+(rebase|cherry-pick|checkout|switch|reset)([[:space:]]|$)' | head -1)
[ -z "$SEG" ] && exit 0

# Don't snapshot the wrong repo.
printf '%s' "$COMMAND" | grep -qE '(^|[[:space:]&|;])cd[[:space:]]' && exit 0

OP=$(echo "$SEG" | sed -E 's/^[[:space:]]*git[[:space:]]+([a-z-]+).*/\1/')

# `git reset` is only risky with --hard (--soft/--mixed/unstage don't touch the tree).
if [ "$OP" = "reset" ] && ! echo "$SEG" | grep -qE '(^|[[:space:]])--hard([[:space:]]|$)'; then
    exit 0
fi

DIRTY=""
[ -n "$(git status --porcelain 2>/dev/null)" ] && DIRTY=1

# Clean checkout/switch is reflog-safe → nothing to snapshot.
case "$OP" in
  checkout|switch) [ -z "$DIRTY" ] && exit 0 ;;
esac

TS=$(date +%Y%m%d-%H%M%S 2>/dev/null || echo now)
HEAD_FULL=$(git rev-parse HEAD 2>/dev/null || echo "")
HEAD_SHORT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git branch --show-current 2>/dev/null); [ -z "$BRANCH" ] && BRANCH="(detached)"
SEG_TRIM=$(echo "$SEG" | sed 's/^[[:space:]]*//')

WT_LINE=""
if [ -n "$DIRTY" ]; then
    STASH=$(git stash create "pre-${OP} snapshot ${TS}" 2>/dev/null || echo "")
    if [ -n "$STASH" ]; then
        git update-ref "refs/snapshots/${TS}-${OP}" "$STASH" 2>/dev/null || true
        WT_LINE="   working tree saved → recover: git stash apply ${STASH}"
    fi
fi

{
    echo ""
    echo "📸 [snapshot-before-rewrite] about to run: ${SEG_TRIM}"
    echo "   pre-op HEAD: ${HEAD_SHORT} on ${BRANCH} — recover: git reset --hard ${HEAD_FULL}"
    [ -n "$WT_LINE" ] && echo "$WT_LINE"
    echo "   list:  git for-each-ref refs/snapshots/"
    echo "   clear: git for-each-ref --format='delete %(refname)' refs/snapshots/ | git update-ref --stdin"
    echo "   (snapshot only — your command was NOT blocked)"
    echo ""
} >&2
exit 0
