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

---

## 2026-08-10 21:14 ET — UNSPECIFIED_SITUATION (recurrence)
**Routine:** pre-market (run date per `date +%Y-%m-%d` = 2026-08-11;
UTC timestamp 2026-08-11T01:14Z)
**Symbol (if applicable):** n/a
**What happened:** Identical failure to the `2026-08-10 21:00 ET`
UNSPECIFIED_SITUATION above, which remains **OPEN**.
`scripts/screener.py` exited 1 on its first Alpaca call:

```
RuntimeError: alpaca.sh account failed: curl: (22) The requested URL
returned error: 403
  screener.py:419 main() -> :189 account_equity() -> :96 run_alpaca()
```

Proxy status confirms org-policy CONNECT denial, freshly recorded for
this run — both the data host and the alert host:

```
2026-08-11T01:14:05Z connect_rejected paper-api.alpaca.markets:443
2026-08-11T01:14:22Z connect_rejected api.telegram.org:443
  "detail": "gateway answered 403 to CONNECT (policy denial or
             upstream failure)"
```

Env vars: all four present and set. Halt check: exit 0.
`memory/HALT.md` absent. Zero screening performed — no regime value, no
universe, no candidates, no rejection counts, so no dated section was
written to `memory/CANDIDATES.md` this run. Nothing re-derived by hand.

**This run answers the open question from commit `df0b228`.** That
commit added `sandbox.network.allowedDomains` for the three hosts to
`.claude/settings.json` and stated: "If the block is an org-managed
policy with allowManagedDomainsOnly set, this will have no effect and
the domains must be allowed on the routine environment instead.
Re-running qms01-pre-market distinguishes the two." It re-ran. The
repository-level allowlist had **no effect** — the 403s are unchanged.
So the block is **not** the Claude Code sandbox prompt-allowlist; it is
the routine environment's / org's egress network policy. Fixing it in
the repo is not possible. It must be changed on the routine environment
itself.

**Rule that doesn't cover this / was ambiguous:** unchanged from the
entry above — Section 12 lists "data feed gap or suspected bad data" as
a HALT condition, but this is an infrastructure egress block returning
*no* data rather than suspect data, and the routine's own failure path
specifies only log + alert + STOP, not creating `memory/HALT.md`.
Writing a halt on the agent's own reading of Section 12 would be
deciding an uncovered case, so it was again not done. Operator still to
decide whether this class of failure should halt. No orders were
possible either way — this routine never trades, and
`memory/POSITIONS.json` is empty.

**Alert channel still down.** The Step 5 Telegram alert could not be
delivered; `api.telegram.org` returned the same proxy 403. Notification
for this run went out via the routine-run push notification only.

**Action taken:** none (screening abandoned for this run). Required
operator fix, on the **routine environment's network policy** (not the
repo): allow `paper-api.alpaca.markets`, `data.alpaca.markets`, and
`api.telegram.org`. Until then no routine can screen, trade, manage a
position, or raise an alert.

---

## 2026-08-10 21:25 ET — UNSPECIFIED_SITUATION
**Routine:** pre-market (run date per `date +%Y-%m-%d` = 2026-08-11)
**Symbol (if applicable):** unknown — the symbol itself is not recorded
anywhere, which is the substance of this entry
**What happened:** The screener completed successfully (exit 0, egress
now working — see the recovery note below). Its own rejection counts do
not fully account for the universe. One symbol was dropped with no
disqualifying rule recorded:

```
Universe                        5900
Stage A rejections (logged)     3460 + 1551 + 500 + 189      = 5700
Stage A survivors               5900 - 5700                  =  200
Stage B rejections (logged)     198 momentum + 1 contraction  =  199
Final candidates                                                   0
Unaccounted                     200 - 199 - 0                =    1
```

Source is `scripts/screener.py::stage_b_setup_scan` lines 249-258: a
Stage-A survivor with fewer than 127 bars, or a `None` 21/63/126-day
return, hits a bare `continue` and never reaches `rejections`. Stage A
logs the same condition as `insufficient_history` (line 219); Stage B
does not log it at all.

