#!/usr/bin/env bash
# Notification wrapper. Posts to a Telegram chat via the Bot API.
# Usage: bash scripts/telegram.sh "<message>"
# If credentials are unset, appends to a local fallback file.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
FALLBACK="$ROOT/DAILY-SUMMARY.md"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ $# -gt 0 ]]; then
  msg="$*"
else
  msg="$(cat)"
fi

if [[ -z "${msg// /}" ]]; then
  echo "usage: bash scripts/telegram.sh \"<message>\"" >&2
  exit 1
fi

stamp="$(date '+%Y-%m-%d %H:%M %Z')"

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  printf "\n---\n## %s (fallback — Telegram not configured)\n%s\n" "$stamp" "$msg" >> "$FALLBACK"
  echo "[telegram fallback] appended to DAILY-SUMMARY.md"
  echo "$msg"
  exit 0
fi

# NO parse_mode. Telegram's legacy Markdown treats `_` as an italic
# delimiter, so any message with an odd number of underscores is rejected
# with 400 "can't parse entities" and never delivered. The tokens this
# system exists to raise alarms about are exactly the ones that break it:
# UNSPECIFIED_SITUATION (Section 0.3/11), RISK_OVERRUN (Section 8.6),
# risk_per_share, POSITIONS.json field names. Verified live 2026-08-11.
# No alert text in this system relies on Markdown rendering, so plain
# text is strictly safer. Do not add parse_mode back.
payload="$(python3 -c "
import json, sys
print(json.dumps({'chat_id': sys.argv[1], 'text': sys.argv[2]}))
" "$TELEGRAM_CHAT_ID" "$msg")"

# Capture body and status separately so a delivery failure is loud rather
# than a bare curl exit code a caller might not check.
http_body="$(mktemp)"
trap 'rm -f "$http_body"' EXIT
code="$(curl -sS -o "$http_body" -w '%{http_code}' -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$payload" || echo "000")"

if [[ "$code" != "200" ]]; then
  echo "TELEGRAM DELIVERY FAILED (HTTP $code) — alert was NOT received:" >&2
  cat "$http_body" >&2
  echo >&2
  printf "\n---\n## %s (UNDELIVERED — Telegram HTTP %s)\n%s\n" "$stamp" "$code" "$msg" >> "$FALLBACK"
  echo "[telegram] message written to DAILY-SUMMARY.md instead" >&2
  exit 1
fi

cat "$http_body"
echo
