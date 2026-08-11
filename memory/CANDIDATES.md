# Candidates Log — QMS-01 Breakout v1.1-paper

Dated sections appended daily by `scripts/screener.py` (via
`routines/pre-market.md`). Each entry: regime state + values, universe
count, Stage A/B counts, ranked candidate list (if regime passed and any
qualified), and rejection counts by rule (Section 11).

No entries yet — screener has not run a full production pass. (Two
scaled-down smoke tests — 25-symbol cap — confirmed the pipeline
end-to-end during development, including validating the Alpaca-name-based
common-stock/ETF filter against a live pull of ~13,300 assets. Not
reproduced here since neither used a real day's full scan.)

## 2026-08-11 — Pre-market Screener

**Regime (ONEQ):** PASS
10 SMA: 101.7634 (yesterday 101.1034) | 20 SMA: 101.2567 (yesterday 101.1122)

**Universe:** 5914 tradable common-stock candidates
**Stage A survivors (price/liquidity/ADR):** 1109
**Stage B candidates (post setup-scan/exclusions):** 1

| Rank | Symbol | 63d Return | ADR_20 | Last Close | Ref SMA | Consol. High | $Vol 50d Avg |
|---|---|---|---|---|---|---|---|
| 1 | FBRX | 219.82% | 5.7% | $76.82 | 10 | $76.6 | $74,551,599 |

**Rejection counts (first disqualifying rule):**
- dollar_volume: 1729
- price_below_5: 1567
- adr_below_4pct: 1339
- momentum_percentile: 1064
- insufficient_history: 199
- close_below_reference_sma_recently: 4
- higher_lows_failed: 3
- close_below_50sma_in_consolidation: 3
- no_reference_sma: 2
- convergence_failed: 1
- extended_beyond_base: 1
- monotonic_contraction_failed: 1

