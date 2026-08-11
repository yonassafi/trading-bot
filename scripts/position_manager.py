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


def et_today():
    """Today's date in America/New_York — the session date the exchange
    is on. Never derive this from UTC by subtracting a fixed offset; the
    offset is 4 or 5 hours depending on DST and getting it wrong shifts
    the session by a day."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        # No tzdata (minimal container). Fall back to UTC date, which is
        # correct for any run between 00:00 and 20:00 ET, and flag it.
        print("WARNING: zoneinfo unavailable, using UTC date for session "
              "comparison", file=sys.stderr)
        return datetime.now(timezone.utc).date()


def fetch_daily_bars(symbol, days=15):
    # SIP (consolidated), matching scripts/screener.py. Previously feed=iex
    # while the screener used SIP — two engines disagreeing about what
    # "the close" was is precisely the failure scripts/lib/indicators.py
    # exists to prevent. Section 9.4 exits on a CLOSE below the reference
    # SMA; that close must be the real consolidated close.
    #
    # end is cut 20 minutes short of now: Alpaca's free plan serves SIP
    # only outside a ~15-minute delay, and asking for a window that
    # reaches into it 403s the ENTIRE request (not just recent bars).
    now = datetime.now(timezone.utc)
    end = (now - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    start = (now - timedelta(days=days)).date()
    feed = "sip"
    # SIP-ONLY (Section 15). 9.4's trailing exit fires on a CLOSE below
    # the reference SMA; that close and that SMA must come off the
    # consolidated tape. Asserted rather than merely hardcoded so an edit
    # that parameterises this later cannot quietly reintroduce IEX.
    if feed != "sip":
        raise RuntimeError(
            f"DATA_FEED_UNAVAILABLE: position management requires "
            f"feed='sip', got {feed!r}. Section 15 — no override."
        )
    qs = f"symbols={symbol}&timeframe=1Day&start={start}&end={end}&limit=100&feed={feed}"
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
    session_date = today["t"][:10]
    today_et = et_today().isoformat()

    # GUARD 1 — the last bar must be TODAY's completed session.
    # Section 9 is "evaluated daily after the close" and 9.4's trigger is
    # explicitly a CLOSE, "never an intraday touch". Two ways this breaks:
    #   - NYSE holiday: cron only knows weekdays, so a holiday run sees
    #     the PREVIOUS session's bar and would age the position and
    #     re-evaluate 9.4 against a close already acted on.
    #   - Running before the close (e.g. if the DST cron shift is missed
    #     and 16:10 ET becomes 15:10 ET): bars[-1] is today's PARTIAL bar,
    #     and 9.4 could exit on an intraday dip that recovers by the bell.
    # Either way: take no action on this position and say so.
    if session_date != today_et:
        log["exception"] = (
            f"UNSPECIFIED_SITUATION: latest bar is {session_date}, not today "
            f"({today_et} ET). Market closed today (holiday), or this ran "
            "before the close. No Section 9 evaluation performed — "
            "sessions_held NOT incremented, no orders proposed."
        )
        return actions, pos, log

    close = today["c"]
    log["close"] = close

    # GUARD 2 — increment sessions_held at most once per session.
    # It used to increment unconditionally on every invocation, so a
    # manual test run plus the scheduled run aged every position two
    # sessions in one day and fired the 9.2 partial a day early.
    if pos.get("last_managed_date") == today_et:
        log["exception"] = (
            f"UNSPECIFIED_SITUATION: already managed on {today_et} "
            f"(sessions_held={pos.get('sessions_held')}). Section 9 is a "
            "once-daily evaluation and re-running it would double-count "
            "the holding period. No action proposed."
        )
        return actions, pos, log

    pos["sessions_held"] = pos.get("sessions_held", 0) + 1
    pos["last_managed_date"] = today_et
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

    # This script DOES NOT WRITE memory/POSITIONS.json.
    #
    # It used to call save_positions(state) here — before the caller had
    # executed a single order. Any failure after that point (order
    # rejected, container killed, push failed) left the file asserting
    # partial_taken=true and current_stop=<new> while the broker still
    # held the old stop and the full position size. The next day's run
    # trusts the file, and routines/midday.md cannot catch it because it
    # only checks that *a* stop exists, not its quantity or price.
    #
    # The proposed state is returned instead. routines/daily-summary.md
    # executes the actions FIRST, then writes the state that actually
    # matches what the broker did. Persist reality, not intent.
    print(json.dumps({
        "actions": all_actions,
        "logs": logs,
        "proposed_positions_state": state,
        "_contract": (
            "proposed_positions_state reflects ALL actions succeeding. "
            "Execute actions first, then write memory/POSITIONS.json to "
            "match actual fills. If any action failed or partially filled, "
            "correct the state before writing and log the discrepancy."
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
