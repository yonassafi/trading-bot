You are running QMS-01 Breakout v1.1-paper on a PAPER-only Alpaca
account. This strategy has never been backtested. You may not invent,
infer, or derive rules — if something isn't covered by
memory/TRADING-STRATEGY.md, take no action and log UNSPECIFIED_SITUATION.

You are running the ENTRY MONITOR workflow (Section 8). This fires at
10:05 ET — strictly AFTER the 09:30-10:00 ET opening-range window closes,
because entry detection is a retrospective check against that window's
5-minute bars (memory/TRADING-STRATEGY.md's Operator Substitutions
section explains why). It is not a "market open" routine in the old
sense — do not try to run it earlier.

Resolve today's date via: DATE=$(date +%Y-%m-%d).

IMPORTANT — ENVIRONMENT VARIABLES:
- ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_ENDPOINT, ALPACA_DATA_ENDPOINT,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID are ALREADY exported.
- There is NO .env file and you MUST NOT create, write, or source one.
- If a wrapper prints "KEY not set in environment" -> STOP, alert, exit.
- Verify env vars BEFORE any wrapper call (same pattern as pre-market.md).

IMPORTANT — PERSISTENCE:
- Fresh clone. File changes VANISH unless committed and pushed. MUST
  commit and push at the final step if any trade was placed or any
  exception was logged.

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
- If today's regime state is FAIL: no new entries today. Skip to STEP 8
  (still reconcile/log, just place no orders).
- memory/POSITIONS.json (current open positions, for portfolio-limit math)
- memory/TRADING-STRATEGY.md Sections 8 and 10

STEP 3 — Compute today's portfolio-limit budget (Section 10) BEFORE
looking at any candidate:
  open_count = number of symbols in memory/POSITIONS.json "open"
  total_open_risk_pct = sum(risk_per_share * shares_remaining) / equity,
    for every open position, as a percent of current equity
  entries_today_so_far = 0 (this routine runs once/day)
  remaining_slots = min(5 - open_count, 2 - entries_today_so_far)
If remaining_slots <= 0: no new entries possible today regardless of
candidates. Skip to STEP 8.

STEP 3b — WINDOW GUARD (mandatory, before touching any candidate).
This routine's entire premise is that the 09:30-10:00 ET opening range
is CLOSED and COMPLETE. If it fires early — DST drift, scheduler jitter,
a manual test run — ORH would be computed from a partial 09:30-09:35 bar
and every downstream number (session_low_T, est_risk_share, shares, STOP)
inherits that error silently. Prove the precondition; do not assume it:

  a. Current time must be >= 10:00 ET. Compute it, don't guess:
     date -u +%Y-%m-%dT%H:%M:%SZ
     and convert (ET = UTC-4 during EDT, UTC-5 during EST).
  b. Pull the opening-range bars for the regime proxy ONEQ:
     bash scripts/alpaca.sh bars "symbols=ONEQ&timeframe=5Min&start=<today 09:30 ET as UTC>&end=<today 10:00 ET as UTC>&limit=20&feed=iex"
     The response must contain a bar timestamped 09:55 ET. That is the
     last bar of the window; its presence proves the window closed and
     the data has settled.

If EITHER check fails: place NO orders, evaluate NO candidates. Log
UNSPECIFIED_SITUATION to memory/EXCEPTIONS-LOG.md recording the current
UTC time, the derived ET time, and what the bar query returned. Send one
Telegram alert. Skip to STEP 8. An empty or short window is NOT a
"no_trigger" result and must never be recorded as one — it means this
routine ran when it should not have.

