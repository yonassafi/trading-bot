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

  4d. Order (Section 8.3): place a real stop-limit buy —
      stop = ORH * 1.0005, limit = ORH * 1.0050 — via:
      bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"N_PLACEHOLDER","side":"buy","type":"stop_limit","stop_price":"X.XX","limit_price":"X.XX","time_in_force":"day"}'
      (qty is computed in 4f below — compute sizing BEFORE placing this
      order, using the ORH-based stop estimate; do not place with a
      placeholder quantity.)
      Poll `bash scripts/alpaca.sh orders` for up to 60 seconds. If still
      unfilled after 60 seconds: cancel it (`bash scripts/alpaca.sh
      cancel ORDER_ID`), log "unfilled_60s", move to the next candidate.
      Never chase — do not re-place at a worse price.

  4e. Initial stop (Section 8.4): STOP = lowest low among the 09:30 ET
      bar through the triggering bar (inclusive). risk_per_share =
      fill_price - STOP.

  4f. Stop width validation (Section 8.5): IF risk_per_share >
      (ADR_20 x fill_price) [ADR_20 is in the candidate's CANDIDATES.md
      row] -> exit immediately at market
      (bash scripts/alpaca.sh close SYM), log STOP_TOO_WIDE to
      memory/EXCEPTIONS-LOG.md, do NOT create a position, move to the
      next candidate.

  4g. Size (Section 8.6):
      risk_capital = equity * 0.005
      shares = floor(risk_capital / risk_per_share)
      cap = floor((equity * 0.20) / fill_price)
      shares = min(shares, cap)
      IF shares < 1: no trade, log "shares_below_1", move on.

  4h. Liquidity exclusion (Section 7, only checkable once size is known):
      IF (shares * fill_price) > 0.01 * dollar_volume_50d_avg [from the
      candidate's CANDIDATES.md row]: this candidate already filled at
      4d — exit immediately at market (like 4f), log the exclusion, do
      NOT keep the position.

  4i. Portfolio-limit re-check: total_open_risk_pct + (risk_per_share *
      shares / equity * 100) must stay <= 3.0%, and (shares * fill_price)
      must stay <= 20% of equity. If either would be breached: exit
      immediately at market, log the breach, do NOT keep the position.

  4j. Place the resting protective stop as a real stop-market order
      (memory/TRADING-STRATEGY.md's Operator Substitutions explains why
      stop-market, not stop-limit):
      bash scripts/alpaca.sh order '{"symbol":"SYM","qty":"N","side":"sell","type":"stop","stop_price":"STOP","time_in_force":"gtc"}'

  4k. Record the position in memory/POSITIONS.json "open" (entry_date,
      fill_price, initial_stop, risk_per_share, shares,
      shares_remaining=shares, partial_taken=false, current_stop=STOP,
      reference_sma_period from the candidate row, sessions_held=0,
      entry_mechanism="retrospective_10ET_approximation",
      consolidation_high_ref from the candidate row).

  4l. Append the entry to memory/TRADE-LOG.md per the format in that
      file's header.

  4m. Increment open_count and entries_today_so_far; decrement
      remaining_slots; update total_open_risk_pct.

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
  git add memory/TRADE-LOG.md memory/POSITIONS.json memory/EXCEPTIONS-LOG.md memory/CANDIDATES.md
  git commit -m "market-open entries $DATE"
  git push origin main
Skip commit if truly nothing changed (regime FAIL and zero candidates).
On push failure: git pull --rebase origin main, then push again. Never
force-push.
