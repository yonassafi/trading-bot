"""
Shared indicator math for QMS-01 Breakout v1.1-paper.

Single source of truth for every rolling-window/percentile calculation
used by scripts/screener.py (Sections 4-7) and scripts/position_manager.py
(Section 9). Duplicating this math in two places would risk the two
engines silently disagreeing on what a rule means — itself a form of the
rule-inventing Section 0.3 forbids.

Bars are plain dicts shaped like Alpaca's bar objects: {"t","o","h","l","c","v"},
sorted ascending by time. All "index" params default to the last bar
(the most recent complete session).
"""


def closes(bars):
    return [b["c"] for b in bars]


def highs(bars):
    return [b["h"] for b in bars]


def lows(bars):
    return [b["l"] for b in bars]


def sma(values, period, index=None):
    """Simple moving average of `values` ending at `index` (default: last).
    None if there isn't enough history."""
    if not values:
        return None
    if index is None:
        index = len(values) - 1
    start = index - period + 1
    if start < 0:
        return None
    window = values[start:index + 1]
    return sum(window) / period


def sma_series(values, period):
    """Full SMA series, same length as `values`, None where undefined."""
    return [sma(values, period, i) for i in range(len(values))]


def adr20(bars, index=None):
    """ADR_20 = mean of (High/Low - 1) over 20 sessions, as a percent.
    Section 5. This is the ONLY ADR definition used anywhere in this repo."""
    if index is None:
        index = len(bars) - 1
    start = index - 20 + 1
    if start < 0:
        return None
    window = bars[start:index + 1]
    ratios = [(b["h"] / b["l"] - 1.0) for b in window if b["l"] > 0]
    if len(ratios) < 20:
        return None
    return (sum(ratios) / 20) * 100.0


def dollar_volume_avg(bars, period=50, index=None):
    if index is None:
        index = len(bars) - 1
    start = index - period + 1
    if start < 0:
        return None
    window = bars[start:index + 1]
    return sum(b["c"] * b["v"] for b in window) / period


def pct_return(bars, period, index=None):
    """(close[index] / close[index-period] - 1)."""
    if index is None:
        index = len(bars) - 1
    if index - period < 0:
        return None
    c_now = bars[index]["c"]
    c_then = bars[index - period]["c"]
    if c_then == 0:
        return None
    return c_now / c_then - 1.0


def percentile_rank(value, population):
    """Percentage of `population` that is <= value."""
    if not population:
        return None
    n = len(population)
    count_le = sum(1 for v in population if v <= value)
    return (count_le / n) * 100.0


def range_pct(bars, n, index=None):
    """R(n) = (max High - min Low) / min Low over the last n sessions
    ending at `index`. Section 6.5's monotonic-contraction test."""
    if index is None:
        index = len(bars) - 1
    start = index - n + 1
    if start < 0:
        return None
    window = bars[start:index + 1]
    hi = max(b["h"] for b in window)
    lo = min(b["l"] for b in window)
    if lo == 0:
        return None
    return (hi - lo) / lo


def find_prior_impulse(bars, index=None, lookback=63, min_gain=0.30,
                        min_h_age=10, max_lh_span=25):
    """Section 6.1. Search the trailing `lookback` sessions ending at
    `index` for a low L and later high H where (H/L - 1) >= min_gain, H
    occurred at least `min_h_age` sessions before `index`, and the span
    between L and H is <= max_lh_span sessions.

    Multiple (L, H) pairs can satisfy these constraints. This picks the
    pair with the MOST RECENT valid H, because Section 6.2 measures the
    consolidation window from H to today, and the most recent qualifying
    high is what's operationally relevant to today's setup. This
    selection rule is a necessary implementation choice (the spec gives
    the numeric constraints but not a tie-break), documented in
    memory/TRADING-STRATEGY.md's Operator Substitutions section.

    Returns (L_index, H_index, L_price, H_price) or None.
    """
    if index is None:
        index = len(bars) - 1
    start = max(0, index - lookback + 1)
    latest_h_idx = index - min_h_age
    if latest_h_idx < start:
        return None

    for h_idx in range(latest_h_idx, start - 1, -1):
        h_price = bars[h_idx]["h"]
        l_start = max(start, h_idx - max_lh_span)
        for l_idx in range(h_idx - 1, l_start - 1, -1):
            l_price = bars[l_idx]["l"]
            if l_price <= 0:
                continue
            if (h_price / l_price - 1.0) >= min_gain:
                return (l_idx, h_idx, l_price, h_price)
    return None


def segment_min_lows(bars, start_idx, end_idx):
    """Section 6.4. Split [start_idx, end_idx] (inclusive) into three
    consecutive segments by session count (remainder folded into the
    final segment). Returns (min_low_seg1, min_low_seg2, min_low_seg3) or
    None if the window is too short to split."""
    length = end_idx - start_idx + 1
    seg_len = length // 3
    if seg_len < 1:
        return None
    seg1_end = start_idx + seg_len - 1
    seg2_end = start_idx + 2 * seg_len - 1
    seg1 = bars[start_idx:seg1_end + 1]
    seg2 = bars[seg1_end + 1:seg2_end + 1]
    seg3 = bars[seg2_end + 1:end_idx + 1]
    if not seg1 or not seg2 or not seg3:
        return None
    return (
        min(b["l"] for b in seg1),
        min(b["l"] for b in seg2),
        min(b["l"] for b in seg3),
    )


def select_reference_sma(bars, start_idx, end_idx, candidates=(10, 20, 50), threshold=0.80):
    """Section 6.3. Among `candidates` (shortest first), pick the shortest
    period whose SMA sits below price for >= `threshold` fraction of the
    consolidation window [start_idx, end_idx]. Returns the period (int)
    or None if none qualify."""
    closes_list = closes(bars)
    for period in sorted(candidates):
        series = sma_series(closes_list, period)
        window = range(start_idx, end_idx + 1)
        valid = [i for i in window if series[i] is not None]
        if not valid:
            continue
        below = sum(1 for i in valid if series[i] < closes_list[i])
        if below / len(valid) >= threshold:
            return period
    return None
