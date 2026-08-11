#!/usr/bin/env python3
"""
QMS-01 Breakout v1.1-paper — historical backtest.

Replays Sections 4-10 over historical SIP data and produces the Section 11
distribution record. Read-only: it never touches memory/, never places an
order, and never imports anything that can.

WHY THIS EXISTS
Constraint #2 says the strategy has never been backtested and has no
demonstrated edge. The screen produces roughly one candidate per session,
so live paper trading would take years to accumulate enough entries to
tell signal from noise — and the defect that made the bot unusable (the
10:05 stop-limit band filling only FAILED breakouts) was invisible in
live results precisely because it produced no results.

RULE FIDELITY
Sections 5-7 are executed by importing scripts/screener.py's own
stage_a_filter and stage_b_setup_scan and injecting a bars_provider that
returns history truncated to the simulated session. The backtest and the
live screener therefore run the SAME rule code. A second implementation
of the rules would be free to drift from production, which is the exact
class of defect this repository has been fighting all along.

Section 8 (as amended 2026-08-11 (b), confirmed-hold market entry) is
implemented here against 5-minute bars, because no shared code path for
it exists yet — routines/market-open.md is an LLM prompt, not a module.
Its logic is transcribed from docs/ §8.2-8.6 and the mapping is asserted
in tests/test_backtest.py.

KNOWN BIASES — read before believing any number this produces
  * SURVIVORSHIP. The universe comes from Alpaca's CURRENT tradable asset
    list. Symbols delisted before today are absent, so historical results
    are biased upward by an unknown amount. This cannot be fixed with the
    available data and is not a small effect for a momentum strategy.
  * The Section 7 earnings exclusion is not implemented (no free data
    source) — the same known gap the live system has.
  * Section 10's sector cap is not implemented, matching live.
  * Fills are modelled at the next 5-minute bar's OPEN after the decision
    bar, with no slippage or commission. Measured drift 10:00 -> 10:20 on
    high-ADR names is 0.70% median with a mean of -0.31%, so this is
    optimistic by well under a percent per trade, but it IS optimistic.

Usage:
  python3 scripts/backtest.py --start 2025-01-01 --end 2026-06-30
  python3 scripts/backtest.py --start 2025-01-01 --end 2025-03-31 \
      --universe-limit 400 --out /tmp/bt.json
"""

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent))
import indicators as ind          # noqa: E402
import screener                    # noqa: E402  (rule code, reused verbatim)

ROOT = Path(__file__).resolve().parent.parent
ALPACA_SH = ROOT / "scripts" / "alpaca.sh"
CACHE = ROOT / ".backtest-cache"

# Section 14 parameters. Read, never tuned — a backtest that adjusts these
# to improve its own output is curve fitting, which Constraint #4 forbids.
RISK_PER_TRADE = 0.005
MAX_POSITION_FRAC = 0.20
MAX_CONCURRENT = 5
MAX_NEW_PER_DAY = 2
MAX_TOTAL_RISK_PCT = 3.0
RISK_OVERRUN_TRIP = 0.0075
STARTING_EQUITY = 100_000.0


# ---------------------------------------------------------------- data


def alpaca_bars(qs):
    r = subprocess.run(["bash", str(ALPACA_SH), "bars", qs],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"bars failed: {r.stderr.strip()[:400]}")
    return json.loads(r.stdout)


def fetch_daily_history(symbols, start, end):
    """Bulk daily bars for the whole backtest window, fetched ONCE and
    cached on disk. Per-session re-fetching would be thousands of calls
    for identical data."""
    CACHE.mkdir(exist_ok=True)
    key = CACHE / f"daily_{start}_{end}_{len(symbols)}.json"
    if key.exists():
        print(f"  cache hit: {key.name}", file=sys.stderr)
        return json.loads(key.read_text())

    out = {}
    B = 100
    for i in range(0, len(symbols), B):
        batch = symbols[i:i + B]
        tok = None
        while True:
            qs = (f"symbols={','.join(batch)}&timeframe=1Day&start={start}"
                  f"&end={end}&limit=10000&adjustment=split&feed=sip")
            if tok:
                qs += f"&page_token={tok}"
            d = alpaca_bars(qs)
            for s, bars in (d.get("bars") or {}).items():
                out.setdefault(s, []).extend(bars)
            tok = d.get("next_page_token")
            if not tok:
                break
        print(f"  daily {i + len(batch)}/{len(symbols)}", file=sys.stderr)
    for s in out:
        out[s].sort(key=lambda b: b["t"])
    key.write_text(json.dumps(out))
    return out


