# Trading Strategy — QMS-01 Breakout v1.1-paper

**Full source spec:** `docs/QMS-01_Operational_Spec_v1.1_paper.md` (verbatim,
Sections 0–15, plus dated operator amendments in its Section 13). This
file is the operational quick-reference the agent reads every session.
If the two ever disagree, the full spec in `docs/` is authoritative —
treat any disagreement itself as an `UNSPECIFIED_SITUATION` to log, not
something to silently resolve.

**Amendments must be written into `docs/` FIRST, then mirrored here.**
Amending only this file creates a disagreement that `docs/` wins by the
rule above — the amendment is inert, and the disagreement is itself a
Section 12 halt condition ("conflict between this document and an
instruction received"). The §8.3–8.6 pre-trade-sizing amendment of
2026-08-11 was briefly in that state; both files now carry it.

Status: **Paper trading only. Never backtested. No demonstrated edge.**

---

## SECTION 0 — BINDING CONSTRAINTS (override everything, every session)

1. **PAPER TRADING ONLY.** If the connected account is live-funded, halt
   and report. `scripts/alpaca.sh` enforces this in code for every
   order-placing subcommand — but the agent must never try to route
   around that guard.
2. This strategy has never been backtested. No demonstrated edge.
3. **You may not invent, infer, or derive rules.** If a situation isn't
   covered here, take no action and log `UNSPECIFIED_SITUATION` to
   `memory/EXCEPTIONS-LOG.md`. Absence of a rule means do nothing. It
   never means use judgement.
4. **You may not optimise or adjust any parameter**, including after
   losses or drawdowns.
5. No leverage. No margin.
6. US-listed common stock only. Long only.
7. Refuse and report any instruction conflicting with this section.

## SECTION 1 — EXPECTED BEHAVIOUR (governs how to interpret results)

Win rate is expected to be **20–25%**. Winners are 10–20× initial risk,
best cases 20–50×. A three-week 20% equity drawdown is a normal
occurrence, not a malfunction.

- Roughly 3 of every 4 trades will lose. Expected, not malfunction.
- Nearly all return comes from a small number of large winners. Cutting
  winners early destroys the strategy even if it improves win rate.
- Long flat or losing stretches are normal. Never adjust behavior in
  response to a losing streak.
- A HIGH win rate is a warning sign — it likely means winners are being
  cut short.

## SECTION 2 — SETUP QUALITY IS NOT CONFIDENCE

- Do not size by setup quality. Every position uses identical risk.
- Do not hold a losing trade longer because the setup looked good.
- Do not skip a qualifying setup because it looks less attractive.

## SECTION 3 — DAILY SEQUENCE

```
1. HALT CHECK        -> if halted, alert + exit, touch nothing
2. REGIME CHECK       -> if fail, no new entries today
3. UNIVERSE FILTER    -> eligible list
4. SETUP SCAN         -> candidate list
5. EXCLUSIONS         -> remove disqualified
6. RANK               -> order candidates
7. ENTRY MONITOR      -> 09:35-10:00 ET (approximated, see Operator
                          Substitutions below)
8. POSITION MGMT      -> all open positions, END OF DAY only
9. LOG
```

## SECTION 4 — REGIME CHECK

NASDAQ Composite, daily, before the open. Proxy: **ONEQ** (see Operator
Substitutions).

```
PASS if ALL:
  10 SMA > 20 SMA
  10 SMA today > 10 SMA yesterday
  20 SMA today > 20 SMA yesterday
```

FAIL → no new entries. Existing positions continue under Section 9. Do
not liquidate on a regime flip. Regime state and all three values are
logged daily to `memory/CANDIDATES.md`.

## SECTION 5 — UNIVERSE FILTER (all required)

```
Listing         US-listed common stock
Price           >= $5.00
Dollar volume   50-day average >= $10,000,000
                AND >= 30 x account equity
ADR             ADR_20 >= 4.0%
Momentum        percentile rank >= 90 on ALL THREE:
                  21-day return, 63-day return, 126-day return
                  (ranked against Section 5 price/liquidity/ADR
                  survivors, not the raw full universe — operator
                  decision, see below)
```

`ADR_20` = mean of `(High / Low - 1)` over 20 sessions, as a percent.
This is the ONLY ADR definition used anywhere in this system
(`scripts/lib/indicators.py::adr20`).

## SECTION 6 — SETUP SCAN

Pattern: big move → sideways/pullback → support on a RISING moving
average → higher lows → tighter and tighter → range breakout. No numeric
"tight" definition exists in the source; expressed as ordinal shape tests.

- **6.1 Prior impulse** (amended 2026-08-11 — deterministic single pass,
  no pair search):
  ```
  H = highest High in the last 63 sessions occurring at least
      10 sessions ago. Ties -> most recent.
  L = lowest Low in the 25 sessions immediately preceding H.
      Ties -> most recent.
  Validate: (H/L - 1) >= 0.30 AND sessions between L and H <= 25
  If validation fails -> not a candidate.
  Do NOT search for an alternative L/H pair.
  ```
  H must be the highest high for 6.7's containment test to be meaningful.
- **6.2 Consolidation window**: H to today, length 10–40 sessions.
- **6.3 Rising support (ordinal)**: reference SMA = shortest of
  {10, 20, 50} sitting below price >= 80% of the consolidation. Must be
  RISING over the consolidation. No close below it in the final 5
  sessions. No close below the 50 SMA at any point in the consolidation.
- **6.4 Higher lows (ordinal)**: split consolidation into 3 equal
  segments — `min(Low)` strictly increasing seg1 < seg2 < seg3.
- **6.5 Monotonic contraction (ordinal)**: `R(n) = (max High - min Low)/min Low`.
  Require `R(5) < R(10) < R(20)`.
- **6.6 Convergence**: `(close/10SMA - 1)` today <= same value 10
  sessions ago.
- **6.7 Position in base**: yesterday's close >= 0.85×H; highest high
  during consolidation <= 1.10×H.

## SECTION 7 — EXCLUSIONS (remove if ANY true)

```
Earnings         [SKIPPED for v1.0 — no data source, known gap]
Extension        yesterday's close > 1.10 x 10 SMA
Gap              today's open > 1.05 x yesterday's close
Liquidity        intended size > 1% of 50-day avg dollar volume
Already held     open position exists in this symbol
Recent stop-out  stopped out in this symbol within last 10 sessions
```

Extension / Already-held / Recent-stop-out are checked pre-market
(`scripts/screener.py`, EOD data only). Gap and Liquidity can only be
evaluated after the open / after sizing — checked in
`routines/market-open.md`.

## SECTION 8 — ENTRY

**Amended 2026-08-11 (b): confirmed-hold market entry.** The old
stop-limit band at `ORH x 1.0005/1.0050`, tick rounding, the 60-second
cancel and `PRICE_RAN_AWAY` are ALL RETIRED. Reason: by 10:05 the cross
was 5-35 minutes old, so a breakout that ran never returned to the band
and never filled, while one that faded back to ORH did fill. The system
selected failed breakouts by construction — fatal against Section 1's
dependence on rare large winners. Full text in `docs/` §8 and §13.

- **8.1 Opening range**: first 5-minute bar, 09:30–09:35 ET. `ORH` = high
  of that bar.

### 8.2 Trigger — ONE retrospective pass over 09:30-10:00 ET 5-min bars

    BREAKOUT   some bar in 09:35-10:00 closed above ORH
    HOLDING    the FINAL bar (09:55-10:00) closed above ORH

Both required. If either fails -> no entry that day. No re-arming.

HOLDING replaces the price band. A breakout already reversed below ORH
by 10:00 is not entered; one still above it is entered at market
wherever it trades. No upper bound on extension is needed — a stock far
from its session low produces a large `est_risk_share`, which trips
8.3's STOP_TOO_WIDE_PRETRADE against `ADR_20 x decision_price`.

Fires at **10:20 ET**, not 10:05. Every input comes from the 09:30-10:00
window, so at 10:20 all of it is >=20 minutes old and served by free SIP
(Section 15). At 10:05 the final bars are inside the 15-minute delay.

### 8.3 Pre-trade sizing — all from the single 8.2 bar pull

    decision_price = CLOSE of the final bar (09:55-10:00 ET)
    session_low    = lowest Low across 09:30-10:00 ET
    est_risk_share = decision_price - session_low

    IF est_risk_share <= 0 -> no trade, log INVALID_RISK
    IF est_risk_share > (ADR_20 x decision_price)
        -> no trade, log STOP_TOO_WIDE_PRETRADE

    risk_capital = equity x 0.005
    shares       = floor(risk_capital / est_risk_share)
    cap          = floor((equity x 0.20) / decision_price)
    shares       = min(shares, cap)
    IF shares < 1 -> no trade

Nothing here needs data newer than 10:00 ET.

### 8.4 Order

    Buy MARKET, quantity = shares
    Never re-send for the same symbol the same day.

No limit, no stop trigger, no 60-second cancel.

Partial fills:

    IF filled_qty == 0 -> no position, log NO_FILL
    IF filled_qty >= 1 -> that IS the position; never top up,
                          never re-send, symbol done for the day

Log intended_qty, filled_qty, fill_ratio on every entry ATTEMPT.
Slippage is not separately capped — 8.6's RISK_OVERRUN governs the only
consequence that matters.

### 8.5 Stop placement (after fill)

    STOP = session_low   (lowest Low across 09:30-10:00 ET, per 8.3)

Placed immediately as a real **stop-market** order for `filled_qty`
ONLY — never intended_qty. A stop covering shares you do not hold goes
short when it triggers (Constraint #6). The stop never widens.

It is the 09:30-10:00 low, NOT the low up to the fill: it is already
known from the 8.2 pull, and a later low could only widen the stop,
which this section forbids anyway.

### 8.6 Post-fill reconciliation

    actual_risk_share = fill_price - STOP
    actual_risk_pct   = (filled_qty x actual_risk_share) / equity

    IF actual_risk_pct > 0.0075
        -> exit immediately at market, log RISK_OVERRUN
    ELSE
        -> log planned vs actual risk and continue

With no limit price bounding the fill, this is the sole slippage
governor. 0.0075 is 1.5x the 0.005 target.

Full size in one order. Never scale in. Never add.

## SECTION 9 — POSITION MANAGEMENT (END OF DAY ONLY, in order)

- **9.1 Stop**: resting stop-market order is always active at Alpaca.
  Gap-below-stop is handled by the broker, not by us polling intraday.
  Reconcile daily: if a symbol drops out of `alpaca.sh positions` without
  our routine having exited it, the resting stop already filled — record
  it before running `position_manager.py`.
- **9.2 First partial**: `IF sessions_held == 4 AND position is at a
  profit -> sell 1/3 of shares at market on close`.
- **9.3 Stop after partial**: raise stop to
  `max(original STOP, fill_price - 0.5 x risk_per_share)`. **Deliberately
  NOT break-even** — this is the single largest deviation from the
  source strategy. Given a 20–25% win rate, a break-even stop removes the
  position from exactly the volatile names that produce outlier winners.
- **9.4 Trailing exit**: after the partial, `IF close < reference SMA ->
  exit entire remaining position at market on close`. Trigger is a
  CLOSE, never an intraday touch.
- **9.5 Earnings while held**: [SKIPPED for v1.0 — no data source, known gap]
- **9.6 No time stop.** Only the stop, the trailing SMA, or (skipped)
  earnings rule exit.

## SECTION 10 — PORTFOLIO LIMITS (checked before every entry; breach blocks it)

```
Max concurrent positions      5
Max new entries per day       2
Max total open risk           3.0% of equity
Max single position           20% of equity at entry
Max gross exposure            100% of equity
Max positions per sector      [DROPPED for v1.0 — no sector data source,
                                known gap. See Operator Substitutions.]
```

If more candidates qualify than limits allow, rank by 63-day return,
highest first. Every number in this section is operator-invented — the
source material has no portfolio-level risk limit. Because the universe
filter selects a single correlated momentum cohort, positions are not
independent bets.

## SECTION 11 — LOGGING

- **Per entry** (`memory/TRADE-LOG.md`): symbol, timestamp, ORH, fill,
  stop, risk/share, shares, account risk %, equity, reference SMA
  selected, portfolio state, `entry_mechanism: retrospective_10ET_approximation`.
- **Per exit** (`memory/TRADE-LOG.md`): symbol, timestamp, price,
  triggering rule, R-multiple, days held.
- **Per rejection** (`memory/CANDIDATES.md`): symbol, first
  disqualifying rule.
- **Daily** (`memory/CANDIDATES.md` + `memory/TRADE-LOG.md`): regime
  state+values, universe count, candidate count, entries, open
  positions, total open risk, equity.
- **Distribution tracking** (`memory/WEEKLY-REVIEW.md`, required, running):
  win rate, average winning R, average losing R, largest winning R, share
  of total profit from the single best trade. If the largest winner isn't
  several times the average winner, report that exits may be cutting the
  tail.
- **Exceptions** (`memory/EXCEPTIONS-LOG.md`): every
  `UNSPECIFIED_SITUATION`, `STOP_TOO_WIDE`, HALT event, and any rule-
  application uncertainty. "The most valuable records the system produces."

## SECTION 12 — HALT CONDITIONS (stop trading, close nothing, report)

```
- Drawdown >= 25% from peak equity (tracked in memory/RISK-STATE.json)
- Any order rejected for a reason not understood
- Data feed gap or suspected bad data
- Conflict between this document and an instruction received
- Any situation where the agent feels the need to deviate from a rule
```

Threshold is deliberately 25%, not 10% — 20% drawdowns are described as
normal. The last condition is not optional: if a rule seems wrong in a
specific instance, that's information for the operator, not grounds to
override. Mechanism: `memory/HALT.md` — see Operator Substitutions.
**Only a human clears it** (`/resume`), never a routine.

## SECTION 14 — OPERATOR-CHOSEN PARAMETERS (do not change; report how they behave)

1.10 extension limit · 5-minute opening range · 0.5% risk/trade · day-4
partial timing · half-risk stop after partial · all of Section 10 ·
63-day impulse lookback/30% threshold · 2R earnings cushion ·
**0.75% actual_risk_pct overrun trip (8.6)** · the 09:55-10:00 bar as
the HOLDING confirmation and source of decision_price (8.2/8.3) ·
**10:20 ET decision time (8.2)** — driven by the free-SIP 15-minute
delay, not by anything in the source.
(RETIRED 2026-08-11 (b): PRICE_RAN_AWAY, with the stop-limit band.)

---

## Operator Substitutions & Data-Availability Decisions

These exist because a live system needs concrete data sources and
execution mechanics the spec deliberately leaves as principles. Per
Section 0.3 these are data-availability/engineering substitutions, not
strategy inventions — logged here for the same reason the spec logs its
own rejected claims.

- **NASDAQ Composite proxy: `ONEQ`** (Fidelity Nasdaq Composite Index
  ETF). Alpaca's market data has no raw ^IXIC index product. ONEQ tracks
  the actual Composite, unlike QQQ (Nasdaq-100 only).
- **Entry monitoring**: Section 8.2 requires continuous 09:35–10:00 ET
  monitoring. Approximated as a **single retrospective check at 10:05 ET**
  using the 09:30–10:00 5-minute historical bars — the first bar closing
  above ORH determines the trigger. This is a deliberate simplification
  given cron-only infrastructure (no persistent process). Every entry is
  tagged `entry_mechanism: retrospective_10ET_approximation` so this is
  auditable. Real fills are still placed as real orders against Alpaca —
  never synthetic/simulated fills.
- **Momentum percentile population** (Section 5): ranked against Section
  5's own price/liquidity/ADR survivors, not the raw ~11k-symbol universe
  — matches the order the spec lists its filters in.
- **Data feed**: Alpaca free/IEX tier. Dollar-volume figures understate
  true consolidated-tape volume. The $10M/30×-equity threshold is used
  exactly as stated (Section 0.4 forbids adjusting it to compensate) —
  `scripts/screener.py` logs a loud warning every run instead.
- **Common-stock/ETF filtering**: best-effort name-regex exclusion applied
  directly to Alpaca's own tradable-asset `name` field (`scripts/screener.py::NON_COMMON_STOCK_RE`)
  — catches `ADR`/`American Depositary`/`Warrant`/`Rights`/`Units`/`Preferred`/`Notes`/
  `ETF`/`Trust`/`Index Fund` plus a non-exhaustive list of major ETF-sponsor
  names (ProShares, Direxion, iShares, SPDR, VanEck, WisdomTree, Global X,
  First Trust, Simplify, YieldMax, Roundhill, Amplify). The free,
  unauthenticated Nasdaq Trader symbol directory (which has an explicit
  ETF Y/N flag) was tried first and worked from a local sandbox, but a
  live test from inside an actual Claude Code cloud routine returned
  HTTP 403 on both endpoints — confirmed network/IP-level blocked, not a
  timeout, not fixable by spoofing a browser User-Agent (also tested).
  Rather than depend on a source that's blocked in production, this uses
  data already being fetched (zero new network dependency). Verified
  empirically against a live pull of Alpaca's ~13,300-asset universe:
  correctly excludes 7,445 ETFs/funds while keeping 5,901 common-stock-like
  names. Known residual gaps: leveraged/thematic ETFs whose short name
  omits both "ETF" and "Trust" (e.g. TQQQ: "ProShares UltraPro QQQ" — only
  caught here because "ProShares" is in the sponsor list, which is not
  exhaustive) and foreign ADRs whose name doesn't say "ADR"/"American
  Depositary" (e.g. TSM: "Taiwan Semiconductor Manufacturing Company
  Ltd.") are not caught at all.
- **Prior-impulse (L, H) selection** (Section 6.1): multiple (L, H) pairs
  can satisfy the numeric constraints. The pair with the **most recent
  valid H** is selected, since Section 6.2 measures the consolidation
  window from H to today. See `scripts/lib/indicators.py::find_prior_impulse`.
- **Resting stop order type**: placed as `stop` (stop-market), not
  `stop-limit` — required so Section 9.1's "gap below stop → exit at
  market, no bounce-waiting" is enforced by Alpaca with zero intraday
  polling.
- **Sector cap dropped** (Section 10): no free, reliable sector data
  source for Alpaca-listed symbols was approved. The other four
  portfolio limits still apply and still block entries.
- **Position state**: `memory/POSITIONS.json`, structured JSON, not
  prose — the only file in `memory/` that isn't markdown. Section 9's
  math needs exact original fill/stop/risk values carried forward across
  days; re-deriving them by re-parsing a markdown table would itself be
  the kind of inference Section 0.3 forbids.
- **Peak-equity / drawdown tracking**: `memory/RISK-STATE.json`, updated
  every `daily-summary` run.

## SECTION 15 — DATA FEED: §8 IS SUSPENDED ON THE FREE TIER

*Operator determination 2026-08-11. Full text in
`docs/QMS-01_Operational_Spec_v1.1_paper.md` §15, which is authoritative.*

**Live intraday execution requires a paid real-time SIP subscription.
`market-open` stays DISABLED and places no entries.**

Free-tier real-time is IEX only — a small single-digit share of
consolidated volume. Applied to §8 that is a directional bias, not noise:
IEX prints fewer trades, so its 5-minute high understates `ORH` and its
low overstates the session low; `est_risk_share` is therefore understated;
and §8.3 divides `risk_capital` by that understated figure, so `shares`
comes out **oversized**. An oversized position is a Section 10 breach.

Firing later (~10:20 ET) to clear the 15-minute SIP delay was considered
and **rejected**: acting 20+ minutes after the trigger means the fill
bears no relation to `ORH × 1.0050` and the stop none to the session low
at trigger. That is a different entry rule with unknown behaviour, not
§8.2 with latency.

Rules now in force:
1. `market-open` DISABLED. Do not re-enable without real-time SIP.
2. All historical/daily work uses `feed=sip`, `end` >= 15 minutes old.
   NEVER fall back to IEX silently — a request that cannot be served by
   SIP fails loudly and logs `DATA_FEED_UNAVAILABLE`.
3. Any code path computing `ORH`, a session low, or a position size must
   assert `feed == "sip"` and raise otherwise.
4. There is deliberately NO config flag to override this. Re-enabling
   live entries is a spec amendment, not a setting.

Sections 4–7 are unaffected — the screener reads completed prior
sessions, where the delay never binds.

## Known Gaps for v1.0 (documented, not silently absorbed)

- No earnings-date exclusion (§7) or earnings-hold rule (§9.5).
- No sector-concentration cap (§10).
- ADR/common-stock separation is best-effort name-regex, not authoritative.
- Entry detection is a retrospective 10:05 ET approximation, not true
  real-time order racing against the market — and per Section 15 above it
  is SUSPENDED entirely until a real-time SIP feed exists.
- (Resolved 2026-08-11: dollar-volume figures previously reflected the
  IEX feed and understated consolidated volume by a measured median of
  28.7x. The screener now uses `feed=sip`.)