**Rule that doesn't cover this / was ambiguous:** Section 11 requires
"**Per rejection** (`memory/CANDIDATES.md`): symbol, first disqualifying
rule." One symbol was screened out this run without either being
recorded. The cause is almost certainly benign and already has a named
Stage-A equivalent (insufficient price history), but naming it here
would be the agent deciding what the missing record says, which Section
0.3 forbids. Section 12's "data feed gap or suspected bad data" was
considered and judged not to apply: this is an engine logging omission
on a symbol that was correctly excluded either way, not suspect data
driving a trading decision, and the run's screening output is otherwise
complete and internally consistent. No halt was written.

**Action taken:** none — logged only. No candidate list was affected: the
dropped symbol could not have become a candidate without passing the
momentum and setup tests it never reached. `scripts/screener.py` was not
modified; changing an engine mid-routine is outside this routine's scope
and is an operator decision. Suggested operator fix: give those two
`continue` statements a `rejections.append((sym, "insufficient_history"))`
so Stage B accounts the same way Stage A does.

**Also recorded — egress recovered.** The 2026-08-10 entries above
reported `paper-api.alpaca.markets`, `data.alpaca.markets`, and
`api.telegram.org` blocked at the proxy with HTTP 403, which aborted
every routine. All three reached today with no errors. This is the first
full production screener pass; the two prior aborted runs produced no
screening data, so `memory/CANDIDATES.md` has no 2026-08-10 section and
that gap is expected, not missing data.

---

## 2026-08-10 21:26 ET — OTHER (alerting defect, no trading impact)
**Routine:** pre-market (run date per `date +%Y-%m-%d` = 2026-08-11)
**Symbol (if applicable):** n/a
**What happened:** The Step 5 Telegram alert failed on first attempt with
`curl: (22) ... error: 400`. Unlike the 2026-08-10 entries, this was NOT
the proxy egress block (that was 403 and is now cleared) — the request
reached Telegram and Telegram rejected it.

Cause: `scripts/telegram.sh` posts with `'parse_mode': 'Markdown'`. Under
legacy Markdown, `_` opens an italic span, so any message containing an
odd number of underscores is rejected with 400 "can't parse entities".
The first attempt contained the literal token `UNSPECIFIED` + `_` +
`SITUATION`. Resending the same text with the underscore removed
succeeded (`"ok":true`, message_id 10).

This is a live alerting hazard, not a cosmetic one. The tokens this
system is required to raise alarms about are exactly the ones that
break it:

```
UNSPECIFIED_SITUATION    Section 0.3 / 11
STOP_TOO_WIDE            Section 8.5
RISK-STATE.json, POSITIONS.json, entry_mechanism: ...
```

An alert naming `STOP_TOO_WIDE` — raised at the moment a position is
being force-exited — would fail to deliver. `scripts/telegram.sh` uses
`curl -fsS`, so the failure prints a one-line curl error and returns
non-zero; a routine that does not check the exit status would treat the
alert as sent. Callers were not audited this run.

**Rule that doesn't cover this / was ambiguous:** none — Section 11
requires the events be logged, and they were. Section 12's "any order
rejected for a reason not understood" does not apply (no order; reason
understood). Recording it here because a silent alerting failure defeats
the escalation path every other rule depends on.

**Action taken:** none beyond resending the alert without the underscore,
and this record. `scripts/telegram.sh` was not modified — this routine's
scope is screen, log, commit, and the fix is an operator call. Suggested
operator fix: drop `parse_mode` from the payload entirely (no alert text
in this system relies on Markdown rendering), and have callers check the
wrapper's exit status.

---

## 2026-08-10 21:31 ET — OTHER (duplicate screener section, no trading impact)
**Routine:** pre-market (run date per `date +%Y-%m-%d` = 2026-08-11)
**Symbol (if applicable):** n/a
**What happened:** This pre-market run fired at 01:28 UTC, ~2 minutes
after the 01:26 UTC run committed as `e4caf24 pre-market screener
2026-08-11`. Both are off-schedule relative to the deployed cron
(`0 11 * * 1-5` UTC = 07:00 ET), i.e. manual/immediate triggers, not
scheduled slots — the same off-hours condition `routines/README.md`
already documents.

