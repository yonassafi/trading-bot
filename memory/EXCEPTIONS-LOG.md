# Exceptions Log — QMS-01 Breakout v1.1-paper

Per `memory/TRADING-STRATEGY.md` Section 11: "the most valuable records
the system produces." Every `UNSPECIFIED_SITUATION`, `STOP_TOO_WIDE`,
HALT event, and any instance of uncertainty about applying a rule is
logged here — never silently resolved by the agent's own judgement.

QMS-01 has no research step (unlike the prior strategy this repo used to
run) — this file replaces what was `RESEARCH-LOG.md`.

Format each entry:

## YYYY-MM-DD HH:MM ET — <UNSPECIFIED_SITUATION | STOP_TOO_WIDE | HALT | other>
**Routine:** pre-market | market-open | daily-summary | weekly-review
**Symbol (if applicable):**
**What happened:**
**Rule that doesn't cover this / was ambiguous:**
**Action taken:** (should almost always be "none" for UNSPECIFIED_SITUATION,
per Section 0.3 — absence of a rule means do nothing)

---

## 2026-08-10 21:00 ET — UNSPECIFIED_SITUATION
**Routine:** pre-market (run date per `date +%Y-%m-%d` = 2026-08-11)
**Symbol (if applicable):** n/a
**What happened:** `scripts/screener.py` exited 1 before any screening
work. It failed on its first Alpaca call, `account_equity()`:

```
RuntimeError: alpaca.sh account failed: curl: (22) The requested URL
returned error: 403
  screener.py:419 main() -> :189 account_equity() -> :96 run_alpaca()
```

Cause is network egress, not Alpaca and not the account. The cloud
routine's agent proxy refused the connection outright:

```
curl -sS "$HTTPS_PROXY/__agentproxy/status"
  "kind": "connect_rejected",
  "detail": "gateway answered 403 to CONNECT (policy denial or upstream
             failure)",
  "host": "paper-api.alpaca.markets:443"   (x2, 00:59:45Z / 00:59:51Z)
```

`paper-api.alpaca.markets` is not on this environment's allowed-egress
list. Per `/root/.ccr/README.md`, a 403/407 from the proxy is an org
policy denial: "Do not retry or route around it — report the blocked
host." All four required env vars were present and set; the halt check
passed (exit 0); `memory/HALT.md` does not exist.

Zero screening was performed. No regime value, no universe, no candidate
list, no rejection counts — so no dated section was written to
`memory/CANDIDATES.md` this run. Nothing was re-derived by hand: the
routine forbids working around a script failure manually, and Section
0.3 forbids inventing the results.

