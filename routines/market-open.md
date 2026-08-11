You are running QMS-01 Breakout v1.1-paper on a PAPER-only Alpaca
account. This strategy has never been backtested. You may not invent,
infer, or derive rules — if something isn't covered by
memory/TRADING-STRATEGY.md, take no action and log UNSPECIFIED_SITUATION.

You are running the ENTRY MONITOR workflow (Section 8), as amended
2026-08-11 (b): **confirmed-hold market entry**.

Fires at 10:20 ET. Every input comes from the 09:30-10:00 ET window and
nothing newer, so at 10:20 all of it is >= 20 minutes old and is served
by free SIP (Section 15). Do not run it earlier: at 10:05 the final bars
sit inside Alpaca's 15-minute delay and cannot be read from SIP at all.

The old stop-limit band (ORH x 1.0005 / x 1.0050), tick rounding, the
60-second cancel and PRICE_RAN_AWAY are RETIRED. They filled failed
breakouts and skipped working ones, by construction. Do not reintroduce
them from memory of an older version of this file.

Resolve today's date via: DATE=$(date +%Y-%m-%d).

IMPORTANT — ENVIRONMENT VARIABLES:
- ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_ENDPOINT, ALPACA_DATA_ENDPOINT,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID are ALREADY exported.
- There is NO .env file and you MUST NOT create, write, or source one.
- If a wrapper prints "KEY not set in environment" -> STOP, alert, exit.
- Verify env vars BEFORE any wrapper call (same pattern as pre-market.md).

IMPORTANT — DATA FEED:
- Every bars request MUST use feed=sip. scripts/alpaca.sh refuses
  anything else and there is no override (Section 15). IEX understates
  highs and overstates lows, which understates risk and OVERSIZES the
  position — a Section 10 breach.

IMPORTANT — PERSISTENCE:
- Fresh clone. File changes VANISH unless committed and pushed. MUST
  commit and push at STEP 8 if any trade was placed or any exception was
  logged.

STEP 1 — Halt check (mandatory, first real step):
  bash scripts/halt.sh check
If non-zero: Telegram alert with the halt reason, then STOP. No orders.

