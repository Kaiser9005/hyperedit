#!/bin/bash
# verify-push-refspec.sh — PreToolUse Bash hook
# Blocks `git push <remote> *:main`, `*:master`, `HEAD:main`, `:main` refspecs
# unless explicit emergency bypass is provided.
#
# Exit 0 = allow; exit 2 = BLOCK (Claude Code PreToolUse blocking code — stderr shown
# to agent). NOTE: exit 1 is NON-blocking in Claude Code (tool proceeds) — this gate
# previously exit-1'd, silently NOT blocking direct-push-to-main (FOF-1398). The
# server-side branch protection (FOF-1322) was the only real defense until this fix.
#
# Wired by: FOF-1326 — Parallel-session worktree isolation + git push refspec validator
# Codifies: F-PARALLEL-SESSION-DIRECT-PUSH-TO-MAIN-1 mitigation (2026-05-27 FOF-1283 ship
#           landed on main without PR review via direct push from a feature-branch working tree)
# Sibling:  FOF-1322 (server-side branch protection via GitHub API — defense in depth)
#
# Bypass options (emergency P0 only):
# - SKIP_PUSH_REFSPEC=1 git push ...                 (env var, naming parity with SKIP_TEST_EVIDENCE / SKIP_STREAM_QUOTA)
# - Include "PUSH_REFSPEC_OVERRIDE=p0-prod-bloquant" in the most recent commit body
#   (parity with STREAM_QUOTA_OVERRIDE=p0-prod-bloquant pattern from verify-stream-quota.sh)
#
# Discipline source:
# - F-HOOKIFY-IGNORECASE-FALSE-POSITIVE-1: anchored regex split on shell separators
# - F-AGENT-OBSERVATION-FALSE-INFERENCE-1: verify positive signal before halt
# - feedback_never_revert_parallel.md: never block legitimate parallel-session feature pushes

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

# Only enforce on actual `git push` invocation — anchored split prevents substring false-positive
# (e.g. echo "we may need to git push later" must NOT be flagged)
if ! printf '%s\n' "$COMMAND" | tr -s '&|;' '\n' | grep -qE '^[[:space:]]*git[[:space:]]+push([[:space:]]|$)'; then
    exit 0
fi

# Emergency bypass via env var (documented in commit body when used)
if [ "${SKIP_PUSH_REFSPEC:-}" = "1" ]; then
    echo "⚠️  [verify-push-refspec] SKIP_PUSH_REFSPEC=1 — bypass enabled (document why in commit body)" >&2
    exit 0
fi

# Emergency bypass via in-body override flag on most-recent commit
# (cheap check: don't grep entire commit history, just HEAD)
if git log -1 --pretty=%B 2>/dev/null | grep -qE 'PUSH_REFSPEC_OVERRIDE=p0-prod-bloquant'; then
    echo "⚠️  [verify-push-refspec] PUSH_REFSPEC_OVERRIDE=p0-prod-bloquant in commit body — bypass enabled" >&2
    exit 0
fi

# Detect dangerous refspecs targeting protected branches
# Patterns blocked:
#   git push origin HEAD:main
#   git push origin feature:main
#   git push origin :main (delete)
#   git push origin HEAD:master
#   git push origin <anything>:main|master|prod|production
#
# Pattern NOT blocked (legitimate):
#   git push origin feature-branch
#   git push origin HEAD
#   git push origin (no refspec)
#   git push -u origin feature-branch
#   git push origin :feature-branch (delete a feature branch is allowed)

DANGEROUS_REFSPEC=$(printf '%s\n' "$COMMAND" | grep -oE '[[:space:]][^[:space:]]*:(main|master|prod|production)([[:space:]]|$|"|'\'')' | head -1 || true)

if [ -n "$DANGEROUS_REFSPEC" ]; then
    {
        echo ""
        echo "❌ [verify-push-refspec] Direct push to protected branch detected: ${DANGEROUS_REFSPEC}"
        echo ""
        echo "   Refspec '*:main' / '*:master' / 'HEAD:main' bypasses PR review."
        echo "   Use the canonical PR-merge flow instead:"
        echo "     gh pr create --title \"...\" --body \"...\""
        echo "     gh pr merge <num> --squash --delete-branch"
        echo ""
        echo "   Source: F-PARALLEL-SESSION-DIRECT-PUSH-TO-MAIN-1 (2026-05-27 FOF-1283 ship)"
        echo "   Sibling: FOF-1322 (server-side branch protection via GitHub API)"
        echo ""
        echo "   Emergency bypass options (document in commit body):"
        echo "   - SKIP_PUSH_REFSPEC=1 git push ...                       (P0 prod only)"
        echo "   - Include 'PUSH_REFSPEC_OVERRIDE=p0-prod-bloquant' in HEAD commit body"
        echo ""
    } >&2
    exit 2
fi

exit 0
