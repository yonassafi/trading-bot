---
description: QMS-01 pre-market screener — regime check, universe filter, setup scan (local test run)
---

Run the pre-market SCREENER workflow locally (`.env` for credentials).
No trading — this only screens and logs. Resolve today's date via:
DATE=$(date +%Y-%m-%d).

STEP 1 — Halt check:
  bash scripts/halt.sh check
If non-zero: print the halt reason and STOP.

STEP 2 — Read memory/TRADING-STRATEGY.md, memory/POSITIONS.json, tail of
memory/CANDIDATES.md.

STEP 3 — Run the screener:
  python3 scripts/screener.py
Writes a dated section to memory/CANDIDATES.md, prints a JSON summary.
If it errors: log UNSPECIFIED_SITUATION to memory/EXCEPTIONS-LOG.md with
the error, STOP. Do not work around a script failure.

STEP 4 — No trading.

STEP 5 — Print a short summary: regime state, universe/candidate counts,
top few candidates.
