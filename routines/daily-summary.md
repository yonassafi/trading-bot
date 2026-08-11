You are running QMS-01 Breakout v1.1-paper on a PAPER-only Alpaca
account. This strategy has never been backtested. You may not invent,
infer, or derive rules — if something isn't covered by
memory/TRADING-STRATEGY.md, take no action and log UNSPECIFIED_SITUATION.

You are running the END-OF-DAY workflow: reconciliation, Section 9
position management, drawdown/halt check, and the daily summary. Fires
at 16:30 ET, after the close.

The 16:30 slot (moved from 16:10 on 2026-08-11) is load-bearing:
scripts/position_manager.py reads SIP bars and Alpaca's free plan only
serves SIP outside a ~15-minute delay, so it requests data up to
now-20min. At 16:10 ET that cutoff is 15:50 — before the close — and
today's daily bar would not exist, so its "latest bar must be today"
guard would block ALL position management, every day. Section 9 says
"evaluated daily after the close" and pins no clock time, so this is a
deployment setting, not a strategy parameter.
Resolve today's date via: DATE=$(date +%Y-%m-%d).

IMPORTANT — ENVIRONMENT VARIABLES:
- ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_ENDPOINT, ALPACA_DATA_ENDPOINT,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID are ALREADY exported.
- There is NO .env file and you MUST NOT create, write, or source one.
- Verify env vars BEFORE any wrapper call (same pattern as pre-market.md).

IMPORTANT — PERSISTENCE:
- Fresh clone. File changes VANISH unless committed and pushed. MUST
  commit and push at STEP 8 — mandatory, no exceptions (tomorrow's Day
  P&L and the peak-equity/drawdown check both depend on this persisting).

STEP 1 — Halt check:
  bash scripts/halt.sh check
If non-zero: Telegram alert with the reason, then STOP — but note Section
12 says "close nothing" on a halt, so even if halted, do NOT skip the
read-only EOD snapshot/notification if you can still produce one safely;
just do not touch orders or memory/POSITIONS.json.

STEP 2 — Pull live state:
  bash scripts/alpaca.sh account
  bash scripts/alpaca.sh positions
  bash scripts/alpaca.sh orders "closed"

STEP 3 — Reconciliation (Section 9.1). Compare memory/POSITIONS.json
"open" against the live positions from STEP 2. For any symbol present in
POSITIONS.json but no longer an open Alpaca position: its resting stop
(or a STOP_TOO_WIDE emergency exit from market-open) already filled.
Find the filled sell order for that symbol in the closed-orders list,
get its actual fill price and time. Compute:
  r_multiple = (exit_price - fill_price) / risk_per_share
  days_held = sessions_held at time of exit
