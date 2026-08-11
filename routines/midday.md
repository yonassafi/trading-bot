You are running QMS-01 Breakout v1.1-paper on a PAPER-only Alpaca
account.

**This routine is a heartbeat only. It takes NO trading action.**
QMS-01's Section 9 (position management) is evaluated once daily, after
the close, in routines/daily-summary.md — not intraday. The resting
protective stop on every position is a real broker-side stop-market
order (see memory/TRADING-STRATEGY.md's Operator Substitutions); Alpaca
itself handles a gap below the stop without this routine polling for it.

If your Claude Code cloud routine setup still has a midday cron trigger
enabled from before this strategy was adopted, either disable it or let
it keep firing this no-op heartbeat — it will never place, modify, or
cancel an order.

Resolve today's date via: DATE=$(date +%Y-%m-%d).

IMPORTANT — ENVIRONMENT VARIABLES:
- ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_ENDPOINT, ALPACA_DATA_ENDPOINT,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID are ALREADY exported.
- There is NO .env file and you MUST NOT create, write, or source one.

STEP 1 — Halt check:
  bash scripts/halt.sh check
If non-zero: Telegram alert with the reason, then STOP.

STEP 2 — Read memory/POSITIONS.json "open" and pull live orders:
  bash scripts/alpaca.sh orders

STEP 3 — For each open position, confirm a resting stop-type order
exists for that symbol among the open orders. If ANY open position is
missing its resting stop: this is a genuine problem (Section 12: "any
situation where you feel the need to deviate from a rule" / a stop
should always be present). Log UNSPECIFIED_SITUATION to
memory/EXCEPTIONS-LOG.md naming the symbol, and send one Telegram alert.
Do NOT place a replacement stop yourself from this routine — that
decision belongs to daily-summary's reconciliation step, which has the
full Section 9 context. This routine only detects and reports.

STEP 4 — No other action. No file writes besides
memory/EXCEPTIONS-LOG.md if STEP 3 found something.

STEP 5 — COMMIT AND PUSH only if memory/EXCEPTIONS-LOG.md changed:
  # The container's clone can land on a DETACHED HEAD, where a commit
  # sits on no branch and the push is rejected. `git pull --rebase` does
  # NOT fix it. Re-attach FIRST (no-op if already on main):
  git checkout -B main HEAD
  git add memory/EXCEPTIONS-LOG.md
  git commit -m "midday heartbeat: missing-stop alert $DATE"
  git push origin main
  # Verify it landed — these MUST match:
  git fetch origin && git rev-parse HEAD origin/main
Otherwise skip the commit entirely — this routine usually changes
nothing. Never force-push.