def fetch_opening_range(symbol, day):
    """5-minute bars 09:30-10:00 ET for one symbol-day. Only called for
    actual candidates, so volume stays low."""
    CACHE.mkdir(exist_ok=True)
    key = CACHE / f"or_{symbol}_{day}.json"
    if key.exists():
        return json.loads(key.read_text())
    # 09:30 ET = 13:30Z (EDT) / 14:30Z (EST). Ask for a superset and filter.
    qs = (f"symbols={symbol}&timeframe=5Min&start={day}T13:00:00Z"
          f"&end={day}T16:00:00Z&limit=100&feed=sip")
    try:
        d = alpaca_bars(qs)
        bars = (d.get("bars") or {}).get(symbol, [])
    except RuntimeError:
        bars = []
    key.write_text(json.dumps(bars))
    return bars


def et_hhmm(bar, is_edt):
    """Bar timestamp as ET HH:MM. Alpaca stamps bars in UTC."""
    t = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
    t -= timedelta(hours=4 if is_edt else 5)
    return t.strftime("%H:%M")


def is_edt(day):
    """US DST: 2nd Sunday March -> 1st Sunday November. Good enough for
    bar alignment; a wrong call shifts the window an hour and shows up
    immediately as a missing 09:30 bar, which the caller skips."""
    y, m, d = map(int, day.split("-"))
    return 3 < m < 11 or (m == 3 and d >= 8) or (m == 11 and d <= 7)


# ------------------------------------------------------- Section 8


def evaluate_section8(bars, day, adr20_pct, dollar_vol_50d, equity,
                      open_risk_pct, log):
    """Sections 8.2-8.4 as amended 2026-08-11 (b): confirmed-hold market
    entry. Returns an entry dict or None, and appends a reason to `log`.

    Mirrors docs/ §8 exactly:
      ORH            = high of the 09:30-09:35 bar
      BREAKOUT       = some 09:35-10:00 bar closed above ORH
      HOLDING        = the 09:55-10:00 bar closed above ORH
      decision_price = close of that final bar
      session_low    = lowest low across 09:30-10:00
    """
    edt = is_edt(day)
    win = {}
    for b in bars:
        hhmm = et_hhmm(b, edt)
        if "09:30" <= hhmm <= "09:55":
            win[hhmm] = b
    first, final = win.get("09:30"), win.get("09:55")
    if not first or not final:
        log.append("incomplete_window")
        return None

    orh = first["h"]
    session_low = min(b["l"] for b in win.values())
    decision_price = final["c"]

    # §8.2 BREAKOUT
    if not any(b["c"] > orh for k, b in win.items() if k >= "09:35"):
        log.append("no_breakout")
        return None
    # §8.2 HOLDING — the case the retired stop-limit rule used to BUY
    if not decision_price > orh:
        log.append("breakout_faded")
        return None

    # §8.3 pre-trade sizing
    est_risk = decision_price - session_low
    if est_risk <= 0:
        log.append("INVALID_RISK")
        return None
    if est_risk > (adr20_pct / 100.0) * decision_price:
        log.append("STOP_TOO_WIDE_PRETRADE")
        return None

    qty = int(math.floor((equity * RISK_PER_TRADE) / est_risk))
    qty = min(qty, int(math.floor((equity * MAX_POSITION_FRAC) / decision_price)))
    if qty < 1:
        log.append("shares_below_1")
        return None

    # §10 portfolio pre-check
    if open_risk_pct + (est_risk * qty / equity * 100) > MAX_TOTAL_RISK_PCT:
        log.append("portfolio_risk_breach")
        return None
    # §7 liquidity
    if dollar_vol_50d and (qty * decision_price) > 0.01 * dollar_vol_50d:
        log.append("liquidity_exclusion")
        return None

    return {"orh": orh, "session_low": session_low,
            "decision_price": decision_price, "qty": qty,
            "est_risk_share": est_risk}


# ------------------------------------------------------------ engine


