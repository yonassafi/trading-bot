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
```
Within the last 63 sessions there exist a low L and a later high H:
  (H / L - 1) >= 0.30
  H occurred at least 10 sessions ago
  sessions between L and H <= 25
```

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
Between 09:35 and 10:00 ET:
```
IF last trade price > ORH → enter
```
After 10:00 ET, cancel. No entry that day.

### 8.3 Order
```
Buy stop-limit
  stop  = ORH + 0.05%
  limit = ORH + 0.50%
Cancel if unfilled after 60 seconds. Never chase.
```

### 8.4 Initial stop
```
STOP = low of the day at moment of fill
```
Place immediately. The stop never widens. If the low extends after
entry, the stop does not move.

### 8.5 Stop width validation
```
risk_per_share = fill_price − STOP
IF risk_per_share > (ADR_20 × fill_price)
    → exit immediately at market, log STOP_TOO_WIDE
```

### 8.6 Size
```
risk_capital = equity × 0.005
shares       = floor(risk_capital / risk_per_share)
cap          = floor((equity × 0.20) / fill_price)
shares       = min(shares, cap)
IF shares < 1 → no trade
```
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
state.

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
