# Trading Strategy — QMS-01 Breakout v1.1-paper

**Full source spec:** `docs/QMS-01_Operational_Spec_v1.1_paper.md` (verbatim,
Sections 0–15). This file is the operational quick-reference the agent
reads every session. If the two ever disagree, the full spec in `docs/`
is authoritative — treat any disagreement itself as an `UNSPECIFIED_SITUATION`
to log, not something to silently resolve.

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

- **6.1 Prior impulse**: within the last 63 sessions, a low L and later
  high H exist where `(H/L - 1) >= 0.30`, H occurred >= 10 sessions ago,
  span between L and H <= 25 sessions.
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

- **8.1 Opening range**: first 5-minute bar, 09:30–09:35 ET. `ORH` = high
  of that bar.
- **8.2 Trigger**: between 09:35–10:00 ET, `IF last trade price > ORH -> enter`.
  After 10:00 ET, cancel — no entry that day. **Approximated** as a
  single retrospective check at 10:05 ET using 5-minute historical bars
  (operator decision, see below).
- **8.3 Order**: buy stop-limit, `stop = ORH + 0.05%`, `limit = ORH + 0.50%`.
  Cancel if unfilled after 60 seconds. Never chase.
- **8.4 Initial stop**: `STOP = low of the day at moment of fill`. Placed
  immediately as a real **stop-market** order (operator decision — see
  below). Never widens.
- **8.5 Stop width validation**: `risk_per_share = fill_price - STOP`.
  `IF risk_per_share > (ADR_20 x fill_price) -> exit immediately at
  market, log STOP_TOO_WIDE`.
- **8.6 Size**: `risk_capital = equity x 0.005`.
  `shares = floor(risk_capital / risk_per_share)`.
  `cap = floor((equity x 0.20)/fill_price)`. `shares = min(shares, cap)`.
  `IF shares < 1 -> no trade`. Full size in one order. Never scale in.
  Never add. Identical risk on every position regardless of setup quality.

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
63-day impulse lookback/30% threshold.

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

## Known Gaps for v1.0 (documented, not silently absorbed)

- No earnings-date exclusion (§7) or earnings-hold rule (§9.5).
- No sector-concentration cap (§10).
- Dollar-volume figures reflect IEX feed, not full consolidated volume.
- ADR/common-stock separation is best-effort name-regex, not authoritative.
- Entry detection is a retrospective 10:05 ET approximation, not true
  real-time order racing against the market.