STEP 2 — Read today's screener output:
- Today's dated section in memory/CANDIDATES.md. If it's missing or not
  dated today: this is a data problem, not something to work around by
  running the screener inline (Section 0.3 forbids inventing a fallback
  the spec doesn't specify). Log UNSPECIFIED_SITUATION to
  memory/EXCEPTIONS-LOG.md, send one Telegram alert, and STOP. Never
  trade without today's documented screen.
- If today's regime state is FAIL: no new entries today. Skip to STEP 8.
- memory/POSITIONS.json (current open positions, for portfolio-limit math)
- memory/TRADING-STRATEGY.md Sections 7, 8 and 10

STEP 3 — Compute today's portfolio-limit budget (Section 10) BEFORE
looking at any candidate:
  open_count = number of symbols in memory/POSITIONS.json "open"
  total_open_risk_pct = sum(risk_per_share * shares_remaining) / equity,
    for every open position, as a percent of current equity
  entries_today_so_far = 0 (this routine runs once/day)
  remaining_slots = min(5 - open_count, 2 - entries_today_so_far)
If remaining_slots <= 0: no new entries possible today. Skip to STEP 8.

STEP 3b — WINDOW GUARD (mandatory, before touching any candidate).
This routine's premise is that the 09:30-10:00 ET window is CLOSED,
COMPLETE, and old enough for SIP. Prove it; do not assume it:

  a. Current time must be >= 10:20 ET. Compute it, don't guess:
     date -u +%Y-%m-%dT%H:%M:%SZ
     and convert (ET = UTC-4 during EDT, UTC-5 during EST).
  b. Pull the window for the regime proxy ONEQ:
     bash scripts/alpaca.sh bars "symbols=ONEQ&timeframe=5Min&start=<today 09:30 ET as UTC>&end=<today 10:00 ET as UTC>&limit=20&feed=sip"
     The response MUST contain a bar timestamped 09:55 ET. That is the
     final bar of the window; its presence proves the window closed and
     SIP will serve it.

If EITHER check fails: place NO orders, evaluate NO candidates. Log
UNSPECIFIED_SITUATION recording the current UTC time, the derived ET
time, and what the bar query returned. Send one Telegram alert. Skip to
STEP 8. An empty or short window is NOT a "no_trigger" result — it means
this routine ran when it should not have.

STEP 4 — For each ranked candidate in today's CANDIDATES.md, in rank
order, until you've placed remaining_slots entries or run out:

  4a. ONE bar pull. Everything below comes from it — no second request,
      nothing newer than 10:00 ET:
      bash scripts/alpaca.sh bars "symbols=SYM&timeframe=5Min&start=<today 09:30 ET as UTC>&end=<today 10:00 ET as UTC>&limit=20&feed=sip"
      From those bars compute:
        ORH            = HIGH of the FIRST bar (09:30-09:35 ET)
        today_open     = OPEN of that same first bar
        session_low    = lowest LOW across ALL bars 09:30-10:00
        final_bar      = the 09:55-10:00 ET bar
        decision_price = CLOSE of final_bar
      If the window is missing bars (no 09:30 bar or no 09:55 bar) for
      this symbol: log "incomplete_window", skip this candidate. Do NOT
      substitute a nearby bar.

  4b. Gap exclusion (Section 7): IF today_open > 1.05 x yesterday's close
      (yesterday's close is in the candidate's CANDIDATES.md row) ->
      reject, log the rejection, next candidate.
      Use today_open from 4a — the actual 09:30 session open. Never use
      `alpaca.sh quote`, which returns the CURRENT price and answers a
      different question.

  4c. TRIGGER (Section 8.2 as amended). BOTH conditions required:
        BREAKOUT: some bar in 09:35-10:00 closed above ORH
        HOLDING : final_bar closed above ORH  (decision_price > ORH)
      If BREAKOUT fails -> log "no_breakout", next candidate.
      If BREAKOUT passed but HOLDING failed -> log "breakout_faded",
        next candidate. This is the case the old rule used to BUY. It is
        now explicitly rejected.
      No re-arming, no second look later.

  4d. PRE-TRADE SIZING (Section 8.3):
        est_risk_share = decision_price - session_low
      Validate BEFORE ordering:
        IF est_risk_share <= 0 -> no trade, log INVALID_RISK, next.
        IF est_risk_share > (ADR_20 * decision_price) [ADR_20 is in the
          candidate's CANDIDATES.md row] -> no trade, log
          STOP_TOO_WIDE_PRETRADE, next.
          This is also what governs chasing: a stock that has run far
          from its session low trips here. There is deliberately no
          separate extension cap.
      Size:
        risk_capital = equity * 0.005
        intended_qty = floor(risk_capital / est_risk_share)
        cap          = floor((equity * 0.20) / decision_price)
        intended_qty = min(intended_qty, cap)
        IF intended_qty < 1 -> no trade, log "shares_below_1", next.

  4e. Portfolio-limit pre-check (Section 10):
        total_open_risk_pct + (est_risk_share * intended_qty / equity * 100)
          must stay <= 3.0%
        (intended_qty * decision_price) must be <= 20% of equity
      IF either would be breached -> no trade, log the breach, next
      candidate. Do not send the order.

  4f. Liquidity exclusion (Section 7): IF (intended_qty * decision_price)
      > 0.01 * dollar_volume_50d_avg [from the candidate's CANDIDATES.md
      row] -> no trade, log the exclusion, next candidate.
      Checked BEFORE ordering. Under the old stop-limit rule size was
      only known after the fill, so this had to buy and then immediately
      sell; now intended_qty and decision_price are both known up front,
      so the position is simply never opened.

  4g. ORDER (Section 8.4) — MARKET, not stop-limit:
      bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"<intended_qty>","side":"buy","type":"market","time_in_force":"day","client_order_id":"qms01-<DATE>-<SYM>-entry"}'
      client_order_id is MANDATORY — scripts/alpaca.sh refuses without
      one. A duplicate from a retry would double position size, which is
      a Section 10 breach, not a plumbing annoyance.
      Read back filled_qty and the actual fill price (avg fill).
        IF filled_qty == 0 -> no position, log NO_FILL with
          intended_qty, filled_qty=0, fill_ratio=0. Next candidate.
        IF filled_qty >= 1 -> THAT IS THE POSITION.
      From here use filled_qty everywhere, never intended_qty.
      Record fill_ratio = filled_qty / intended_qty.
      Never top up. Never re-send for this symbol today, for any reason.

  4h. STOP PLACEMENT (Section 8.5) — immediately after fill:
        STOP = session_low     (from 4a — already known, no new request)
      bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"<filled_qty>","side":"sell","type":"stop","stop_price":"<STOP>","time_in_force":"gtc","client_order_id":"qms01-<DATE>-<SYM>-stop"}'
      qty MUST be filled_qty. A resting sell-stop covering shares you do
      not hold goes SHORT when it triggers — Binding Constraint #6
      forbids that.
      The stop NEVER widens.

  4i. POST-FILL RECONCILIATION (Section 8.6). With no limit price
      bounding the fill, this is the SOLE slippage governor:
        actual_risk_share = fill_price - STOP
        actual_risk_pct   = (filled_qty * actual_risk_share) / equity
      IF actual_risk_pct > 0.0075 -> exit immediately at market and log
        RISK_OVERRUN. Cancel the resting stop from 4h FIRST
        (bash scripts/alpaca.sh cancel STOP_ORDER_ID), THEN
        bash scripts/alpaca.sh close SYM. Leaving a live sell-stop on
        shares you no longer hold is itself a hazard. Do NOT create a
        position; next candidate.
      ELSE log planned (est_risk_share) vs actual (actual_risk_share)
        and continue. A fill BELOW plan carries proportionally less risk
        than budgeted; that is fine and is never topped up.

  4j. Record the position in memory/POSITIONS.json "open" (entry_date,
      fill_price, initial_stop=STOP, risk_per_share=actual_risk_share,
      shares=filled_qty, shares_remaining=filled_qty, intended_qty,
      fill_ratio, decision_price, orh, partial_taken=false,
      current_stop=STOP, reference_sma_period from the candidate row,
      sessions_held=0, last_managed_date=null,
      entry_mechanism="confirmed_hold_market_1020ET",
      consolidation_high_ref from the candidate row).
      risk_per_share is the ACTUAL value from 4i, not the 4d estimate —
      Section 9 stop management, r_multiple and the Section 11
      distribution record all key off the real fill.

  4k. Append the entry to memory/TRADE-LOG.md per that file's header
      format. Include ORH, decision_price, session_low, planned vs
      actual risk per share, and intended_qty / filled_qty / fill_ratio.
      Section 11 requires these on every entry ATTEMPT, including ones
      that ended NO_FILL.

  4l. Increment open_count and entries_today_so_far; decrement
      remaining_slots; update total_open_risk_pct using
      actual_risk_share and filled_qty.