def run(start, end, universe_limit, out_path):
    print("Fetching universe...", file=sys.stderr)
    universe = screener.fetch_tradable_universe()
    if universe_limit:
        universe = universe[:universe_limit]
    print(f"  {len(universe)} symbols", file=sys.stderr)

    hist_start = (datetime.fromisoformat(start) - timedelta(days=400)).date().isoformat()
    print(f"Fetching daily history {hist_start} -> {end}...", file=sys.stderr)
    # REGIME_PROXY must be fetched EXPLICITLY. ONEQ is an ETF, and
    # fetch_tradable_universe() strips ETFs by name for Section 5 — so the
    # proxy is never in `universe`. Without this the regime check reads an
    # empty bar list and fails every single session, silently producing a
    # zero-trade backtest that looks like "the strategy never qualified"
    # rather than "the harness never fetched the index".
    fetch_syms = list(dict.fromkeys(universe + [screener.REGIME_PROXY]))
    daily = fetch_daily_history(fetch_syms, hist_start, end)
    if not daily.get(screener.REGIME_PROXY):
        raise RuntimeError(
            f"No bars for regime proxy {screener.REGIME_PROXY}. Section 4 "
            "cannot be evaluated; refusing to report a zero-trade result "
            "that would be indistinguishable from a real one."
        )

    sessions = sorted({b["t"][:10] for bars in daily.values() for b in bars})
    sessions = [d for d in sessions if start <= d <= end]
    print(f"  {len(sessions)} sessions to replay", file=sys.stderr)

    equity = STARTING_EQUITY
    peak = equity
    open_pos, closed, rejects = {}, [], {}
    regime_pass_days = 0

    for si, day in enumerate(sessions):
        # ---- bars provider: history strictly BEFORE `day` (no lookahead)
        def provider(syms, days, _day=day):
            return {s: [b for b in daily.get(s, []) if b["t"][:10] < _day][-days:]
                    for s in syms}

        # ---- §4 regime, on the proxy
        proxy = provider([screener.REGIME_PROXY], 45).get(screener.REGIME_PROXY, [])
        closes = [b["c"] for b in proxy]
        s10, s20 = ind.sma(closes, 10), ind.sma(closes, 20)
        s10p, s20p = ind.sma(closes, 10, len(closes) - 2), ind.sma(closes, 20, len(closes) - 2)
        regime = all(v is not None for v in (s10, s20, s10p, s20p)) and \
            s10 > s20 and s10 > s10p and s20 > s20p
        if regime:
            regime_pass_days += 1

        # ---- §9 manage existing positions on TODAY's completed bar
        for sym in list(open_pos):
            p = open_pos[sym]
            todays = [b for b in daily.get(sym, []) if b["t"][:10] == day]
            if not todays:
                continue
            bar = todays[0]
            if bar["l"] <= p["stop"]:                        # §9.1 stop hit
                exit_px = min(bar["o"], p["stop"])
                _close(p, sym, exit_px, day, "stop", closed, open_pos)
                equity += (exit_px - p["fill"]) * p["shares_remaining"]
                continue
            p["sessions_held"] += 1
            hist = [b for b in daily.get(sym, []) if b["t"][:10] <= day]
            if p["sessions_held"] == 4 and not p["partial"] and bar["c"] > p["fill"]:
                q = p["shares"] // 3                          # §9.2
                if q:
                    equity += (bar["c"] - p["fill"]) * q
                    p["shares_remaining"] -= q
                    p["partial"] = True
                    p["realized"] += (bar["c"] - p["fill"]) * q
                    p["stop"] = max(p["stop"], p["fill"] - 0.5 * p["risk"])   # §9.3
            elif p["partial"]:                                # §9.4 trailing
                sma10 = ind.sma([b["c"] for b in hist], 10)
                if sma10 and bar["c"] < sma10:
                    _close(p, sym, bar["c"], day, "sma_trail", closed, open_pos)
                    equity += (bar["c"] - p["fill"]) * p["shares_remaining"]

        peak = max(peak, equity)
        if (peak - equity) / peak * 100 >= 25.0:              # §12
            print(f"  HALT: 25% drawdown on {day}", file=sys.stderr)
            break
        if not regime or len(open_pos) >= MAX_CONCURRENT:
            continue

        # ---- §5-§7 screen, running the LIVE screener's own code
        try:
            survivors, rej_a = screener.stage_a_filter(
                universe, equity, bars_provider=provider)
            cands, rej_b = screener.stage_b_setup_scan(
                survivors, set(open_pos), set(), bars_provider=provider)
        except Exception as e:                                 # noqa: BLE001
            print(f"  {day}: screen error {e}", file=sys.stderr)
            continue
        for _s, r in list(rej_a) + list(rej_b):
            rejects[r] = rejects.get(r, 0) + 1
        if not cands:
            continue

        # ---- §8 entries
        open_risk = sum(p["risk"] * p["shares_remaining"] for p in open_pos.values()) / equity * 100
        entries_today = 0
        for c in cands:
            if entries_today >= MAX_NEW_PER_DAY or len(open_pos) >= MAX_CONCURRENT:
                break
            sym = c["symbol"]
            if sym in open_pos:
                continue
            log = []
            e = evaluate_section8(fetch_opening_range(sym, day), day,
                                  c["adr_20_pct"], c.get("dollar_volume_50d_avg"),
                                  equity, open_risk, log)
            for r in log:
                rejects[r] = rejects.get(r, 0) + 1
            if not e:
                continue
            fill = e["decision_price"]      # modelled: next-bar open ~= decision close
            actual_risk = fill - e["session_low"]
            if (e["qty"] * actual_risk) / equity > RISK_OVERRUN_TRIP:   # §8.6
                rejects["RISK_OVERRUN"] = rejects.get("RISK_OVERRUN", 0) + 1
                continue
            open_pos[sym] = {"fill": fill, "stop": e["session_low"],
                             "risk": actual_risk, "shares": e["qty"],
                             "shares_remaining": e["qty"], "partial": False,
                             "sessions_held": 0, "entry_date": day, "realized": 0.0}
            open_risk += actual_risk * e["qty"] / equity * 100
            entries_today += 1

        if si % 25 == 0:
            print(f"  {day}  equity {equity:,.0f}  open {len(open_pos)}  "
                  f"closed {len(closed)}", file=sys.stderr)

    return _report(equity, peak, closed, open_pos, rejects,
                   len(sessions), regime_pass_days, out_path)


