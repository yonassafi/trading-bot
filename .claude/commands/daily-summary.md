---
description: Daily EOD summary — compute day/phase P&L, snapshot to trade log, notify
---

Run the daily summary workflow locally. Uses the local .env for credentials.
Resolve today's date via: DATE=$(date +%Y-%m-%d).

STEP 1 — Read memory for continuity:
- tail of memory/TRADE-LOG.md (find most recent EOD snapshot -> yesterday's
  equity, needed for Day P&L)
- Count TRADE-LOG entries dated today (for "Trades today")
- Count trades Mon-today this week (for 3/week cap)

STEP 2 — Pull final state of the day:
  bash scripts/alpaca.sh account
  bash scripts/alpaca.sh positions
  bash scripts/alpaca.sh orders

STEP 3 — Compute metrics:
- Day P&L ($ and %) = today_equity - yesterday_equity
- Phase cumulative P&L ($ and %) = today_equity - starting_equity
- Trades today (list or "none")
- Trades this week (running total)

STEP 4 — Append EOD snapshot to memory/TRADE-LOG.md:
### MMM DD — EOD Snapshot (Day N, Weekday)
**Portfolio:** $X | **Cash:** $X (X%) | **Day P&L:** ±$X (±X%) | **Phase P&L:** ±$X (±X%)
| Ticker | Shares | Entry | Close | Day Chg | Unrealized P&L | Stop |
**Notes:** one-paragraph plain-english summary.

STEP 5 — Send ONE Telegram message (always, even on no-trade days). <= 15 lines:
  bash scripts/telegram.sh "EOD MMM DD
  Portfolio: \$X (±X% day, ±X% phase)
  Cash: \$X
  Trades today: <list or none>
  Open positions:
    SYM ±X.X% (stop \$X.XX)
  Tomorrow: <one-line plan>"
