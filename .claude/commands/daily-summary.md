---
description: QMS-01 end-of-day — reconcile fills, run Section 9 position management, drawdown/halt check, EOD summary (local test run)
---

Run the END-OF-DAY workflow locally (`.env` for credentials). Full
step-by-step logic is in routines/daily-summary.md — follow it exactly:
halt check -> pull live state -> reconcile fills against
memory/POSITIONS.json -> run `python3 scripts/position_manager.py` ->
execute its action list via scripts/alpaca.sh -> peak-equity/drawdown
check against memory/RISK-STATE.json (25% halt threshold) -> append EOD
snapshot to memory/TRADE-LOG.md -> notify.

Do not paraphrase the reconciliation or drawdown math — follow
routines/daily-summary.md STEPs 3 and 6 precisely.