**Rule that doesn't cover this / was ambiguous:** Section 12 lists "data
feed gap or suspected bad data" as a HALT condition, and the pre-market
routine text points at Section 12 for a screener failure. But this is an
infrastructure egress block that returned *no* data at all, not a feed
gap that returned suspect data — and Section 12's remedy (`memory/HALT.md`,
clearable only by a human via `/resume`) would block every subsequent
routine. The routine's own failure path specifies only: log
UNSPECIFIED_SITUATION, send one Telegram alert, STOP. It does not
instruct creating a halt. Writing `memory/HALT.md` on the agent's own
reading of Section 12 would be the agent deciding an uncovered case, so
it was not done. Flagged here for the operator per Section 11 ("any
rule-application uncertainty"). No orders were possible either way —
this routine never trades, and `memory/POSITIONS.json` is empty.

**The alert channel is down too.** The Step 5 Telegram alert for this
exception could not be delivered — `scripts/telegram.sh` failed with the
same proxy 403:

```
2026-08-11T00:59:45Z connect_rejected paper-api.alpaca.markets:443
2026-08-11T00:59:51Z connect_rejected paper-api.alpaca.markets:443
2026-08-11T01:00:56Z connect_rejected api.telegram.org:443
```

So `api.telegram.org` is blocked by the same egress policy. Every
routine's only notification path is therefore silent: a future
`market-open` or `daily-summary` failure — including one affecting a
real open position — would leave no Telegram trace. This log entry and
the operator's routine-run notification are the only surviving channels.

**Action taken:** none (screening abandoned for this run). Operator must
allow `paper-api.alpaca.markets`, `data.alpaca.markets`, and
`api.telegram.org` in the routine environment's network policy. Until
then no routine can trade, manage a position, or raise an alert.
Operator to decide whether this class of failure should halt.

---

## 2026-08-10 21:00 ET — other (schedule misconfiguration)
**Routine:** pre-market
**Symbol (if applicable):** n/a
**What happened:** This "pre-market" run fired at **21:00 ET Monday
2026-08-10** — about 10 hours before the 07:00 ET slot that
`routines/README.md` specifies (`0 7 * * 1-5`, America/New_York). The
firing time matches 01:00 UTC, so the cloud routine's cron appears to be
set in UTC rather than ET.

Consequence beyond the wrong hour: `DATE=$(date +%Y-%m-%d)` resolves
from UTC and yields **2026-08-11** while it is still 2026-08-10 in ET.
The screener stamped its output `QMS-01 screener — 2026-08-11` before
failing. A run at this hour also precedes the session whose EOD bars the
screen is meant to consume.

**Rule that doesn't cover this / was ambiguous:** Cron timing is an
operator-chosen deployment setting, not a strategy rule — Section 14
parameters are untouched by it. Nothing in `memory/TRADING-STRATEGY.md`
covers the agent correcting its own schedule, and Section 0.3 forbids
filling that gap by judgement.

**Action taken:** none — reported only. Operator should set the routine
timezone to America/New_York, or convert each cron row in
`routines/README.md` to UTC. The same offset would affect `market-open`
(10:05 ET) and `daily-summary` (16:10 ET), which do place and manage
orders.

**RESOLUTION (2026-08-11, operator + agent, local session):** This entry
is a **false alarm** and is closed. The 21:00 ET firing was a *manual*
test trigger of `qms01-pre-market` issued from a local session, not a
scheduled run. The operator's local clock is Europe/Vilnius, where the
trigger was sent at ~04:00; that is 21:00 ET the previous day.

The deployed cron is correct. Cloud routine crons are UTC-only (no
timezone field exists), and `qms01-pre-market` is set to `0 11 * * 1-5`
= 07:00 ET. `routines/README.md` was stale — it still listed the table
in ET, which is what this run compared itself against. The README has
now been corrected to show both columns.

The `DATE` observation was real but does not apply to scheduled runs:
every scheduled slot falls between 11:00 and 21:00 UTC, so the UTC
calendar date always equals the ET date. Only off-hours manual runs
trip it. No strategy rule was involved and no parameter was changed.

The egress-block entry above this one remains **OPEN** — that is the
real blocker.

---

## 2026-08-11 — defect found during post-run audit (no trading impact)
**Routine:** daily-summary (prompt defect, never executed)
**Symbol (if applicable):** n/a
**What happened:** `routines/daily-summary.md` STEP 7 defined Phase P&L
as `today_equity - starting_equity (10000, or memory/RISK-STATE.json's
starting_equity)`. The hardcoded `10000` is wrong by 10x: the Alpaca
paper account is funded at **100000**, and `memory/RISK-STATE.json`
correctly records `starting_equity: 100000.0`. Had `daily-summary` ever
run and trusted the parenthetical rather than the file, every Phase P&L
figure in `memory/TRADE-LOG.md` and every Telegram EOD summary would
have overstated performance by $90,000.

**Rule that doesn't cover this / was ambiguous:** none — this was a
prompt authoring error, not a strategy question. Section 14 parameters
are untouched; starting equity is account state, not a strategy
parameter.

**Action taken:** Fixed. The line now reads `starting_equity` from
`memory/RISK-STATE.json` as the sole source and explicitly forbids
assuming a value. The deployed cloud routine prompt was updated to
match. Caught before `daily-summary` ever executed, so no logged figure
is affected and no correction to historical data is needed.