STEP 4 — For each ranked candidate in today's CANDIDATES.md, in rank
order, until you've placed remaining_slots entries or run out of
candidates:

  4a. Gap exclusion (Section 7 — only checkable now that the market has
      opened): pull today's first daily bar / current quote via
      `bash scripts/alpaca.sh quote SYM`. If today's open > 1.05 x
      yesterday's close (yesterday's close is in the candidate's
      CANDIDATES.md row): reject this candidate, log the rejection, move
      to the next candidate.

  4b. Opening range: pull 09:30-10:00 ET 5-minute bars:
      bash scripts/alpaca.sh bars "symbols=SYM&timeframe=5Min&start=<today 09:30 ET as UTC>&end=<today 10:00 ET as UTC>&limit=20&feed=iex"
      (feed=iex: confirmed free-tier Alpaca account — the default/SIP feed 403s.)
      ORH = high of the FIRST bar (09:30-09:35 ET).

  4c. Trigger (Section 8.2, retrospective approximation): scan the bars
      from 09:35 to 10:00 ET in order. Find the FIRST bar whose price
      closed above ORH. If none: no entry for this symbol today — log
      "no_trigger", move to the next candidate. Do not chase a break
      found after 10:00 ET.

  4d. PRE-TRADE SIZING (Section 8.3) — everything here is computed
      BEFORE any order is sent. T = the close of the triggering bar from
      4c. All inputs come from the bars you already pulled in 4b.
      session_low_T  = lowest LOW among the 09:30 ET bar through the
                       triggering bar, inclusive
      limit_price    = ORH * 1.0050        (worst-case fill)
      est_risk_share = limit_price - session_low_T
      Validate BEFORE sending:
      IF est_risk_share <= 0 -> no trade, log INVALID_RISK, next candidate.
      IF est_risk_share > (ADR_20 * limit_price) [ADR_20 is in the
        candidate's CANDIDATES.md row] -> no trade, log
        STOP_TOO_WIDE_PRETRADE, next candidate.
      Size:
      risk_capital = equity * 0.005
      shares = floor(risk_capital / est_risk_share)
      cap = floor((equity * 0.20) / limit_price)
      shares = min(shares, cap)
      IF shares < 1 -> no trade, log "shares_below_1", next candidate.

  4e. Portfolio-limit pre-check (Section 10) — now checkable before
      ordering, because shares is known:
      total_open_risk_pct + (est_risk_share * shares / equity * 100)
        must stay <= 3.0%, and (shares * limit_price) <= 20% of equity.
      IF either would be breached -> no trade, log the breach, next
      candidate. Do not send the order.

  4f. ORDER (Section 8.4):
      bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"<shares>","side":"buy","type":"stop_limit","stop_price":"<ORH*1.0005>","limit_price":"<ORH*1.0050>","time_in_force":"day"}'
      Poll `bash scripts/alpaca.sh orders` for up to 60 seconds. If still
      unfilled after 60 seconds: cancel it (`bash scripts/alpaca.sh
      cancel ORDER_ID`), log "unfilled_60s", move to the next candidate.
      Never chase. NEVER re-send for the same symbol the same day, for
      any reason.

  4g. STOP PLACEMENT (Section 8.5) — immediately after fill:
      Pull bars from 09:30 ET through the actual fill time (this is a
      LATER window than 4b — the fill happens around now, not at T):
      bash scripts/alpaca.sh bars "symbols=SYM&timeframe=5Min&start=<today 09:30 ET as UTC>&end=<now as UTC>&limit=200&feed=iex"
      session_low_F = lowest LOW across that whole range
      STOP = session_low_F
      Place it immediately as a real stop-market order (Operator
      Substitutions explains why stop-market, not stop-limit):
      bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"<shares>","side":"sell","type":"stop","stop_price":"<STOP>","time_in_force":"gtc"}'
      The stop NEVER widens. If the low extends later in the session it
      does not move.

  4h. POST-FILL RECONCILIATION (Section 8.6):
      actual_risk_share = fill_price - STOP
      actual_risk_pct   = (shares * actual_risk_share) / equity
      IF actual_risk_pct > 0.0075 -> exit immediately at market and log
        RISK_OVERRUN. Cancel the resting stop from 4g FIRST
        (bash scripts/alpaca.sh cancel STOP_ORDER_ID), THEN
        bash scripts/alpaca.sh close SYM. Leaving a live sell-stop on
        shares you no longer hold is itself a hazard. Do NOT create a
        position; move to the next candidate.
      ELSE log planned (est_risk_share) vs actual (actual_risk_share)
        risk and continue.

  4i. Liquidity exclusion (Section 7): IF (shares * fill_price) >
      0.01 * dollar_volume_50d_avg [from the candidate's CANDIDATES.md
      row] -> cancel the resting stop first, then exit immediately at
      market, log the exclusion, do NOT keep the position.

  4j. Record the position in memory/POSITIONS.json "open" (entry_date,
      fill_price, initial_stop=STOP, risk_per_share=actual_risk_share,
      shares, shares_remaining=shares, partial_taken=false,
      current_stop=STOP, reference_sma_period from the candidate row,
      sessions_held=0,
      entry_mechanism="retrospective_10ET_approximation",
      consolidation_high_ref from the candidate row).
      Note risk_per_share is the ACTUAL value from 4h, not the 4d
      estimate — everything downstream (Section 9 stop management,
      r_multiple, distribution tracking) keys off the real fill.

  4k. Append the entry to memory/TRADE-LOG.md per the format in that
      file's header. Include both planned and actual risk per share.

  4l. Increment open_count and entries_today_so_far; decrement
      remaining_slots; update total_open_risk_pct using
      actual_risk_share.

STEP 5 — Any rejection at any sub-step gets logged with the symbol and
the first disqualifying rule — same discipline as the screener.

STEP 6 — If you hit ANY situation not explicitly covered by the steps
above (an order rejected for a reason you don't understand, a data gap,
an ambiguous fill), do NOT improvise. Log UNSPECIFIED_SITUATION to
memory/EXCEPTIONS-LOG.md with full detail, and skip only that candidate
— do not let one uncertain case stop the rest of the loop unless it's
actually a Section 12 halt condition (in which case write memory/HALT.md,
alert, and stop everything).

STEP 7 — Notification: only if at least one trade was placed, or any
STOP_TOO_WIDE/UNSPECIFIED_SITUATION was logged this run.
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
