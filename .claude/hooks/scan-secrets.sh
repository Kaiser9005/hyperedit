#!/bin/bash
# scan-secrets.sh — self-contained pre-commit secret scanner (git-secrets/trufflehog
# replacement, no external binary so it works on a fresh clone with zero install).
#
# BLOCKS `git commit` (exit 2 — Claude Code PreToolUse blocking code; exit 1 is
# NON-blocking, FOF-1398) when the STAGED diff introduces a high-confidence secret.
# Born from the 2026-06-28 BetAgent leak: a Supabase service_role JWT (exp-2076),
# an account-wide sbp_ PAT, and a Railway deploy token sat in PUBLIC git history
# for ~8 months across 38 commits. This hook makes a repeat structurally hard.
#
# Patterns (high-confidence — tuned to avoid placeholder false positives):
#   - Supabase JWT          eyJ...eyJ...role...service_role|anon...   (3-segment JWT)
#   - Supabase PAT          sbp_<40 hex>
#   - Supabase publishable  sb_(publishable|secret)_<...>
#   - Railway/UUID token    8-4-4-4-12 hex UUID assigned to *RAILWAY*TOKEN*
#   - Generic 32+ hex token assigned to *_API_KEY / *_TOKEN / *_SECRET
#   - Plaintext password     *PASSWORD* = "literal" not reading from the environment
#                            (the 2026-06-28 hyperedit leak: LOGIN_PASSWORD="Admin123!")
#
# Allowlisted (never a secret): the .env.example template, this hook's own file,
# and placeholder values (your_/_here/example/<REDACTED…>/etc.).
#
# Bypass (emergency, document why in commit body): SKIP_SECRET_SCAN=1 git commit ...
set -uo pipefail

INPUT=$(cat 2>/dev/null || true)
COMMAND=$(printf '%s' "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

# Only act on a real `git commit` (split on shell separators to dodge quoted substrings).
if ! printf '%s\n' "$COMMAND" | tr -s '&|;' '\n' | grep -qE '^[[:space:]]*git[[:space:]]+commit([[:space:]]|$)'; then
  exit 0
fi

# Bypass — from hook env OR inline command string (FOF-1398 parity).
if [ "${SKIP_SECRET_SCAN:-}" = "1" ] \
   || printf '%s' "$COMMAND" | grep -qE '(^|[[:space:]])SKIP_SECRET_SCAN=1([[:space:]]|$)'; then
  echo "⚠️  [scan-secrets] SKIP_SECRET_SCAN=1 — bypass enabled (document why in commit body)" >&2
  exit 0
fi

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 0

# Added lines in the staged diff only (what this commit would introduce).
DIFF=$(git diff --cached --no-color -U0 2>/dev/null | grep -E '^\+' | grep -vE '^\+\+\+' || true)
[ -z "$DIFF" ] && exit 0

# Drop obvious placeholders so templates/docs never false-positive.
SCAN=$(printf '%s\n' "$DIFF" \
  | grep -viE 'your_|_here|example|placeholder|<REDACTED|<PASTE|xxxx+|changeme|dummy|sample')

HITS=""
add_hit() { HITS="${HITS}\n  - $1"; }

# Supabase 3-segment JWT carrying a service_role / anon role
echo "$SCAN" | grep -qE 'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}' \
  && add_hit "Supabase JWT (eyJ…eyJ…) — use os.environ[\"SUPABASE_SERVICE_KEY\"]"
# Supabase account-wide Personal Access Token
echo "$SCAN" | grep -qE 'sbp_[A-Za-z0-9]{20,}' \
  && add_hit "Supabase PAT (sbp_…) — account-wide, env-only (SUPABASE_ACCESS_TOKEN)"
# New-model publishable/secret keys
echo "$SCAN" | grep -qE 'sb_(publishable|secret)_[A-Za-z0-9_-]{16,}' \
  && add_hit "Supabase sb_ key — env-only"
# Railway/UUID token assigned to a RAILWAY*TOKEN var
echo "$SCAN" | grep -qiE 'RAILWAY[_A-Z]*TOKEN[^A-Za-z0-9]+[\"'"'"']?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
  && add_hit "Railway deploy token (UUID) — set RAILWAY_TOKEN via env/.env"
# Generic long hex/secret assigned to *_API_KEY / *_TOKEN / *_SECRET
echo "$SCAN" | grep -qiE '(API_KEY|_TOKEN|_SECRET)[^A-Za-z0-9]*[:=][^A-Za-z0-9]*[\"'"'"']?[A-Za-z0-9]{32,}' \
  && add_hit "Hardcoded API key / token / secret (32+ chars) — move to env/.env"
# Hardcoded plaintext PASSWORD assigned a string literal (the 2026-06-28 hyperedit
# leak class: LOGIN_PASSWORD = "Admin123!" sat in public history). Only flags lines
# that assign a quoted literal of 6+ chars AND do NOT read from the environment —
# so the env-injected form  PASSWORD = os.environ.get(...)  never trips it.
echo "$SCAN" \
  | grep -iE '[A-Z_]*PASS(WORD|WD)?[A-Z_]*[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{6,}["'"'"']' \
  | grep -viqE 'os\.environ|getenv|process\.env|import\.meta\.env|System\.getenv|config\(' \
  && add_hit "Hardcoded plaintext password (PASSWORD = \"…\") — read via os.environ.get(\"…\")"

if [ -n "$HITS" ]; then
  {
    echo ""
    echo "🔴 [scan-secrets] BLOCKED: the staged diff introduces a likely secret:"
    printf '%b\n' "$HITS"
    echo ""
    echo "   Move it to .env (gitignored) and read via os.environ / \$VAR."
    echo "   Template: .env.example. See .claude/hooks/scan-secrets.sh for patterns."
    echo "   Emergency bypass (document why): SKIP_SECRET_SCAN=1 git commit ..."
    echo ""
  } >&2
  exit 2
fi

exit 0
