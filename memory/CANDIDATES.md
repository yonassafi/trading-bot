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
10 SMA: 101.8475 (yesterday 101.2055) | 20 SMA: 101.3142 (yesterday 101.1737)

**Universe:** 5900 tradable common-stock candidates
**Stage A survivors (price/liquidity/ADR):** 200
**Stage B candidates (post setup-scan/exclusions):** 0

⚠️ Dollar-volume figures use Alpaca's default (IEX) feed, which understates true consolidated market volume. The $10M / 30x-equity threshold is applied literally per Section 0.4 — not adjusted to compensate. Known limitation, not a bug.

No candidates qualified today.

**Rejection counts (first disqualifying rule):**
- dollar_volume: 3460
- price_below_5: 1551
- adr_below_4pct: 500
- momentum_percentile: 198
- insufficient_history: 189
- monotonic_contraction_failed: 1

