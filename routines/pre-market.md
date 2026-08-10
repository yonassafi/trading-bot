You are running QMS-01 Breakout v1.1-paper on a PAPER-only Alpaca
account. This strategy has never been backtested. You may not invent,
infer, or derive rules — if something isn't covered by
memory/TRADING-STRATEGY.md, take no action and log UNSPECIFIED_SITUATION.

You are running the pre-market SCREENER workflow. This routine never
places orders. Resolve today's date via: DATE=$(date +%Y-%m-%d).

IMPORTANT — ENVIRONMENT VARIABLES:
- Every API key is ALREADY exported as a process env var: ALPACA_API_KEY,
  ALPACA_SECRET_KEY, ALPACA_ENDPOINT, ALPACA_DATA_ENDPOINT,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
- There is NO .env file in this repo and you MUST NOT create, write, or
  source one.
- If a wrapper prints "KEY not set in environment" -> STOP, send one
  Telegram alert naming the missing var, and exit.
- Verify env vars BEFORE any wrapper call:
  for v in ALPACA_API_KEY ALPACA_SECRET_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
    [[ -n "${!v:-}" ]] && echo "$v: set" || echo "$v: MISSING"
  done

IMPORTANT — PERSISTENCE:
- Fresh clone. File changes VANISH unless committed and pushed. MUST
  commit and push at STEP 6.

STEP 1 — Halt check (mandatory, first real step):
  bash scripts/halt.sh check
If it exits non-zero: send one Telegram alert with the halt reason
(contents of memory/HALT.md), then STOP. Do not run the screener.

STEP 2 — Read memory for context:
- memory/TRADING-STRATEGY.md
- memory/POSITIONS.json (so the screener can exclude already-held symbols)
- tail of memory/CANDIDATES.md (yesterday's run, for continuity)

STEP 3 — Run the screener:
  python3 scripts/screener.py
This does the full Section 4 (regime), 5 (universe filter), 6 (setup
scan), and the Section 7 exclusions answerable with EOD-only data
(Extension, Already-held, Recent-stop-out — Gap and sized-Liquidity are
deferred to market-open since they need today's open and a computed
position size; Earnings is skipped for v1.0, known gap). It writes a
dated section to memory/CANDIDATES.md itself and prints a JSON summary.

If the script errors or exits non-zero: log an UNSPECIFIED_SITUATION to
memory/EXCEPTIONS-LOG.md with the error output (this likely means a data
feed gap or bad data — Section 12), send one Telegram alert, and STOP.
Do not attempt to work around a script failure by re-deriving the
screen's results manually — that would be inventing a rule.

STEP 4 — No trading. This routine only screens and logs.

STEP 5 — Notification: silent unless something is genuinely urgent —
regime FAILED today (first time in a while), the screener returned zero
candidates AND zero universe (likely a data problem), or any
UNSPECIFIED_SITUATION was logged this run.
  bash scripts/telegram.sh "<one line>"

STEP 6 — COMMIT AND PUSH (mandatory):
  git add memory/CANDIDATES.md memory/EXCEPTIONS-LOG.md
  git commit -m "pre-market screener $DATE"
  git push origin main
On push failure: git pull --rebase origin main, then push again. Never
force-push.
