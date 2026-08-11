#!/usr/bin/env python3
"""
QMS-01 Breakout v1.1-paper — Sections 4-7 screener.

Run once daily, pre-market (routines/pre-market.md), using data through
yesterday's close. Pure stdlib — no pandas/numpy — to keep an unattended
cron container's dependency surface at zero.

Pipeline:
  Section 4  Regime check (NASDAQ Composite proxy: ONEQ)
  Universe   Alpaca tradable assets, filtered to common-stock-like names
             using Alpaca's own asset `name` field (see NON_COMMON_STOCK_RE
             below — the Nasdaq Trader symbol directory was tried first but
             is IP/network-blocked from the Claude Code cloud routine
             container; confirmed via a live test, not a guess)
  Stage A    ~50-day bars, whole universe -> Section 5 price/liquidity/ADR
  Stage B    ~150-day bars, Stage-A survivors only -> Section 5 momentum
             percentile (ranked against Stage-A survivors, per operator
             decision) + Section 6 setup scan + Section 7 exclusions that
             don't require today's open (Extension, Already-held,
             Recent-stop-out). Gap and Liquidity-vs-intended-size are
             deferred to routines/market-open.md, which knows today's
             open and the sized order. Earnings is skipped for v1.0 (no
             data source) - see memory/TRADING-STRATEGY.md known gaps.

Writes memory/CANDIDATES.md. Every rejection is logged with the first
rule that disqualified it (Section 11).

Known limitation: Alpaca free/IEX-feed dollar-volume figures understate
true consolidated volume. Per Section 0.4 the $10M/30x-equity threshold
is used exactly as stated, not adjusted to compensate - a loud warning is
logged instead.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
import indicators as ind  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALPACA_SH = ROOT / "scripts" / "alpaca.sh"
CANDIDATES_FILE = ROOT / "memory" / "CANDIDATES.md"
POSITIONS_FILE = ROOT / "memory" / "POSITIONS.json"

# NASDAQ Composite proxy. Alpaca's market data API has no raw-index
# product for ^IXIC (it isn't a tradable security). ONEQ (Fidelity Nasdaq
# Composite Index ETF) is the closest tradable instrument that actually
# tracks the Composite, rather than a subset like QQQ (Nasdaq-100). This
# is a data-availability substitution per Section 0.3, not a strategy
# invention - documented in memory/TRADING-STRATEGY.md.
REGIME_PROXY = "ONEQ"

# Common-stock/ETF filtering: best-effort regex against Alpaca's own asset
# `name` field. The free Nasdaq Trader symbol directory (which has an
# explicit ETF Y/N flag) was tried first but returns HTTP 403 from the
# Claude Code cloud routine container's network — confirmed via a live
# test from that exact environment, not a timeout, not a guess. Rather
# than depend on a source that's actively blocked in production, this
# uses data already being fetched (no new network dependency at all).
#
# Verified empirically against real Alpaca asset names (see conversation
# history / commit message): catches plain "ETF" names (IWM, XLF, JEPI,
# BND), "Trust"-named funds (QQQ: "Invesco QQQ Trust, Series 1"; GLD:
# "SPDR Gold Trust"), and known ADR/warrant/unit/preferred language.
# Known residual gaps (accepted, documented): leveraged/thematic ETFs
# whose short name omits both "ETF" and "Trust" (e.g. TQQQ: "ProShares
# UltraPro QQQ") are only caught via the sponsor-name list below, which
# is NOT exhaustive; foreign ADRs whose name doesn't say "ADR"/"American
# Depositary" (e.g. TSM: "Taiwan Semiconductor Manufacturing Company
# Ltd.") are not caught at all. See memory/TRADING-STRATEGY.md known gaps.
NON_COMMON_STOCK_RE = re.compile(
    r"\b(ADR|American Depositary|Warrant|Rights?|Units?|Preferred|Notes?"
    r"|ETF|Trust|Index Fund"
    r"|ProShares|Direxion|iShares|Invesco QQQ|SPDR|VanEck|WisdomTree"
    r"|Global X|First Trust|Simplify|YieldMax|Roundhill|Amplify)\b",
    re.IGNORECASE,
)

# Debug/testing knob: cap the universe size so this can be smoke-tested
# without waiting on (or paying the API cost of) a full market scan.
# Cloud/production runs should NOT set this.
MAX_SYMBOLS = int(__import__("os").environ.get("SCREENER_MAX_SYMBOLS", "0")) or None


def run_alpaca(*args):
    result = subprocess.run(
        ["bash", str(ALPACA_SH), *args],
        capture_output=True, text=True, timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alpaca.sh {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_tradable_universe():
    """Section 5 "US-listed common stock" universe. Filters Alpaca's
    tradable us_equity assets using NON_COMMON_STOCK_RE against each
    asset's own `name` field — no external data source, see the comment
    on NON_COMMON_STOCK_RE for why and its known residual gaps."""
    assets = run_alpaca("assets")
    if not assets:
        # Section 12: "data feed gap or suspected bad data". An empty
        # asset list from Alpaca itself is a core-dependency failure, not
        # a filtering edge case — fail loudly rather than proceed with a
        # zero-symbol universe.
        raise RuntimeError("Alpaca returned zero tradable assets. Refusing to proceed.")
    universe = []
    excluded_count = 0
    for a in assets:
        if not a.get("tradable"):
            continue
        if a.get("class") != "us_equity":
            continue
        sym = a.get("symbol")
        if not sym:
            continue
        name = a.get("name", "")
        if NON_COMMON_STOCK_RE.search(name):
            excluded_count += 1
            continue
        universe.append(sym)
    print(
        f"Universe filter: {len(universe)} kept, {excluded_count} excluded "
        "as ETF/non-common-stock by name (best-effort, see known gaps)",
        file=sys.stderr,
    )
    if MAX_SYMBOLS:
        universe = universe[:MAX_SYMBOLS]
    return universe


def fetch_bars_batch(symbols, days, feed=None):
    """Daily bars for a batch of symbols via scripts/alpaca.sh bars,
    following next_page_token. Returns {symbol: [bar,...]} ascending by
    time."""
    if not symbols:
        return {}
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    out = {}
    page_token = None
    while True:
        qs = f"symbols={','.join(symbols)}&timeframe=1Day&start={start}&end={end}&limit=10000&adjustment=split"
        if feed:
            qs += f"&feed={feed}"
        if page_token:
            qs += f"&page_token={page_token}"
        resp = run_alpaca("bars", qs)
        bars = resp.get("bars", {}) or {}
        for sym, sym_bars in bars.items():
            out.setdefault(sym, []).extend(sym_bars)
        page_token = resp.get("next_page_token")
        if not page_token:
            break
    for sym in out:
        out[sym].sort(key=lambda b: b["t"])
    return out


def check_regime(feed=None):
    """Section 4."""
    bars_map = fetch_bars_batch([REGIME_PROXY], days=45, feed=feed)
    bars = bars_map.get(REGIME_PROXY, [])
    if len(bars) < 21:
        return {"pass": False, "reason": f"insufficient {REGIME_PROXY} history", "proxy": REGIME_PROXY}
    closes_list = ind.closes(bars)
    sma10 = ind.sma_series(closes_list, 10)
    sma20 = ind.sma_series(closes_list, 20)
    i, y = len(bars) - 1, len(bars) - 2
    if None in (sma10[i], sma20[i], sma10[y], sma20[y]):
        return {"pass": False, "reason": "insufficient SMA history", "proxy": REGIME_PROXY}
    passed = sma10[i] > sma20[i] and sma10[i] > sma10[y] and sma20[i] > sma20[y]
    return {
        "pass": passed,
        "proxy": REGIME_PROXY,
        "sma10_today": round(sma10[i], 4),
        "sma10_yesterday": round(sma10[y], 4),
        "sma20_today": round(sma20[i], 4),
        "sma20_yesterday": round(sma20[y], 4),
    }


def account_equity():
    acct = run_alpaca("account")
    return float(acct["equity"])


def load_position_symbols():
    """Symbols currently open, and symbols stopped out within the last 10
    sessions - for the Already-held / Recent-stop-out exclusions."""
    if not POSITIONS_FILE.exists():
        return set(), set()
    state = json.loads(POSITIONS_FILE.read_text())
    open_syms = set(state.get("open", {}).keys())
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=15)).isoformat()
    recent_stopouts = {
        c["symbol"] for c in state.get("closed", [])
        if c.get("exit_rule", "").startswith("stop") and c.get("exit_date", "") >= cutoff
    }
    return open_syms, recent_stopouts


def stage_a_filter(universe, equity, feed=None):
    """Section 5 price/liquidity/ADR filter, ~50-day bars, whole universe."""
    survivors = []
    rejections = []
    batch_size = 150
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i + batch_size]
        bars_map = fetch_bars_batch(batch, days=75, feed=feed)
        for sym in batch:
            bars = bars_map.get(sym, [])
            if len(bars) < 50:
                rejections.append((sym, "insufficient_history"))
                continue
            last_close = bars[-1]["c"]
            if last_close < 5.00:
                rejections.append((sym, "price_below_5"))
                continue
            dv = ind.dollar_volume_avg(bars, period=50)
            if dv is None or dv < 10_000_000 or dv < 30 * equity:
                rejections.append((sym, "dollar_volume"))
                continue
            adr = ind.adr20(bars)
            if adr is None or adr < 4.0:
                rejections.append((sym, "adr_below_4pct"))
                continue
            survivors.append(sym)
    return survivors, rejections


def stage_b_setup_scan(survivor_symbols, open_syms, recent_stopouts, feed=None):
    """Section 5 momentum percentile (population = Stage-A survivors,
    operator decision) + Section 6 setup scan + Section 7 exclusions that
    don't require today's open."""
    batch_size = 80
    full_bars = {}
    for i in range(0, len(survivor_symbols), batch_size):
        batch = survivor_symbols[i:i + batch_size]
        bars_map = fetch_bars_batch(batch, days=200, feed=feed)
        full_bars.update(bars_map)

    returns_21, returns_63, returns_126 = {}, {}, {}
    # Symbols dropped here used to hit a bare `continue` and never reach
    # `rejections`, so they vanished from the accounting Section 11
    # requires ("per rejection: symbol, first disqualifying rule"). Stage A
    # already logs the identical condition as "insufficient_history"
    # (see stage_a, ~line 219); Stage B now matches it.
    insufficient_history = []
    for sym in survivor_symbols:
        bars = full_bars.get(sym, [])
        if len(bars) < 127:
            insufficient_history.append(sym)
            continue
        r21 = ind.pct_return(bars, 21)
        r63 = ind.pct_return(bars, 63)
        r126 = ind.pct_return(bars, 126)
        if None in (r21, r63, r126):
            insufficient_history.append(sym)
            continue
        returns_21[sym], returns_63[sym], returns_126[sym] = r21, r63, r126

    pop21, pop63, pop126 = list(returns_21.values()), list(returns_63.values()), list(returns_126.values())

    candidates, rejections = [], []
    rejections.extend((sym, "insufficient_history") for sym in insufficient_history)

    for sym in returns_21:
        if sym in open_syms:
            rejections.append((sym, "already_held"))
            continue
        if sym in recent_stopouts:
            rejections.append((sym, "recent_stop_out"))
            continue

        p21 = ind.percentile_rank(returns_21[sym], pop21)
        p63 = ind.percentile_rank(returns_63[sym], pop63)
        p126 = ind.percentile_rank(returns_126[sym], pop126)
        if not (p21 >= 90 and p63 >= 90 and p126 >= 90):
            rejections.append((sym, "momentum_percentile"))
            continue

        bars = full_bars[sym]
        impulse = ind.find_prior_impulse(bars)
        if impulse is None:
            rejections.append((sym, "no_prior_impulse"))
            continue
        _l_idx, h_idx, _l_price, h_price = impulse

        today_idx = len(bars) - 1
        consolidation_len = today_idx - h_idx + 1
        if not (10 <= consolidation_len <= 40):
            rejections.append((sym, "consolidation_window"))
            continue

        ref_sma = ind.select_reference_sma(bars, h_idx, today_idx)
        if ref_sma is None:
            rejections.append((sym, "no_reference_sma"))
            continue

        closes_list = ind.closes(bars)
        ref_series = ind.sma_series(closes_list, ref_sma)
        if ref_series[today_idx] is None or ref_series[h_idx] is None:
            rejections.append((sym, "insufficient_sma_history"))
            continue
        if not (ref_series[today_idx] > ref_series[h_idx]):
            rejections.append((sym, "reference_sma_not_rising"))
            continue

        final_5 = range(max(h_idx, today_idx - 4), today_idx + 1)
        if any(ref_series[i] is not None and closes_list[i] < ref_series[i] for i in final_5):
            rejections.append((sym, "close_below_reference_sma_recently"))
            continue

        sma50_series = ind.sma_series(closes_list, 50)
        if any(
            sma50_series[i] is not None and closes_list[i] < sma50_series[i]
            for i in range(h_idx, today_idx + 1)
        ):
            rejections.append((sym, "close_below_50sma_in_consolidation"))
            continue

        seg_lows = ind.segment_min_lows(bars, h_idx, today_idx)
        if seg_lows is None or not (seg_lows[2] > seg_lows[1] > seg_lows[0]):
            rejections.append((sym, "higher_lows_failed"))
            continue

        r5, r10, r20 = ind.range_pct(bars, 5), ind.range_pct(bars, 10), ind.range_pct(bars, 20)
        if None in (r5, r10, r20) or not (r5 < r10 < r20):
            rejections.append((sym, "monotonic_contraction_failed"))
            continue

        if today_idx - 10 < 0 or ref_series[today_idx - 10] is None:
            rejections.append((sym, "insufficient_history_for_convergence"))
            continue
        conv_today = closes_list[today_idx] / ref_series[today_idx] - 1
        conv_10ago = closes_list[today_idx - 10] / ref_series[today_idx - 10] - 1
        if not (conv_today <= conv_10ago):
            rejections.append((sym, "convergence_failed"))
            continue

        yesterday_close = closes_list[today_idx]
        if not (yesterday_close >= 0.85 * h_price):
            rejections.append((sym, "too_far_below_base"))
            continue
        highest_high_consolidation = max(b["h"] for b in bars[h_idx:today_idx + 1])
        if not (highest_high_consolidation <= 1.10 * h_price):
            rejections.append((sym, "extended_beyond_base"))
            continue

        # Section 7 — Extension exclusion (the only §7 check answerable
        # with EOD-only data; Gap and sized-Liquidity are deferred to
        # market-open.md; Earnings is skipped for v1.0, known gap).
        sma10_series = ind.sma_series(closes_list, 10)
        if sma10_series[today_idx] is not None and yesterday_close > 1.10 * sma10_series[today_idx]:
            rejections.append((sym, "extension_exclusion"))
            continue

        candidates.append({
            "symbol": sym,
            "consolidation_high_ref": round(h_price, 4),
            "consolidation_start_idx": h_idx,
            "reference_sma_period": ref_sma,
            "return_63d_pct": round(returns_63[sym] * 100, 2),
            "adr_20_pct": round(ind.adr20(bars), 2),
            "last_close": round(yesterday_close, 2),
            "dollar_volume_50d_avg": round(ind.dollar_volume_avg(bars, period=50), 0),
        })

    candidates.sort(key=lambda c: c["return_63d_pct"], reverse=True)
    return candidates, rejections


def write_candidates_md(date_str, regime, universe_count, stage_a_count,
                         candidates, rejection_counts, feed_warning):
    lines = [f"\n## {date_str} — Pre-market Screener\n"]
    lines.append(f"**Regime ({regime['proxy']}):** {'PASS' if regime['pass'] else 'FAIL'}")
    if "sma10_today" in regime:
        lines.append(
            f"10 SMA: {regime['sma10_today']} (yesterday {regime['sma10_yesterday']}) | "
            f"20 SMA: {regime['sma20_today']} (yesterday {regime['sma20_yesterday']})"
        )
    else:
        lines.append(f"Reason: {regime.get('reason', 'unknown')}")
    lines.append("")
    lines.append(f"**Universe:** {universe_count} tradable common-stock candidates")
    lines.append(f"**Stage A survivors (price/liquidity/ADR):** {stage_a_count}")
    lines.append(f"**Stage B candidates (post setup-scan/exclusions):** {len(candidates)}")
    if feed_warning:
        lines.append(f"\n⚠️ {feed_warning}")
    lines.append("")

    if not regime["pass"]:
        lines.append("Regime FAIL — no new entries today regardless of candidates below.")
        lines.append("")

    if candidates:
        lines.append("| Rank | Symbol | 63d Return | ADR_20 | Last Close | Ref SMA | Consol. High |")
        lines.append("|---|---|---|---|---|---|---|")
        for i, c in enumerate(candidates, 1):
            lines.append(
                f"| {i} | {c['symbol']} | {c['return_63d_pct']}% | {c['adr_20_pct']}% | "
                f"${c['last_close']} | {c['reference_sma_period']} | ${c['consolidation_high_ref']} |"
            )
    else:
        lines.append("No candidates qualified today.")
    lines.append("")

    lines.append("**Rejection counts (first disqualifying rule):**")
    for rule, count in sorted(rejection_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {rule}: {count}")
    lines.append("")

    CANDIDATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES_FILE, "a") as f:
        f.write("\n".join(lines) + "\n")


def main():
    date_str = datetime.now(timezone.utc).date().isoformat()
    print(f"QMS-01 screener — {date_str}", file=sys.stderr)

    equity = account_equity()
    print(f"Account equity: {equity}", file=sys.stderr)

    # Free/IEX data-feed acknowledgment (operator decision — see
    # memory/TRADING-STRATEGY.md). Threshold is NOT adjusted to
    # compensate (Section 0.4 forbids parameter tuning).
    feed_warning = (
        "Dollar-volume figures use Alpaca's default (IEX) feed, which "
        "understates true consolidated market volume. The $10M / 30x-"
        "equity threshold is applied literally per Section 0.4 — not "
        "adjusted to compensate. Known limitation, not a bug."
    )
    # Alpaca's /v2/stocks/bars defaults to SIP for recent data and 403s if
    # the account isn't entitled to it. Confirmed free/IEX-tier account
    # (user-provided) -> request feed=iex explicitly everywhere. See the
    # feed_warning above for why this isn't silently "fixed" by pretending
    # it's SIP.
    feed = "iex"

    regime = check_regime(feed=feed)
    print(f"Regime: {'PASS' if regime['pass'] else 'FAIL'}", file=sys.stderr)

    universe = fetch_tradable_universe()
    print(f"Universe (post ETF/non-common-stock filter): {len(universe)} symbols", file=sys.stderr)

    open_syms, recent_stopouts = load_position_symbols()

    survivors, rejections_a = stage_a_filter(universe, equity, feed=feed)
    print(f"Stage A survivors: {len(survivors)}", file=sys.stderr)

    candidates, rejections_b = stage_b_setup_scan(survivors, open_syms, recent_stopouts, feed=feed)
    print(f"Final candidates: {len(candidates)}", file=sys.stderr)

    rejection_counts = {}
    for _sym, rule in rejections_a + rejections_b:
        rejection_counts[rule] = rejection_counts.get(rule, 0) + 1

    write_candidates_md(
        date_str, regime, len(universe), len(survivors),
        candidates if regime["pass"] else [], rejection_counts, feed_warning,
    )

    print(json.dumps({
        "date": date_str,
        "regime": regime,
        "universe_count": len(universe),
        "stage_a_count": len(survivors),
        "candidates": candidates if regime["pass"] else [],
    }, indent=2))


if __name__ == "__main__":
    main()