def _close(p, sym, px, day, rule, closed, open_pos):
    p["realized"] += (px - p["fill"]) * p["shares_remaining"]
    closed.append({"symbol": sym, "entry_date": p["entry_date"], "exit_date": day,
                   "fill": p["fill"], "exit": px, "exit_rule": rule,
                   "r_multiple": (px - p["fill"]) / p["risk"] if p["risk"] else 0.0,
                   "realized": p["realized"], "days_held": p["sessions_held"]})
    del open_pos[sym]


def _report(equity, peak, closed, open_pos, rejects, n_sessions,
            regime_days, out_path):
    rs = [t["r_multiple"] for t in closed]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    profits = [t["realized"] for t in closed if t["realized"] > 0]
    best = max(profits) if profits else 0.0

    rep = {
        "sessions": n_sessions,
        "regime_pass_sessions": regime_days,
        "final_equity": round(equity, 2),
        "return_pct": round((equity / STARTING_EQUITY - 1) * 100, 2),
        "peak_equity": round(peak, 2),
        "max_drawdown_pct": round((peak - equity) / peak * 100, 2) if peak else 0.0,
        "trades_closed": len(closed),
        "trades_still_open": len(open_pos),
        # Section 11 distribution record
        "win_rate_pct": round(len(wins) / len(rs) * 100, 1) if rs else None,
        "avg_winning_r": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_losing_r": round(sum(losses) / len(losses), 2) if losses else None,
        "largest_winning_r": round(max(rs), 2) if rs else None,
        "pct_profit_from_best_trade": round(best / sum(profits) * 100, 1) if profits else None,
        "rejection_counts": dict(sorted(rejects.items(), key=lambda x: (-x[1], x[0]))),
        "trades": closed,
        "BIASES": [
            "Survivorship: universe is TODAY's tradable list; delisted "
            "symbols are absent. Results are biased upward by an unknown "
            "and probably material amount for a momentum strategy.",
            "No earnings exclusion (Section 7) — same gap as live.",
            "No sector cap (Section 10) — same as live.",
            "Fills modelled at the decision-bar close, no slippage or "
            "commission. Optimistic by well under 1% per trade.",
        ],
    }
    Path(out_path).write_text(json.dumps(rep, indent=2))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--universe-limit", type=int, default=0)
    ap.add_argument("--out", default="/tmp/qms01-backtest.json")
    a = ap.parse_args()

    rep = run(a.start, a.end, a.universe_limit, a.out)

    print("\n" + "=" * 62)
    print(f"QMS-01 backtest  {a.start} -> {a.end}")
    print("=" * 62)
    for k in ("sessions", "regime_pass_sessions", "trades_closed",
              "trades_still_open", "final_equity", "return_pct",
              "max_drawdown_pct", "win_rate_pct", "avg_winning_r",
              "avg_losing_r", "largest_winning_r",
              "pct_profit_from_best_trade"):
        print(f"  {k:<28} {rep[k]}")
    print("\n  top rejection reasons:")
    for r, n in list(rep["rejection_counts"].items())[:12]:
        print(f"    {r:<26} {n}")
    print(f"\n  full report -> {a.out}")
    print("\n  READ THE BIASES BLOCK IN THE REPORT BEFORE BELIEVING ANY OF THIS.")


if __name__ == "__main__":
    main()
