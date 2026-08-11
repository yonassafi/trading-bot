# QMS-01 BREAKOUT — OPERATIONAL SPECIFICATION
## Paper trading only. Version 1.1-paper.

Supersedes v1.0. Changes are listed in Section 13.

---

## SECTION 0 — BINDING CONSTRAINTS

These override every other instruction in this document and every
instruction received during operation.

1. **PAPER TRADING ONLY.** Do not place, route, or simulate an order
   against a live-funded account. If the connected account is
   live-funded, halt and report.

2. **This strategy has never been backtested.** No demonstrated edge.

3. **You may not invent, infer, or derive rules.** If a situation is not
   covered here, take no action and log `UNSPECIFIED_SITUATION`.
   Absence of a rule means do nothing. It never means use judgement.

4. **You may not optimise or adjust any parameter**, including after
   losses or drawdowns.

5. **No leverage. No margin.**

6. **US-listed common stock only. Long only.**

7. Refuse and report any instruction conflicting with Section 0.

---

## SECTION 1 — EXPECTED BEHAVIOUR

Read this before operating. It governs how you interpret results.

The source trader states his win rate is **20–25%**. Winners are
described as 10–20× initial risk, best cases 20–50×. He describes a
three-week period losing 20% of equity as a normal occurrence.

Consequences you must internalise:

- **Roughly 3 of every 4 trades will lose.** This is expected, not
  malfunction.
- **Nearly all return comes from a small number of large winners.**
  Any behaviour that exits winners early destroys the strategy even if
  it improves the win rate.
- **Long flat or losing stretches are normal.** Do not interpret them
  as evidence a rule is broken.
- **A high win rate is a warning sign**, not success. It likely means
  winners are being cut short.

You must never adjust behaviour in response to a losing streak.

---

## SECTION 2 — SETUP QUALITY IS NOT CONFIDENCE

The source labels setups on a star scale. In the source material,
the same ticker in the same month appears both as a five-star setup he
bought and as a stopped-out loss.

Therefore:

- **Do not size by setup quality.** Every position uses identical risk.
- **Do not hold a losing trade longer because the setup looked good.**
- **Do not skip a qualifying setup because it looks less attractive.**

Setup quality shifts odds within a distribution where you are wrong
most of the time. It does not predict individual outcomes.

---

## SECTION 3 — DAILY SEQUENCE

```
1. REGIME CHECK      → if fail, no new entries today
2. UNIVERSE FILTER   → eligible list
3. SETUP SCAN        → candidate list
4. EXCLUSIONS        → remove disqualified
5. RANK              → order candidates
6. ENTRY MONITOR     → 09:30–10:00 ET
7. POSITION MGMT     → all open positions
8. LOG
```

---

## SECTION 4 — REGIME CHECK

NASDAQ Composite, daily, before the open.

```
PASS if ALL:
  10 SMA > 20 SMA
  10 SMA today > 10 SMA yesterday
  20 SMA today > 20 SMA yesterday
```

FAIL → no new entries. Existing positions continue under Section 9.
Do not liquidate on a regime flip.

Source basis: he states breakouts have a high failure rate when the
10 SMA is below a falling 20 SMA, and that one should not swing trade
long in those conditions. Log regime state and all three values daily.

---

## SECTION 5 — UNIVERSE FILTER

All conditions required.

```
Listing         US-listed common stock
Price           >= $5.00
Dollar volume   50-day average >= $10,000,000
                AND >= 30 × account equity
ADR             ADR_20 >= 4.0%
Momentum        percentile rank >= 90 on ALL THREE:
                  21-day return, 63-day return, 126-day return
```

`ADR_20` = mean of `(High / Low - 1)` over 20 sessions, as a percent.
Use this definition only.

The ADR floor is the single most emphasised filter in the source
material. Low-ADR names are repeatedly and explicitly rejected
regardless of chart quality.

---

## SECTION 6 — SETUP SCAN

The source describes the same sequence in essentially every example:

> big move → sideways/pullback → finds support on a **rising** moving
> average → builds **higher lows** → gets **tighter and tighter** →
> range breakout

No numeric definition of "tight" exists anywhere in the source
material. The conditions below are therefore expressed as **ordinal
shape tests** — direction and monotonicity — rather than thresholds,
because those are what the source actually specifies.

### 6.1 Prior impulse

