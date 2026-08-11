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
    """Section 6.1, as amended by the operator 2026-08-11.

    Deterministic single pass — NOT a search over candidate pairs:

        H = highest High in the last `lookback` sessions occurring at
            least `min_h_age` sessions ago. Ties -> most recent.
        L = lowest Low in the `max_lh_span` sessions immediately
            preceding H. Ties -> most recent.

        Validate (H/L - 1) >= min_gain and span(L,H) <= max_lh_span.
        On failure -> not a candidate. Do NOT look for another pair.

    The previous implementation searched backwards for the most recent
    qualifying H. Because H can never be newer than `min_h_age`, that H
    advanced one session per session for as long as price stayed >=30%
    above any low in the preceding 25 sessions — so the consolidation
    window measured from H was pinned near `min_h_age + 1` sessions
    regardless of the real base. Section 6.2's 10-40 test was inert,
    6.3-6.5 analysed a truncated slice, and 6.7 measured containment
    against an ordinary base bar instead of the impulse peak. H must be
    the highest high for 6.7 to mean anything.

    Returns (L_index, H_index, L_price, H_price) or None.
    """
    if index is None:
        index = len(bars) - 1
    start = max(0, index - lookback + 1)
    latest_h_idx = index - min_h_age
    if latest_h_idx < start:
        return None

    # H: highest High in [start, latest_h_idx]. Ties -> most recent, so
    # iterate forwards and take >= (a later equal high replaces an
    # earlier one).
    h_idx = start
    for i in range(start, latest_h_idx + 1):
        if bars[i]["h"] >= bars[h_idx]["h"]:
            h_idx = i
    h_price = bars[h_idx]["h"]

    # L: lowest Low in the max_lh_span sessions immediately preceding H.
    l_start = max(0, h_idx - max_lh_span)
    if l_start >= h_idx:
        return None
    l_idx = l_start
    for i in range(l_start, h_idx):
        if bars[i]["l"] <= bars[l_idx]["l"]:
            l_idx = i
    l_price = bars[l_idx]["l"]

    if l_price <= 0:
        return None
    if (h_price / l_price - 1.0) < min_gain:
        return None
    if (h_idx - l_idx) > max_lh_span:
        return None
    return (l_idx, h_idx, l_price, h_price)


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