STEP 5 — Every rejection at every sub-step gets logged with the symbol
and the FIRST disqualifying rule — same discipline as the screener.
Record the counts of no_breakout / breakout_faded separately: the ratio
between them is the single most informative number this routine
produces about whether the strategy is finding real breakouts.

STEP 6 — If you hit ANY situation not explicitly covered above (an order
rejected for a reason you don't understand, a data gap, an ambiguous
fill), do NOT improvise. Log UNSPECIFIED_SITUATION with full detail and
skip only that candidate — do not let one uncertain case stop the rest
of the loop unless it's actually a Section 12 halt condition (in which
case write memory/HALT.md, alert, and stop everything).
scripts/alpaca.sh prints Alpaca's actual rejection body to stderr, so
read it before concluding a reason is not understood.

STEP 7 — Notification: only if at least one trade was placed, or any
RISK_OVERRUN / STOP_TOO_WIDE_PRETRADE / INVALID_RISK /
UNSPECIFIED_SITUATION was logged this run.
  bash scripts/telegram.sh "<symbols, shares, fill prices, one-line why>"

STEP 8 — COMMIT AND PUSH (mandatory if anything changed):
  # CRITICAL for this routine: orders you placed exist at Alpaca whether
  # or not this push lands. If it fails, memory/POSITIONS.json is lost
  # with the container and the next run sees an empty positions file
  # beside live broker positions carrying stops it knows nothing about.
  # The container's clone can land on a DETACHED HEAD, where a commit
  # sits on no branch and the push is rejected with "a pushed branch tip
  # is behind its remote counterpart". `git pull --rebase` does NOT fix
  # this — it reports "up to date" and the next push fails identically.
  # Re-attach FIRST (harmless no-op if already on main):
  git checkout -B main HEAD
  git add memory/TRADE-LOG.md memory/POSITIONS.json memory/EXCEPTIONS-LOG.md memory/CANDIDATES.md
  git commit -m "market-open entries $DATE"
  git push origin main
  # Verify it actually landed — these MUST match:
  git fetch origin && git rev-parse HEAD origin/main
If the two hashes differ the push did NOT land. Do NOT end the run
quietly: send a Telegram alert naming every symbol you entered, its
share count, fill price and stop, so the positions are recoverable by
hand. Skip commit only if truly nothing changed (regime FAIL and zero
candidates). On push failure: git pull --rebase origin main, then push
again. Never force-push.

CONFLICT DURING `git pull --rebase` — do NOT improvise inside the
compliance record.

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
