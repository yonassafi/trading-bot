#!/usr/bin/env bash
# Alpaca API wrapper. All trading API calls go through here.
# Usage: bash scripts/alpaca.sh <subcommand> [args...]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${ALPACA_API_KEY:?ALPACA_API_KEY not set in environment}"
: "${ALPACA_SECRET_KEY:?ALPACA_SECRET_KEY not set in environment}"

API="${ALPACA_ENDPOINT:-https://paper-api.alpaca.markets/v2}"
DATA="${ALPACA_DATA_ENDPOINT:-https://data.alpaca.markets/v2}"

H_KEY="APCA-API-KEY-ID: $ALPACA_API_KEY"
H_SEC="APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY"

# QMS-01 Binding Constraint #1: PAPER TRADING ONLY. Any subcommand that can
# place, modify, or cancel an order must refuse to run against anything
# other than Alpaca's paper endpoint. This is enforced here, in code, not
# left to prompt instructions alone.
require_paper() {
  case "$API" in
    *paper-api.alpaca.markets*) ;;
    *)
      echo "REFUSING: ALPACA_ENDPOINT ($API) is not the paper-trading endpoint." >&2
      echo "Binding Constraint #1 (QMS-01 Section 0): paper trading only." >&2
      exit 1
      ;;
  esac
}

cmd="${1:-}"
shift || true

case "$cmd" in
  account)
    curl -fsS -H "$H_KEY" -H "$H_SEC" "$API/account"
    ;;
  positions)
    curl -fsS -H "$H_KEY" -H "$H_SEC" "$API/positions"
    ;;
  position)
    sym="${1:?usage: position SYM}"
    curl -fsS -H "$H_KEY" -H "$H_SEC" "$API/positions/$sym"
    ;;
  quote)
    sym="${1:?usage: quote SYM}"
    curl -fsS -H "$H_KEY" -H "$H_SEC" "$DATA/stocks/$sym/quotes/latest"
    ;;
  orders)
    status="${1:-open}"
    curl -fsS -H "$H_KEY" -H "$H_SEC" "$API/orders?status=$status"
    ;;
  assets)
    # Full tradable US-equity asset list, used by scripts/screener.py to
    # build the daily candidate universe (Section 5). Read-only.
    curl -fsS -H "$H_KEY" -H "$H_SEC" "$API/assets?status=active&asset_class=us_equity&tradable=true"
    ;;
  bars)
    # Raw querystring passthrough so screener.py/position_manager.py can
    # drive multi-symbol batching and page_token pagination themselves.
    # Usage: bars "symbols=AAPL,MSFT&timeframe=1Day&start=...&end=...&limit=10000[&page_token=...][&feed=...]"
    qs="${1:?usage: bars '<querystring>'}"
    curl -fsS -H "$H_KEY" -H "$H_SEC" "$DATA/stocks/bars?$qs"
    ;;
  order)
    require_paper
    body="${1:?usage: order '<json>'}"
    curl -fsS -H "$H_KEY" -H "$H_SEC" -H "Content-Type: application/json" \
      -X POST -d "$body" "$API/orders"
    ;;
  cancel)
    require_paper
    oid="${1:?usage: cancel ORDER_ID}"
    curl -fsS -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/orders/$oid"
    ;;
  cancel-all)
    require_paper
    curl -fsS -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/orders"
    ;;
  close)
    require_paper
    sym="${1:?usage: close SYM}"
    curl -fsS -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/positions/$sym"
    ;;
  close-all)
    require_paper
    curl -fsS -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/positions"
    ;;
  *)
    echo "Usage: bash scripts/alpaca.sh <account|positions|position|quote|orders|assets|bars|order|cancel|cancel-all|close|close-all> [args]" >&2
    exit 1
    ;;
esac
echo