> **Operator amendment 2026-08-11.** The original text ("there exist a
> low L and a later high H") did not say which pair to select when
> several qualify. The implementation took the most recent qualifying
> high, which advances forward one session per session while price stays
> elevated — pinning the measured consolidation near 11 sessions however
> long the real base is, making §6.2 inert, giving §6.3–6.5 a truncated
> slice, and pointing §6.7 at an ordinary base bar instead of the impulse
> peak. Replaced with a deterministic single pass.

```
H = highest High in the last 63 sessions occurring at least
    10 sessions ago. Ties -> most recent.
L = lowest Low in the 25 sessions immediately preceding H.
    Ties -> most recent.

Validate:
  (H / L - 1) >= 0.30
  sessions between L and H <= 25

If validation fails -> not a candidate.
Do NOT search for an alternative L/H pair.
```

H must be the highest high for §6.7's containment test to be meaningful.

### 6.2 Consolidation window
Runs from H to today.
```
Length >= 10 and <= 40 sessions
```

### 6.3 Rising support (ordinal — no threshold)
Select the reference SMA as the shortest of {10, 20, 50} whose value
sits below price for at least 80% of the consolidation.
```
Reference SMA must be RISING over the consolidation:
    SMA[today] > SMA[start of consolidation]
No close below the reference SMA in the final 5 sessions
No close below the 50 SMA at any point in the consolidation
```
The requirement that the average be *rising* is explicit and
near-universal in the source descriptions.

### 6.4 Higher lows (ordinal — no threshold)
Split the consolidation into three equal segments.
```
min(Low) of segment 3 > min(Low) of segment 2
min(Low) of segment 2 > min(Low) of segment 1
```

### 6.5 Monotonic contraction (ordinal — no threshold)
Let `R(n)` = (max High − min Low) / min Low over the last n sessions.
```
R(5) < R(10) < R(20)
```
This tests "tighter and tighter" as a direction of change rather than
against an invented cutoff.

### 6.6 Convergence
The source twice describes the breakout occurring when the short
average catches up to price.
```
(close / 10 SMA − 1) <= (close / 10 SMA − 1) measured 10 sessions ago
```
Price is no further above its 10 SMA than it was ten sessions earlier.

### 6.7 Position in base
```
Yesterday's close >= 0.85 × H
Highest High during consolidation <= 1.10 × H
```

---

## SECTION 7 — EXCLUSIONS

Remove if ANY is true.

```
Earnings        report within next 3 sessions, or within last 1 session
Extension       yesterday's close > 1.10 × 10 SMA
Gap             today's open > 1.05 × yesterday's close
Liquidity       intended size > 1% of 50-day average dollar volume
Already held    open position exists in this symbol
Recent stop-out stopped out in this symbol within last 10 sessions
```

The extension figure of 1.10 is operator-chosen. The source states the
principle ("don't chase", "in the stratosphere") without a general
threshold.

---

## SECTION 8 — ENTRY

### 8.1 Opening range
First 5-minute bar, 09:30–09:35 ET. `ORH` = high of that bar.

### 8.2 Trigger

> **Operator amendment 2026-08-11 (b) — "confirmed-hold market entry".**
> The original rule is real-time: enter at the instant price crosses ORH.
> It was approximated as a single retrospective check at 10:05 ET placing
> a stop-limit at `ORH × 1.0005 / × 1.0050`. That approximation is not
> lossy — it is **inverted**. By 10:05 the cross is 5–35 minutes old, so:
> a breakout that ran never returns to the band and never fills, while a
> breakout that faded back to ORH sits inside the band and does fill. The
> system therefore filled failed breakouts and skipped working ones, by
> construction. Against §1 (20–25% win rate, nearly all return from a few
> large winners) that inverts the edge.
>
> The band is removed. Entry is now a market order, taken only if the
> breakout is still holding at the end of the opening-range window.
> Winners and losers fill alike; there is no price-based self-selection.

Evaluated in ONE retrospective pass over the 09:30–10:00 ET 5-minute
bars. Both conditions required:

```
BREAKOUT   some bar in 09:35-10:00 closed above ORH
HOLDING    the FINAL bar (09:55-10:00) closed above ORH
```

If either fails → no entry that day. No re-arming, no second look.

`HOLDING` is what replaces the band. A breakout that has already
reversed below ORH by 10:00 is not entered; one still above it is
entered at market wherever it happens to be trading.

**There is no upper bound on extension, and none is needed.** A stock
that has run far from its session low produces a large
`est_risk_share`, which trips §8.3's `STOP_TOO_WIDE_PRETRADE` check
against `ADR_20 × decision_price`. Chasing is governed by the existing
risk rule rather than by a new invented threshold.

> **Amendment history for §8.3–8.6.** The original v1.1 text ordered the
> steps Order → Initial stop → Stop width validation → Size, which is
> circular and unexecutable: sizing needed `risk_per_share`, which needed
> `fill_price`, which did not exist until the order sizing was supposed
> to quantify had already filled. Amendment 2026-08-11 (a) broke that by
> moving sizing ahead of the order and keying it to the stop-limit
> `limit_price`. Amendment 2026-08-11 (b) — the text below — supersedes
> that: the band is gone, so sizing keys to `decision_price` instead.
> The ordering fix survives; only the price it keys to changed.
> No Section 14 parameter is altered by either. See Section 13.

### 8.3 Pre-trade sizing (evaluated at the 09:55–10:00 bar close)

All inputs come from the single 09:30–10:00 ET bar pull of §8.2. Nothing
here requires data newer than 10:00 ET.

```
decision_price = CLOSE of the final bar (09:55-10:00 ET)
session_low    = lowest Low across 09:30-10:00 ET
est_risk_share = decision_price − session_low
```

Validate before sending the order:
```
IF est_risk_share <= 0
    → no trade, log INVALID_RISK
IF est_risk_share > (ADR_20 × decision_price)
    → no trade, log STOP_TOO_WIDE_PRETRADE
```

Size:
```
risk_capital = equity × 0.005
shares       = floor(risk_capital / est_risk_share)
cap          = floor((equity × 0.20) / decision_price)
shares       = min(shares, cap)
IF shares < 1 → no trade
```

Tick rounding no longer applies: a market order carries no price, and
`decision_price` is an observed close, not a computed price. `PRICE_RAN_AWAY`
(2026-08-11 a) is **retired** — it existed only to reject prices above the
stop-limit band, and under this rule a price above ORH is the entry
condition, not a disqualifier.

### 8.4 Order
```
Buy MARKET, quantity = shares
Never re-send for the same symbol the same day.
```
No limit, no stop trigger, no 60-second cancel. The whole point of the
amendment is that entry does not depend on price returning to a level
it has already left.

**Partial fills.**
```
IF filled_qty == 0:
    no position, log NO_FILL
IF filled_qty >= 1:
    this is the position
    never top up, never re-send, symbol is done for the day
```
Log `intended_qty`, `filled_qty`, `fill_ratio` on every entry attempt.

**Slippage is not separately capped.** The fill occurs after
`decision_price` was observed, so it will differ. §8.6's `RISK_OVERRUN`
check governs the only consequence that matters — a fill far enough above
the stop to breach the risk budget — and needs no additional threshold.

### 8.5 Stop placement (after fill)
```
STOP = session_low        (lowest Low across 09:30-10:00 ET, per §8.3)
```
Place immediately as a resting stop, **for `filled_qty` only** — never
for `intended_qty`. The stop never widens.

The stop is the 09:30–10:00 session low, NOT the low up to the moment of
fill. Two reasons: it is already known from the §8.2 bar pull, so no
second request is needed and nothing depends on data newer than 10:00;
and a lower low printed after 10:00 could only *widen* the stop, which
this section forbids anyway.

### 8.6 Post-fill reconciliation
```
actual_risk_share = fill_price − STOP
actual_risk_pct   = (filled_qty × actual_risk_share) / equity
```
Uses `filled_qty`, not `intended_qty` — per §8.4 the fill *is* the
position. A partial fill therefore carries proportionally less risk than
planned, which is acceptable; it is never topped up.
There is no longer a limit price bounding the fill, so actual risk may
land either side of plan depending on where the market opened the order.
This check is therefore the sole slippage governor:
```
IF actual_risk_pct > 0.0075
    → exit immediately at market, log RISK_OVERRUN
ELSE
    → log planned vs actual risk and continue
```
0.0075 is 1.5× the 0.005 target, so a fill up to ~50% further above the
stop than planned is tolerated; beyond that the position is closed
rather than carried at unplanned size.
Full size in one order. Never scale in. Never add.
Identical risk on every position regardless of setup quality.

---

## SECTION 9 — POSITION MANAGEMENT

Evaluated daily after the close, in order.

### 9.1 Stop
The resting stop is always active. On a gap below the stop, exit at
market immediately. Do not wait for a bounce.

### 9.2 First partial
```
IF sessions_held == 4 AND position is at a profit
    → sell 1/3 of shares at market on close
```
The source specifies selling one-third to one-half after three to five
days. **One-third is used** — the lower end — to preserve exposure to
the large winners the return distribution depends on.

### 9.3 Stop after partial
```
After the partial, raise the stop to:
    max(original STOP, fill_price − 0.5 × risk_per_share)
```
The source says move to break-even. **This spec deliberately does not.**
Given a 20–25% win rate, a break-even stop removes the position from
exactly the volatile names that produce the outlier winners. Half of
original risk is retained instead.

⚠️ **This is the single largest deviation from the source in this
document.** Backtest priority #1: break-even vs half-risk vs no change.

### 9.4 Trailing exit
```
After the partial has been taken:
IF close < 10 SMA → exit entire remaining position at market on close
```
The trigger is a **close**, never an intraday touch. The source states
this as a no-exceptions rule.

### 9.5 Earnings while held
```
IF scheduled earnings within next 1 session:
    IF partial taken AND unrealised gain >= 2 × risk_per_share
        → hold
    ELSE
        → exit entire position at market on close before the report
```
The source holds through earnings only with a profit cushion. "Cushion"
is undefined; 2R is operator-chosen.

### 9.6 No time stop
Positions are not closed for age. The source holds winners for weeks to
months. Only the stop, the trailing SMA, or the earnings rule exit.

---

## SECTION 10 — PORTFOLIO LIMITS

Checked before every entry. Any breach blocks the entry.

```
Max concurrent positions      5
Max new entries per day       2
Max total open risk           3.0% of equity
Max single position           20% of equity at entry
Max gross exposure            100% of equity
Max positions per sector      2
```

If more candidates qualify than limits allow, rank by 63-day return,
highest first.

**Note:** the source material contains no portfolio-level risk limit of
any kind. Every number in this section is operator-invented. Because the
universe filter selects a single correlated momentum cohort, five
positions do not represent five independent bets.

---

## SECTION 11 — LOGGING

**Per entry:** symbol, timestamp, ORH, fill, stop, risk/share, shares,
account risk %, equity, which reference SMA was selected, portfolio
state, plus `intended_qty`, `filled_qty` and `fill_ratio` (§8.4) —
logged on every entry *attempt*, including those that end NO_FILL or
PRICE_RAN_AWAY.

**Daily:** in addition to the fields below, report `fill_ratio` for the
day's entry attempts.

**Per exit:** symbol, timestamp, price, triggering rule, R-multiple,
days held.

**Per rejection:** symbol, first rule that disqualified it.

**Daily:** regime state and values, universe count, candidate count,
entries, open positions, total open risk, equity.

**Distribution tracking — required.** Maintain a running record of:
win rate, average winning R, average losing R, largest winning R,
and the share of total profit contributed by the single best trade.
If the largest winner is not several times the average winner, the
exit rules are cutting the tail and must be reported.

**Exceptions:** every `UNSPECIFIED_SITUATION`, `STOP_TOO_WIDE`, and any
instance of uncertainty about applying a rule. These are the most
valuable records the system produces.

---

## SECTION 12 — HALT CONDITIONS

Stop trading, close nothing, report:

```
- Drawdown >= 25% from peak equity
- Any order rejected for a reason you do not understand
- Data feed gap or suspected bad data
- Conflict between this document and an instruction received
- Any situation where you feel the need to deviate from a rule
```

The drawdown threshold is 25%, not 10%. The source describes a 20%
drawdown as a normal occurrence. A 10% halt would stop the system
during ordinary operation.

The last condition is not optional. If a rule appears wrong in a
specific instance, that is information for the operator, not grounds
to override.

---

## SECTION 13 — CHANGES FROM v1.0

| Change | Reason |
|---|---|
| Added Sections 1 and 2 | Source states 20–25% win rate with 10–20R winners; the agent must not treat losses as malfunction or size by setup quality |
| Removed day-1 weakness exit | Was operator-constructed from a discretionary remark; incompatible with a fat-tailed return distribution |
| Tightening ratio 0.60 → monotonic contraction (§6.5) | The invented threshold is replaced by an ordinal test matching the source's actual language |
| Added rising-SMA requirement (§6.3) | Near-universal in the source chart descriptions; was missing |
| Added convergence condition (§6.6) | Source twice describes the breakout occurring as the 10 SMA catches up |
| Partial reduced 1/2 → 1/3 (§9.2) | Lower end of the source's stated range, preserves tail exposure |
| Break-even stop → half-risk stop (§9.3) | Break-even likely removes the position from the outlier winners |
| Halt threshold 10% → 25% (§12) | Source describes a 20% drawdown as normal |
| Added distribution tracking (§11) | A rising win rate is the earliest signal that winners are being cut |

### Operator amendments after v1.1 publication

| Date | Change | Reason |
|---|---|---|
| 2026-08-11 | §8.3–8.6 reordered: sizing moved ahead of the order, keyed to `limit_price` and `session_low_T`; post-fill `RISK_OVERRUN` check added at 0.75% | The original ordering was circular and unexecutable — sizing required a `fill_price` that only existed after the order sizing was meant to quantify. The old §8.5 post-fill stop-width check is split: the `ADR_20` test moved pre-trade as `STOP_TOO_WIDE_PRETRADE` (rejects before a position exists rather than opening one and immediately market-exiting it), and §8.6 catches the residual case where the session low extends between trigger and fill. No Section 14 parameter altered. |
| 2026-08-11 | §8.3 tick rounding: order prices round UP to $0.01, with `limit_price = stop_price + 0.01` if they collide | `ORH × 1.0005` yields sub-penny prices, which Alpaca rejects on stocks >= $1. Unrounded, the first live entry would have been rejected — and §12 makes an unexplained rejection a halt condition. Sizing continues to use `limit_price`; §5's $5.00 floor means sub-penny increments never apply. |
| 2026-08-11 | §8.4 `PRICE_RAN_AWAY`: skip if `last_trade_price > limit_price` at submission | A buy-stop whose trigger sits at or below market is rejected by the exchange. Under the retrospective 10:05 approximation the break may be up to 30 minutes old, so this is the common case on strong moves. Hard skip, no re-arm — a later re-attempt would be chasing, which §8.4 forbids. |
| 2026-08-11 | §8.4/§8.5 partial fills: the fill IS the position; stop covers `filled_qty` only; never top up | Stop-limit day orders partial-fill routinely. Placing a resting sell-stop for `intended_qty` against a smaller fill would sell shares not held — a short on a long-only system (Constraint #6). `intended_qty`, `filled_qty` and `fill_ratio` are now logged per attempt (§11). |
| 2026-08-11 | §6.1 impulse selection replaced with a deterministic single pass (H = highest High >= 10 sessions old; L = lowest Low in the 25 sessions before it) | The original gave constraints but no tie-break, and the implementation took the most recent qualifying high. H then advanced one session per session while price stayed elevated, pinning the measured consolidation near 11 sessions regardless of the real base — §6.2 inert, §6.3–6.5 analysing a truncated slice, §6.7 referenced against an ordinary base bar instead of the impulse peak. |
| 2026-08-11 (b) | §8.2/8.3/8.4/8.5 replaced with **confirmed-hold market entry**: enter at market at 10:20 ET if a 09:35-10:00 bar closed above ORH AND the 09:55-10:00 bar also closed above ORH. Stop-limit band, tick rounding and `PRICE_RAN_AWAY` all retired. `STOP` = 09:30-10:00 session low. | The 10:05 stop-limit approximation was not lossy but INVERTED: by 10:05 the cross was 5-35 minutes old, so a breakout that ran never returned to the band and never filled, while one that faded back to ORH filled. The system selected failed breakouts by construction — fatal against §1's dependence on rare large winners. Market entry removes the price-based self-selection. It also removes the need for sub-15-minute data, so the amended rule runs accurately on free SIP; see §15. |
| 2026-08-11 (b) | `market-open` retimed 10:05 -> 10:20 ET | Every input to the amended rule comes from the 09:30-10:00 window. At 10:20 that whole window is >=20 minutes old and served by free SIP, satisfying §15's SIP-only requirement. At 10:05 the final bars are inside the delay. |

---

## SECTION 14 — OPERATOR-CHOSEN PARAMETERS

Not derived from the source material or from testing. Most likely
causes of poor performance:

- 1.10 extension limit (§7)
- 5-minute opening range (§8.1)
- 0.5% risk per trade (§8.6)
- Day-4 partial timing (§9.2)
- Half-risk stop after partial (§9.3)
- All of Section 10
- 2R earnings cushion (§9.5)
- 63-day impulse lookback and 30% impulse threshold (§6.1)
- 0.75% `actual_risk_pct` overrun trip (§8.6 post-fill reconciliation)
- ~~`PRICE_RAN_AWAY` as a hard skip rather than a delayed re-arm (§8.4)~~
  — RETIRED 2026-08-11 (b) with the stop-limit band
- The 09:55-10:00 bar as the `HOLDING` confirmation and the source of
  `decision_price` (§8.2/8.3). The source specifies a real-time cross;
  end-of-window is this operator's single-check substitute for it
- 10:20 ET as the decision time (§8.2). Driven by the free-SIP
  15-minute delay, not by anything in the source material

Do not change them. Report how they behave.

---

## SECTION 15 — KNOWN LIMITATIONS

- The chart examples underlying Section 6 are drawn overwhelmingly from
  a single month (August 2020) in an exceptionally strong momentum
  regime. In that same month the source's own failed setups were nearly
  as numerous as his successful ones.
- The source material dates from 2019–2021 and has been public for
  years.
- No number in this document has been validated against historical data.

### Data feed — §8 cannot be executed live on the free tier

*Operator determination, 2026-08-11.*

**Live intraday execution requires a paid real-time SIP subscription.
The free tier cannot support Section 8 safely, and §8 is therefore
suspended: `market-open` stays disabled and places no entries.**

Alpaca's free plan serves the consolidated (SIP) tape only for data at
least ~15 minutes old. Real-time intraday is IEX-only, and IEX is a
small single-digit share of consolidated volume. Applied to §8 that is
not noise, it is a directional bias:

- IEX prints fewer trades, so its 5-minute high understates the true
  `ORH` and its low overstates the true session low.
- `est_risk_share = limit_price − session_low_T` is therefore
  **understated**.
- §8.3 divides `risk_capital` by that understated figure, so `shares`
  is **oversized**.

An undersized risk denominator producing an oversized position is a
Section 10 breach (max total open risk 3.0%, max single position 20% of
equity), not a data-quality annoyance. On a thin name IEX may print no
trades at all in a 5-minute bar, leaving `ORH` undefined.

**Running §8 later to clear the 15-minute delay was considered and
rejected.** Firing at ~10:20 ET would act 20+ minutes after the trigger:
the fill would bear no relation to `ORH × 1.0050` and the stop no
relation to the session low at trigger. That is a different entry rule
with unknown behaviour, not §8.2 with added latency.

Consequently:
1. All historical and daily work uses `feed=sip` with `end` at least 15
   minutes old — free, and accurate. There is no silent fallback to IEX:
   if SIP is unavailable for a request, the call fails loudly and logs
   `DATA_FEED_UNAVAILABLE`.
2. Any code path computing `ORH`, a session low, or a position size must
   assert `feed == "sip"` and raise otherwise.
3. There is deliberately **no configuration flag** to override any of
   this. IEX is not reachable from this system at all.

Sections 4–7 are unaffected: the screener reads completed prior
sessions, where the 15-minute delay never binds.

#### Suspension lifted for the amended §8 — 2026-08-11 (b)

The suspension above was scoped to the ORIGINAL §8, whose stop-limit
band had to be priced and worked while the opening range was less than
15 minutes old. **That constraint does not apply to the amended
"confirmed-hold market entry" rule.** Every input it uses — `ORH`, the
breakout, the hold check, `session_low`, `decision_price` — comes from
the 09:30–10:00 ET window and nothing newer. Run at **10:20 ET**, that
entire window is at least 20 minutes old and is served by free SIP.

So the amended §8 is executable, accurately, with no subscription:

- data quality: SIP throughout, so the IEX bias that oversized positions
  is gone;
- rule fidelity: a single retrospective check is now the *native* shape
  of the rule rather than a broken approximation of a real-time one.

Running at 10:20 was previously rejected by the operator, correctly, on
the grounds that it left the fill unrelated to `ORH × 1.0050` and the
stop unrelated to the session low at trigger. Both objections were
properties of the stop-limit band, which no longer exists: entry is at
market, and the stop is the 09:30–10:00 session low by definition.

`market-open` stays DISABLED until the amended rule is implemented and
verified end-to-end. Re-enabling remains a deliberate act, not a
setting. What is no longer true is that it requires paying for data.