The screener has no idempotency check: `write_candidates_section`
unconditionally appends. `memory/CANDIDATES.md` therefore now holds
**two `## 2026-08-11 — Pre-market Screener` sections**. Both re-ran
against the same EOD bars (last close 2026-08-10) and are identical on
every field except the Stage B accounting fix landed in `51bc554`
between them:

```
regime ONEQ          PASS (10SMA 101.8475 > 20SMA 101.3142, both rising)
universe             5900
Stage A survivors     200
candidates              0
insufficient_history  189 (first section)  ->  190 (this section)
```

That single-count delta is the previously logged unaccounted symbol
(see 2026-08-10 21:25 ET) now being recorded. Rejections in this section
sum to 5900 = universe, and Stage B sums to 200 = Stage A survivors, so
the accounting is complete for the first time.

**Rule that doesn't cover this / was ambiguous:** Nothing in
`memory/TRADING-STRATEGY.md` covers a routine firing twice for the same
date, and nothing authorises the agent to skip a routine's stated step
on its own assessment — declining to run `scripts/screener.py` would
itself have been the judgement call Section 0.3 forbids, so STEP 3 was
executed as written. Section 12 was considered and does not apply: no
order, no data-feed gap (both runs agree exactly), no rule conflict.

**Action taken:** none beyond this record. The duplicate section was
left in place rather than hand-edited — `memory/CANDIDATES.md` is
engine-written and Section 11 treats it as the daily record; deleting a
run's output to tidy it is not this routine's call. No trading impact:
`routines/market-open.md` reads "today's dated section", both sections
carry zero candidates, and `memory/POSITIONS.json` is empty, so either
resolution yields the same no-entry outcome. Suggested operator fix:
have `scripts/screener.py` replace an existing section for the same date
instead of appending, or refuse to run when one exists.

---

## 2026-08-10 21:33 ET — OTHER (routine push-recovery gap, no trading impact)
**Routine:** pre-market (run date per `date +%Y-%m-%d` = 2026-08-11)
**Symbol (if applicable):** n/a
**What happened:** STEP 6's push was rejected with "a pushed branch tip
is behind its remote counterpart". The container's fresh clone had left
the working tree on a **detached HEAD**, not on `main`, so the commit
landed on no branch. `git status -sb` showed `## HEAD (no branch)`.

The routine's documented recovery — `git pull --rebase origin main, then
push again` — does **not** fix this. It reported "HEAD is up to date"
(the rebase had nothing to do; the commit was already on top of
`origin/main`) and the second push failed identically. Resolved with
`git checkout -B main HEAD`, then push, which fast-forwarded
`51bc554..e4cfaaa`. No force-push was used and no commit was discarded.

**Rule that doesn't cover this / was ambiguous:** none — git plumbing is
deployment mechanics, not a strategy rule, and Section 0.3 is not
engaged. Logged because every routine's persistence depends on STEP 6
and the stated fallback silently fails here.

**Action taken:** none beyond the recovery above and this record. The
routine prompts in `routines/` were not edited — they are the deployed
production text and changing them is an operator call.

**Why this matters more elsewhere:** pre-market only loses a screen that
can be re-run. `market-open` commits `memory/TRADE-LOG.md` and
`memory/POSITIONS.json` after placing real orders, and `daily-summary`
commits `memory/RISK-STATE.json`. If either hits this and treats the
`pull --rebase` fallback as sufficient, the orders still exist at Alpaca
but the position state recording them is lost when the container is
reclaimed — the next run would then see an empty `POSITIONS.json` beside
live broker positions. Suggested operator fix: add
`git rev-parse --abbrev-ref HEAD` (or `git checkout -B main HEAD`) to
the STEP 6 block of every routine, ahead of the commit, and require the
push exit status to be checked.
