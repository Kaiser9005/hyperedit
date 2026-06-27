#!/usr/bin/env bash
# guard-supabase-mcp.sh — single-prong Supabase-MCP DDL guard for a ClipWise session.
# Adapted from ~/njangi-platform/.claude/hooks/guard-supabase-mcp.sh (NJANGI two-prong),
# reduced to ONE prong because ClipWise has NO own scoped Supabase project.
#
# CONTEXT (FOF-1420): ClipWise deliberately uses the FOFAL DB (he_* tables) through an
# anon key + RLS — service_role was dropped client-side (PR #… merged 2026-06-12). The
# durable own-Supabase-project migration is P3 (NOT this card). Meanwhile, the global
# Supabase MCP (~/.claude.json) is hard-pinned to FOFAL PROD (--project-ref=bbkdzfxdbeclyxoaaadb),
# and a ClipWise session inherits it. A ClipWise session calling mcp__supabase__apply_migration
# or execute_sql would run DDL/arbitrary SQL against FOFAL's live tables with FULL PAT privileges
# — bypassing the anon+RLS read-only contract entirely (F-MCP-LOCAL-NAME-POINTS-TO-PROD-1 class,
# and a direct FOF-1420 contract violation). The Bash-level guard cannot see MCP tool calls, so
# this PreToolUse hook BLOCKS the mutating MCP ops OUTRIGHT (fail-CLOSED).
#
# ClipWise has no project-pinned MCP of its own → no Prong-2. If a scoped own-project MCP is added
# later (P3), extend this guard with a Prong-2 ref-verification block mirroring the crypto/NJANGI
# variants.
#
# Read-only MCP calls (list_tables / get_project_url / list_migrations) are NEVER blocked — they
# are how you inspect the schema. A read-only SELECT via execute_sql is also blocked here (the
# guard can't parse SQL intent safely), but any genuine read need can use list_tables/list_migrations
# or the anon Supabase client in app code; bypass for a confirmed read-only need: CONFIRM_SUPABASE_CLIPWISE_RO=1.
set -euo pipefail

FOFAL_REF="bbkdzfxdbeclyxoaaadb"

input="$(cat 2>/dev/null || true)"
tool="$(printf '%s' "$input" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("tool_name",""))
except Exception: print("")' 2>/dev/null || true)"

case "$tool" in
  # FOFAL-bound generic MCP: block any DDL / arbitrary SQL outright (fail-CLOSED).
  mcp__supabase__apply_migration|mcp__supabase__execute_sql)
    [ "${CONFIRM_SUPABASE_CLIPWISE_RO:-}" = "1" ] && exit 0
    echo "🔴 [guard-supabase-mcp] BLOCKED: $tool — ClipWise must stay READ-ONLY/anon on the FOFAL DB." >&2
    echo "   ClipWise uses the FOFAL DB ($FOFAL_REF) via an anon key + RLS (FOF-1420 contract)." >&2
    echo "   The global Supabase MCP wields the FULL account PAT — running this would mutate FOFAL's" >&2
    echo "   live tables, bypassing anon+RLS entirely. P5 / FOF-1420 violation." >&2
    echo "   Allowed instead: read-only MCP (list_tables / get_project_url / list_migrations) or the" >&2
    echo "   anon Supabase client in app code. Schema changes belong in a FOFAL migration PR, not here." >&2
    echo "   The durable fix is a ClipWise-own Supabase project (P3 migration)." >&2
    echo "   Bypass ONLY for a confirmed read-only SELECT need: CONFIRM_SUPABASE_CLIPWISE_RO=1" >&2
    exit 2
    ;;
  *) exit 0 ;;
esac