Move it from "open" to "closed" in memory/POSITIONS.json with
exit_rule: "stop" (or "stop_too_wide" if you can tell from context/logs
that's what happened). Append the exit to memory/TRADE-LOG.md per that
file's format. If you cannot find a matching filled order for a symbol
that's missing from live positions, that's an UNSPECIFIED_SITUATION —
log it, do not guess the exit price.

STEP 3b — REVERSE RECONCILIATION (orphans). STEP 3 only handles "in
POSITIONS.json but gone at the broker". The opposite direction has no
rule anywhere, and it is the exact state produced by market-open dying
between a fill and its commit — orders exist at Alpaca, the file that
records them never landed.

  (i) LIVE POSITION NOT IN THE FILE. For every symbol in
      `alpaca.sh positions` with no entry in memory/POSITIONS.json
      "open": log UNSPECIFIED_SITUATION naming the symbol, quantity,
      average entry price, and whether a resting stop exists for it.
      Send a Telegram alert. Do NOT invent a position record (you cannot
      know its ORH, initial stop, risk_per_share or reference SMA, and
      guessing them would corrupt every downstream r_multiple and the
      Section 11 distribution record). Do NOT exit it either — Section
      12 says "close nothing". Report and leave it.

  (ii) ORPHANED OR MISMATCHED RESTING STOP. Cross-check every open
      sell-stop order in `alpaca.sh orders` against POSITIONS.json:
        - a stop whose symbol has NO open position at all
        - a stop whose qty EXCEEDS the position's shares_remaining
      Either one will go SHORT when it triggers, which Binding
      Constraint #6 (long only) forbids. Log UNSPECIFIED_SITUATION with
      the order id, symbol, stop qty and the position's actual
      shares_remaining, and send a Telegram alert naming it explicitly
      as a long-only breach risk.
      Do NOT cancel it on your own initiative — no rule authorises that,
      and an unprotected position is its own hazard. This is a genuine
      gap in the spec: escalate it, do not resolve it.

STEP 4 — Run Section 9.2-9.4 position management on whatever remains open:
  python3 scripts/position_manager.py
It prints JSON with three keys:
  "actions"  — partial_sell / replace_stop / full_exit per position
  "logs"     — per-symbol reasoning, including any exception
  "proposed_positions_state" — what memory/POSITIONS.json SHOULD look
     like assuming every action succeeds

IMPORTANT: this script does NOT execute orders and does NOT write
memory/POSITIONS.json. It used to write the file before any order had
been placed, so a rejection or crash afterwards left the file claiming
partial_taken=true and a raised stop while the broker still held the old
stop and full size — and the next day's run trusted the file.
YOU write memory/POSITIONS.json, in STEP 5b, AFTER executing.

If a "logs" entry carries an "exception", that position was NOT
evaluated (stale/holiday bar, or already managed today). Take no action
on it and carry the exception into memory/EXCEPTIONS-LOG.md.

STEP 5 — Execute each action from STEP 4's output, in the order given,
via scripts/alpaca.sh:
- partial_sell: market sell the given qty
  (bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"N","side":"sell","type":"market","time_in_force":"day","client_order_id":"qms01-<DATE>-<SYM>-partial"}')
- replace_stop: cancel the existing resting stop order for that symbol
  (bash scripts/alpaca.sh cancel ORDER_ID), then place a new stop-market
  order at new_stop for the remaining shares
  (bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"N","side":"sell","type":"stop","stop_price":"X.XX","time_in_force":"gtc","client_order_id":"qms01-<DATE>-<SYM>-stop2"}')
  ORDER MATTERS: cancel the old stop BEFORE placing the new one. Two
  live stops on the same shares would sell twice — short, per Constraint
  #6 — if both trigger. If the cancel fails, do NOT place the new stop:
  log UNSPECIFIED_SITUATION and leave the existing stop in place.
- full_exit: market sell the remaining shares, then compute r_multiple
  and days_held using the actual fill price, move the position from
  "open" to "closed" in memory/POSITIONS.json (exit_rule from the
  action's "reason" field), append the exit to memory/TRADE-LOG.md.
Every order needs a deterministic client_order_id — scripts/alpaca.sh
refuses one without it. Use:
  qms01-<DATE>-<SYM>-partial   for a 9.2 partial_sell
  qms01-<DATE>-<SYM>-stop2     for a 9.3 replacement stop
  qms01-<DATE>-<SYM>-exit      for a 9.4 full_exit
This makes a duplicate from a retry structurally impossible; a duplicate
sell could take the position short, which Binding Constraint #6 forbids.

If any order is rejected for a reason you don't understand: log
UNSPECIFIED_SITUATION, do not retry with different parameters, do not
guess — this may itself be a Section 12 halt condition ("any order
rejected for a reason not understood"). scripts/alpaca.sh now prints
Alpaca's actual rejection body to stderr, so read it before concluding
the reason is not understood — most rejections are self-explanatory.

STEP 5b — WRITE memory/POSITIONS.json (after executing, not before).
Start from STEP 4's "proposed_positions_state" and correct it to match
what ACTUALLY happened:
- an action that was rejected or failed -> revert that position's
  changed fields to their pre-run values and log the discrepancy
- a partial_sell that filled short -> shares_remaining reflects the
  ACTUAL filled quantity, not the requested one
- a full_exit that filled -> move the position to "closed" with the real
  exit price
Persist reality, never intent. If you cannot determine what actually
happened for a symbol, log UNSPECIFIED_SITUATION and leave that
position's state untouched.

STEP 6 — Peak-equity / drawdown check (Section 12). Read
memory/RISK-STATE.json. Using today's final equity from STEP 2:
  IF today_equity > peak_equity: update peak_equity = today_equity,
    peak_equity_date = DATE
  current_drawdown_pct = (peak_equity - today_equity) / peak_equity * 100
  Update last_updated_date = DATE. Write memory/RISK-STATE.json.
  IF current_drawdown_pct >= 25.0:
    Write memory/HALT.md with reason "25% drawdown from peak equity
    ($peak_equity on $peak_equity_date -> $today_equity on $DATE)",
    timestamp, and this routine's name. Commit and push immediately.
    Send one Telegram alert. This is Section 12 — close nothing, just
    stop taking new actions from this point forward in future runs.

STEP 7 — Compute and append the EOD snapshot to memory/TRADE-LOG.md per
that file's format:
  Day P&L = today_equity - yesterday's EOD equity (from TRADE-LOG.md tail)
  Phase P&L = today_equity - memory/RISK-STATE.json's starting_equity
    (read it from the file — do NOT assume a value. The account is
    funded at 100000, not 10000; an earlier revision of this line
    carried a wrong hardcoded figure.)
  Open positions count, total open risk % of equity
  Entries today (from STEP 5 / market-open's log), trades this week
  fill_ratio for today's entry ATTEMPTS (Section 11) — read
    intended_qty / filled_qty / fill_ratio from today's market-open
    entries in memory/TRADE-LOG.md, including attempts that ended
    NO_FILL or PRICE_RAN_AWAY. A persistently low fill ratio means the
    stop-limit band is rarely being caught and is worth reporting, not
    acting on.

Send ONE Telegram message, always, even on no-action days, <= 15 lines:
  bash scripts/telegram.sh "EOD MMM DD
  Equity: \$X (±X% day, ±X% phase)
  Regime: PASS/FAIL | Open positions: N/5 | Open risk: X.X%
  Today: <entries/exits or 'no action'>
  Drawdown from peak: X.X%
  <one-line note if anything exceptional was logged>"

STEP 8 — COMMIT AND PUSH (mandatory, no exceptions):
  # CRITICAL: memory/RISK-STATE.json carries peak equity, which the
  # 25%-drawdown halt check depends on. Losing this push means tomorrow's
  # Section 12 check runs against a stale peak.
  # The container's clone can land on a DETACHED HEAD, where a commit
  # sits on no branch and the push is rejected with "a pushed branch tip
  # is behind its remote counterpart". `git pull --rebase` does NOT fix
  # this — it reports "up to date" and the next push fails identically.
  # Re-attach FIRST (harmless no-op if already on main):
  git checkout -B main HEAD
  git add memory/TRADE-LOG.md memory/POSITIONS.json memory/RISK-STATE.json memory/EXCEPTIONS-LOG.md
  git commit -m "EOD reconciliation + summary $DATE"
  git push origin main
  # Verify it actually landed — these MUST match:
  git fetch origin && git rev-parse HEAD origin/main
If the two hashes differ the push did NOT land: send a Telegram alert
saying so explicitly and include the equity figure and any position
state changes, so they can be reconstructed by hand. On push failure:
git pull --rebase origin main, then push again. Never force-push.

CONFLICT DURING `git pull --rebase` — do NOT improvise inside the
compliance record. The prompts previously said only "pull --rebase, then
push again", which leaves an agent resolving a conflict by judgement in
exactly the files that are meant to be evidence.

- memory/EXCEPTIONS-LOG.md, memory/TRADE-LOG.md, memory/CANDIDATES.md
  and memory/WEEKLY-REVIEW.md are APPEND-ONLY. A conflict there means
  another run appended too. Keep BOTH sides, in chronological order.
  Never drop, reword or overwrite another run's entry.

- memory/POSITIONS.json and memory/RISK-STATE.json are STATE, not logs.
  A conflict means two runs disagree about live positions or peak
  equity, and no rule resolves that. STOP: do not merge, do not
  force-push, leave origin/main untouched. Log UNSPECIFIED_SITUATION
  quoting BOTH versions, send one Telegram alert, and end the run
  reporting that the push did not land. A wrong merge here silently
  corrupts position state and the drawdown baseline that Section 12's
  halt check depends on.
