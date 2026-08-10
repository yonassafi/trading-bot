#!/usr/bin/env python3
"""
QMS-01 Breakout v1.1-paper — Section 9 position management.

Run once daily, after the close (routines/daily-summary.md), for every
symbol currently open in memory/POSITIONS.json. Applies 9.1-9.4 in order.
No time stop (9.6). No earnings rule (9.5 skipped for v1.0 - no data
source, see memory/TRADING-STRATEGY.md known gaps).

This script does NOT place orders. It reads state, computes what SHOULD
happen today per each position, and prints a JSON action list. The
calling routine (an LLM agent following routines/daily-summary.md's
steps) executes each action via scripts/alpaca.sh — which carries the
require_paper() safety guard — and is responsible for recording realized
fills into memory/POSITIONS.json's "closed" list and memory/TRADE-LOG.md.

Section 9.1 (resting stop): the protective stop is a real broker-side
stop-market order placed at entry (routines/market-open.md). Alpaca
itself handles "gap below stop -> exit at market" with zero intraday
polling from this system. This script's role for 9.1 is reconciliation
only: if a symbol in POSITIONS.json's "open" no longer appears in
`scripts/alpaca.sh positions`, its stop (or a manual exit) already
filled — the calling routine must detect and record that BEFORE calling
this script, so an already-closed position isn't evaluated as if still
open.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
import indicators as ind  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALPACA_SH = ROOT / "scripts" / "alpaca.sh"
POSITIONS_FILE = ROOT / "memory" / "POSITIONS.json"


def run_alpaca(*args):
    result = subprocess.run(
        ["bash", str(ALPACA_SH), *args],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alpaca.sh {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def load_positions():
    if not POSITIONS_FILE.exists():
        return {"open": {}, "closed": []}
    return json.loads(POSITIONS_FILE.read_text())


def save_positions(state):
    POSITIONS_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def fetch_daily_bars(symbol, days=15):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    # feed=iex: confirmed free/IEX-tier Alpaca account — SIP (the
    # unqualified default) 403s. See scripts/screener.py for the same note.
    qs = f"symbols={symbol}&timeframe=1Day&start={start}&end={end}&limit=100&feed=iex"
    resp = run_alpaca("bars", qs)
    bars = resp.get("bars", {}).get(symbol, []) or []
    bars.sort(key=lambda b: b["t"])
    return bars


def manage_position(symbol, pos, bars):
    """Apply Section 9.2-9.4 in order (9.1 is reconciliation, handled by
    the caller before this runs). Returns (actions, updated_pos, log)."""
    actions = []
    log = {"symbol": symbol}

    if not bars:
        log["exception"] = "UNSPECIFIED_SITUATION: no bar data returned for open position"
        return actions, pos, log

    today = bars[-1]
    close = today["c"]
    log["close"] = close

    pos["sessions_held"] = pos.get("sessions_held", 0) + 1
    log["sessions_held"] = pos["sessions_held"]

    # 9.2 — first partial: exactly session 4, and at a profit.
    if pos["sessions_held"] == 4 and not pos.get("partial_taken") and close > pos["fill_price"]:
        qty = pos["shares"] // 3
        if qty > 0:
            actions.append({"type": "partial_sell", "symbol": symbol, "qty": qty})
            pos["shares_remaining"] = pos["shares"] - qty
            pos["partial_taken"] = True
            log["partial_sell_qty"] = qty

            # 9.3 — stop after partial: max(original, fill - 0.5*risk).
            # Deliberately NOT break-even — see memory/TRADING-STRATEGY.md
            # Section 13 (largest deviation from the source strategy).
            half_risk_stop = pos["fill_price"] - 0.5 * pos["risk_per_share"]
            new_stop = max(pos["initial_stop"], half_risk_stop)
            if new_stop > pos["current_stop"]:
                actions.append({
                    "type": "replace_stop", "symbol": symbol,
                    "qty": pos["shares_remaining"], "new_stop": round(new_stop, 2),
                })
                pos["current_stop"] = new_stop
                log["new_stop"] = round(new_stop, 2)
    elif pos["sessions_held"] == 4 and not pos.get("partial_taken"):
        log["note"] = "session 4 reached but not at a profit — no partial per §9.2"

    # 9.4 — trailing exit: after partial taken, a CLOSE below the
    # position's reference SMA exits the remainder. Never an intraday
    # touch.
    if pos.get("partial_taken") and pos.get("shares_remaining", 0) > 0:
        period = pos["reference_sma_period"]
        closes_list = ind.closes(bars)
        sma_val = ind.sma(closes_list, period)
        if sma_val is None:
            log["exception"] = f"UNSPECIFIED_SITUATION: insufficient history for {period}-SMA trailing check"
        elif close < sma_val:
            actions.append({
                "type": "full_exit", "symbol": symbol,
                "qty": pos["shares_remaining"], "reason": "trailing_sma",
            })
            log["exit_reason"] = "trailing_sma"
            log["exit_reference_sma"] = round(sma_val, 4)

    return actions, pos, log


def main():
    state = load_positions()
    all_actions = []
    logs = []

    for symbol, pos in list(state["open"].items()):
        bars = fetch_daily_bars(symbol)
        actions, updated_pos, log = manage_position(symbol, dict(pos), bars)
        state["open"][symbol] = updated_pos
        all_actions.extend(actions)
        logs.append(log)

    save_positions(state)
    print(json.dumps({"actions": all_actions, "logs": logs}, indent=2))


if __name__ == "__main__":
    main()
