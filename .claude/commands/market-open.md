---
description: QMS-01 entry monitor — retrospective ORH breakout check + sizing + entries (local test run)
---

Run the ENTRY MONITOR workflow (Section 8) locally (`.env` for
credentials). Only meaningful after 10:00 ET, once the 09:30-10:00
opening-range bars exist. Full step-by-step logic is in
routines/market-open.md — follow it exactly, with these differences:
skip the env-var-check block (use `.env`), and don't require the
persistence framing (still commit if you want the test run to leave a
trail, but it's optional for a local dry run).

STEP 1 — Halt check: `bash scripts/halt.sh check`. If non-zero, STOP.

STEP 2 — Read today's memory/CANDIDATES.md entry. If missing/not dated
today: log UNSPECIFIED_SITUATION, STOP. Never invent a fallback screen.

STEP 3 — Compute today's portfolio-limit budget from memory/POSITIONS.json
(Section 10: max 5 open, max 2 new/day, max 3% total open risk, max 20%
per position).

STEP 4 — For each ranked candidate, in order, until slots run out: Gap
check -> opening-range/ORH -> retrospective trigger check -> stop-limit
order + 60s fill window -> initial stop -> stop-width validation
(STOP_TOO_WIDE) -> sizing -> liquidity check -> portfolio-limit re-check
-> resting stop-market order -> record in memory/POSITIONS.json and
memory/TRADE-LOG.md. See routines/market-open.md STEP 4 for the exact
sub-steps and formulas — follow them precisely, do not paraphrase the math.

STEP 5 — Print a summary of what happened (entries, rejections, any
exceptions logged).
