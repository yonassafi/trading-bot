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

# All HTTP goes through here. Deliberately NOT `curl -f`: -f throws away
# the response BODY on an HTTP error, and Alpaca puts the rejection reason
# (sub-penny price, buy-stop below market, insufficient buying power,
# wash-trade block...) in exactly that body. Section 12 makes "any order
# rejected for a reason you do not understand" a HALT condition, so
# swallowing the reason converts every ordinary 422 into a self-inflicted
# halt. Success -> body on stdout, unchanged, so screener.py and
# position_manager.py keep parsing it as before. Failure -> status line
# AND body on stderr, non-zero exit.
#
# --max-time bounds a hung request. Without it a stalled call can hang a
# routine that may have just placed a live order it is no longer watching.
req() {
  local body status
  body="$(mktemp)"; trap 'rm -f "$body"' RETURN
  status="$(curl -sS --max-time 45 -o "$body" -w '%{http_code}' "$@" || echo 000)"
  if [[ "$status" != "2"* ]]; then
    echo "ALPACA HTTP $status for: ${*: -1}" >&2
    echo "--- response body (the rejection reason) ---" >&2
    cat "$body" >&2
    echo >&2
    return 1
  fi
  cat "$body"
}

cmd="${1:-}"
shift || true

case "$cmd" in
  account)
    req -H "$H_KEY" -H "$H_SEC" "$API/account"
    ;;
  positions)
    req -H "$H_KEY" -H "$H_SEC" "$API/positions"
    ;;
  position)
    sym="${1:?usage: position SYM}"
    req -H "$H_KEY" -H "$H_SEC" "$API/positions/$sym"
    ;;
  quote)
    sym="${1:?usage: quote SYM}"
    req -H "$H_KEY" -H "$H_SEC" "$DATA/stocks/$sym/quotes/latest"
    ;;
  orders)
    status="${1:-open}"
    req -H "$H_KEY" -H "$H_SEC" "$API/orders?status=$status"
    ;;
  assets)
    # Full tradable US-equity asset list, used by scripts/screener.py to
    # build the daily candidate universe (Section 5). Read-only.
    req -H "$H_KEY" -H "$H_SEC" "$API/assets?status=active&asset_class=us_equity&tradable=true"
    ;;
  bars)
    # Raw querystring passthrough so screener.py/position_manager.py can
    # drive multi-symbol batching and page_token pagination themselves.
    # Usage: bars "symbols=AAPL,MSFT&timeframe=1Day&start=...&end=...&limit=10000&feed=sip[&page_token=...]"
    qs="${1:?usage: bars '<querystring>'}"

    # SIP-ONLY (Section 15, operator determination 2026-08-11).
    # feed=sip is MANDATORY and there is deliberately no override.
    #
    # IEX is a small single-digit share of consolidated volume, so its
    # 5-minute high understates ORH and its low overstates the session
    # low. est_risk_share = limit_price - session_low_T is therefore
    # understated, and Section 8.3 divides risk_capital by it — producing
    # an OVERSIZED position. That is a Section 10 risk-limit breach, not
    # a data-quality annoyance, which is why this is enforced in code
    # rather than left to the prompt.
    #
    # This guard is also what keeps market-open non-functional while
    # Section 15 suspends it: its opening-range pull cannot be served.
    # That is intended. Re-enabling live entries requires a real-time SIP
    # subscription AND a spec amendment — not a flag here.
    case "$qs" in
      *feed=sip*) ;;
      *)
        echo "DATA_FEED_UNAVAILABLE: bars request must specify feed=sip." >&2
        echo "Section 15: IEX understates ORH and overstates the session" >&2
        echo "low, which understates risk_per_share and OVERSIZES the" >&2
        echo "position — a Section 10 breach. There is no override." >&2
        echo "Rejected querystring: $qs" >&2
        exit 1
        ;;
    esac

    if ! req -H "$H_KEY" -H "$H_SEC" "$DATA/stocks/bars?$qs"; then
      # A SIP request that cannot be served (commonly: `end` reaches into
      # the free plan's ~15-minute delay window) must fail loudly, never
      # degrade to IEX.
      echo "DATA_FEED_UNAVAILABLE: SIP bars request failed. Do NOT retry" >&2
      echo "this with feed=iex. If 'end' is within ~15 minutes of now," >&2
      echo "move it back; otherwise treat as a Section 12 data-feed gap." >&2
      exit 1
    fi
    ;;
  order)
    require_paper
    body="${1:?usage: order '<json>'}"
    # IDEMPOTENCY (Section 10 protection, not plumbing hygiene).
    # Every order MUST carry a client_order_id. Alpaca rejects a repeat
    # of an id it has already seen, which makes a duplicate structurally
    # impossible rather than merely discouraged by prose. Without it, a
    # retry after an ambiguous timeout silently doubles position size —
    # that is a "max single position 20% of equity" and "max total open
    # risk 3.0%" breach, i.e. a risk-limit violation, not a glitch.
    #
    # Convention (see routines/market-open.md):
    #   qms01-<YYYY-MM-DD>-<SYMBOL>-entry
    #   qms01-<YYYY-MM-DD>-<SYMBOL>-stop
    #   qms01-<YYYY-MM-DD>-<SYMBOL>-partial
    #   qms01-<YYYY-MM-DD>-<SYMBOL>-exit
    # Deterministic from date+symbol+purpose, so a re-run of the same
    # logical order reproduces the same id and is refused by the broker.
    if ! printf '%s' "$body" | grep -q '"client_order_id"'; then
      echo "REFUSING: order body has no client_order_id." >&2
      echo "A retry without one can duplicate the order and breach the" >&2
      echo "Section 10 position/risk limits. Use:" >&2
      echo '  qms01-<YYYY-MM-DD>-<SYMBOL>-<entry|stop|partial|exit>' >&2
      exit 1
    fi
    req -H "$H_KEY" -H "$H_SEC" -H "Content-Type: application/json" \
      -X POST -d "$body" "$API/orders"
    ;;
  cancel)
    require_paper
    oid="${1:?usage: cancel ORDER_ID}"
    req -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/orders/$oid"
    ;;
  cancel-all)
    require_paper
    req -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/orders"
    ;;
  close)
    require_paper
    sym="${1:?usage: close SYM}"
    req -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/positions/$sym"
    ;;
  close-all)
    require_paper
    req -H "$H_KEY" -H "$H_SEC" -X DELETE "$API/positions"
    ;;
  *)
    echo "Usage: bash scripts/alpaca.sh <account|positions|position|quote|orders|assets|bars|order|cancel|cancel-all|close|close-all> [args]" >&2
    exit 1
    ;;
esac
echo
