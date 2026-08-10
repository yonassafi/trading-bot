You are running QMS-01 Breakout v1.1-paper on a PAPER-only Alpaca
account. This routine REPORTS ONLY. Per Section 0.4, you may not
optimise or adjust any strategy parameter, including in response to this
week's results — do not touch memory/TRADING-STRATEGY.md from this
routine, regardless of what the numbers show.

You are running the Friday weekly-review workflow. Fires at 16:45 ET
Friday, after that day's daily-summary has already committed. Resolve
today's date via: DATE=$(date +%Y-%m-%d).

IMPORTANT — ENVIRONMENT VARIABLES:
- ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_ENDPOINT, ALPACA_DATA_ENDPOINT,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID are ALREADY exported.
- There is NO .env file and you MUST NOT create, write, or source one.

IMPORTANT — PERSISTENCE:
- Fresh clone. File changes VANISH unless committed and pushed. MUST
  commit and push at STEP 5.

STEP 1 — Halt check:
  bash scripts/halt.sh check
If non-zero: still produce the report (this routine reports, it doesn't
trade), but note the halt state prominently in both the file and the
Telegram message.

STEP 2 — Read for full context:
- memory/WEEKLY-REVIEW.md (match the existing template exactly)
- This week's entries in memory/TRADE-LOG.md
- memory/POSITIONS.json — "closed" array is the source of truth for
  distribution tracking (Section 11), computed since inception, not just
  this week
- This week's entries in memory/EXCEPTIONS-LOG.md
- memory/RISK-STATE.json

STEP 3 — Pull Friday close state:
  bash scripts/alpaca.sh account
  bash scripts/alpaca.sh positions

STEP 4 — Compute, per the template in memory/WEEKLY-REVIEW.md:
- Starting/ending equity and week return (from this week's TRADE-LOG.md
  EOD snapshots)
- Trades this week (entries + exits), open positions, total open risk %
- Distribution tracking from memory/POSITIONS.json's "closed" array,
  ALL-TIME (Section 11 calls this "a running record"):
    win_rate = wins / total_closed
    avg_winning_r = mean(r_multiple for closed trades where r_multiple > 0)
    avg_losing_r = mean(r_multiple for closed trades where r_multiple <= 0)
    largest_winning_r = max(r_multiple)
    pct_profit_from_best_trade = best trade's realized $ profit / sum of
      all positive realized $ profit, as a percent
  Report the tail check: is largest_winning_r several times
  avg_winning_r? State the answer plainly. Do not act on it.
- Exceptions this week: count + one-line pointer to each
  UNSPECIFIED_SITUATION/STOP_TOO_WIDE/HALT entry in
  memory/EXCEPTIONS-LOG.md dated this week

STEP 5 — Append the full section to memory/WEEKLY-REVIEW.md per its
template, including the "Known Gaps Reminder" block restated verbatim
(no earnings filtering, no sector cap, IEX-feed volume, best-effort
ADR/common-stock filtering, retrospective entry approximation).

Do NOT modify memory/TRADING-STRATEGY.md. Do NOT propose rule changes.
If you notice something that looks like it should change, log it as an
observation in this week's section, not as an action.

STEP 6 — Send ONE Telegram message, <= 15 lines:
  bash scripts/telegram.sh "Week ending MMM DD
  Equity: \$X (±X% week, ±X% phase)
  Trades: N | Open: N/5
  Win rate: X% | Avg win: X.XXR | Avg loss: X.XXR | Largest win: X.XXR
  Best trade share of profit: X%
  <halt-state note if applicable>"

STEP 7 — COMMIT AND PUSH (mandatory):
  git add memory/WEEKLY-REVIEW.md
  git commit -m "weekly review $DATE"
  git push origin main
On push failure: git pull --rebase origin main, then push again. Never
force-push. Note: unlike the old strategy's weekly-review, this NEVER
also commits memory/TRADING-STRATEGY.md — that file is never touched by
an automated routine.
