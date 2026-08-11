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

STEP 3 — Cross-check POSITIONS.json against the live orders BOTH ways.
Also pull live positions for the reverse direction:
  bash scripts/alpaca.sh positions

  (a) MISSING STOP. Every open position must have a resting stop-type
      order. If any does not: Section 12 territory (a stop should always
      be present). Log UNSPECIFIED_SITUATION naming the symbol, send one
      Telegram alert.

  (b) STOP QTY MISMATCH. A stop whose qty EXCEEDS that position's
      shares_remaining will go SHORT when it triggers — Binding
      Constraint #6 (long only) forbids that. Log UNSPECIFIED_SITUATION
      with the order id, stop qty and actual shares_remaining, and alert
      naming it as a long-only breach risk. A stop qty BELOW
      shares_remaining leaves part of the position unprotected — log and
      alert that too.

  (c) ORPHANS. A live Alpaca position with no entry in POSITIONS.json,
      or a resting sell-stop for a symbol with no open position at all.
      Both indicate a run that placed orders and failed to persist.
      Log UNSPECIFIED_SITUATION and alert.

Do NOT place, modify, or cancel ANY order from this routine — not a
replacement stop, not a cancellation of an orphan. That decision belongs
to daily-summary's reconciliation, which has the full Section 9 context.
This routine only detects and reports.

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
