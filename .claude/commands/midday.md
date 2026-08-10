---
description: QMS-01 midday heartbeat — checks every open position has a resting stop (no trading action)
---

Heartbeat only. QMS-01's Section 9 position management is end-of-day
only (see routines/daily-summary.md) — this command takes NO trading
action, ever.

STEP 1 — Halt check: `bash scripts/halt.sh check`. If non-zero, print the
reason and STOP.

STEP 2 — Read memory/POSITIONS.json "open" and `bash scripts/alpaca.sh orders`.

STEP 3 — For each open position, confirm a resting stop-type order
exists for that symbol. If any is missing, log UNSPECIFIED_SITUATION to
memory/EXCEPTIONS-LOG.md naming the symbol — do not place a replacement
stop from here.

STEP 4 — Print the result. No other action.
