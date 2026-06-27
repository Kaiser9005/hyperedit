#!/bin/bash
# Insights-gap-audit Tier-1 #1 — PreToolUse Bash hook
# Blocks `git commit` when HEAD is on a protected branch (main/master/production/prod).
#
# Rationale: verify-push-refspec.sh blocks the PUSH to main, but nothing blocks a
# LOCAL commit while HEAD is on main. The /insights report (2026-05-31) flagged
# "commits landing on main" as the #1 recurring Claude-side error. This closes the
# gap at commit time — the earliest possible point — so commits never accumulate on
# the wrong branch and then need untangling.
#
# Defense-in-depth layers:
#   1. block-commit-on-main.sh  (this) — catches it at commit time
#   2. verify-push-refspec.sh         — catches a dangerous push refspec
#   3. GitHub branch protection       — server-side last line (FOF-1322)
#
# Wiring: .claude/settings.json PreToolUse Bash matcher (sibling to verify-test-evidence.sh).
# Reads tool_input JSON from stdin (Claude Code hook protocol).
# Exit 0 = allow; exit 2 = BLOCK (Claude Code PreToolUse blocking code — stderr shown to agent).
#
# Emergency bypass: SKIP_COMMIT_MAIN_CHECK=1 git commit ...   (document why in the commit body)
#
# Discipline source: F-HOOKIFY-IGNORECASE-FALSE-POSITIVE-1 — split command on shell
# separators BEFORE matching to avoid quoted-substring false positives like
# `echo "remember to git commit"`.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

# Only enforce on an actual `git commit` invocation (not a quoted substring).
# Split on shell separators (&, |, ;); a segment must START with `git commit`.
if ! printf '%s\n' "$COMMAND" | tr -s '&|;' '\n' \
     | grep -qE '^[[:space:]]*git[[:space:]]+commit([[:space:]]|$)'; then
    exit 0
fi

# Emergency bypass
if [ "${SKIP_COMMIT_MAIN_CHECK:-}" = "1" ]; then
    echo "⚠️  [block-commit-on-main] SKIP_COMMIT_MAIN_CHECK=1 — bypass enabled" >&2
    exit 0
fi

# Current branch. Fail-open if git can't tell us (detached HEAD → empty → not
# protected → allow; matches the repo's other fail-open hooks).
BRANCH=$(git branch --show-current 2>/dev/null || echo "")

case "$BRANCH" in
  main|master|production|prod)
    {
        echo ""
        echo "❌ [block-commit-on-main] Refusing to commit directly on protected branch '${BRANCH}'."
        echo "   Create a feature branch first:"
        echo "       git switch -c <type>/<scope>-<short-desc>"
        echo "   then re-run the commit. Open a PR:"
        echo "       gh pr create ... && gh pr merge <N> --auto --squash --delete-branch"
        echo "   Bypass (emergency only — document why in the commit body):"
        echo "       SKIP_COMMIT_MAIN_CHECK=1 git commit ..."
        echo ""
    } >&2
    exit 2
    ;;
  *)
    exit 0
    ;;
esac
