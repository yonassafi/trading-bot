# Cloud Routines — QMS-01 Breakout v1.1-paper

These five prompts are the production path. Each gets pasted verbatim
into a Claude Code cloud routine (Routines → New Routine → paste into the
prompt field). Do not paraphrase — the env-var check block, the halt
check, and the commit-and-push step are all load-bearing.

**This cadence is different from a typical "trade at the open" bot.**
QMS-01's entry detection is a retrospective check against the 09:30-10:00
ET opening range, and Section 9 position management is explicitly
end-of-day only — so `market-open` fires later than the open, and there
is no midday trading routine at all. See
`memory/TRADING-STRATEGY.md`'s "Operator Substitutions" section for why.

## Cron schedule (ET)

| Routine | Cron (ET) | What it does |
|---|---|---|
| `pre-market.md` | `0 7 * * 1-5` (07:00) | Runs `scripts/screener.py`: regime check, universe filter, setup scan, ranks candidates. No trading. |
| `market-open.md` | `5 10 * * 1-5` (10:05) | Must fire strictly after the 09:30-10:00 ET opening-range window closes. Checks the retrospective ORH trigger, sizes, places entries + resting stops. |
| `midday.md` | Optional / disable | No trading — QMS-01's Section 9 is end-of-day only. If left enabled it's a no-op heartbeat that only alerts if a position is missing its resting stop. Safe to disable entirely. |
| `daily-summary.md` | `10 16 * * 1-5` (16:10) | Reconciles fills, runs `scripts/position_manager.py` (Section 9.2-9.4), checks the 25%-drawdown halt condition, posts the EOD summary. |
| `weekly-review.md` | `45 16 * * 5` (Fri 16:45) | Distribution-tracking report only. Never modifies `memory/TRADING-STRATEGY.md`. |

Set these as America/New_York (ET) on the routine, or convert to your
routine's configured timezone.

## One-time prerequisites

1. **Install the Claude GitHub App** on this repo (least privilege — this
   repo only).
2. **Enable "Allow unrestricted branch pushes"** in each routine's
   environment settings — without it `git push origin main` silently
   fails with a proxy error.
3. **Set environment variables on the routine itself** (not `.env` — no
   `.env` exists in cloud mode):
   - `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (required)
   - `ALPACA_ENDPOINT` (optional; defaults to Alpaca's **paper** trading
     URL — `scripts/alpaca.sh` refuses to place orders against anything
     else, per QMS-01 Binding Constraint #1)
   - `ALPACA_DATA_ENDPOINT` (optional; defaults to the data URL)
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (required for notifications)
   - `PERPLEXITY_API_KEY` is **not required** — QMS-01 has no research step.

## The mental model

Each firing is an ephemeral container: clone `main`, run the prompt,
commit, push, destroy. If a run doesn't commit and push, everything it
did evaporates. Git is the only memory — and for `daily-summary`, the
committed `memory/RISK-STATE.json` and `memory/POSITIONS.json` are what
the *next* run's drawdown check and reconciliation depend on.

## The halt mechanism

Every routine's first real step is `bash scripts/halt.sh check`. If
`memory/HALT.md` exists, the routine alerts and stops — no trading, no
position management, nothing else touched (Section 12: "stop trading,
close nothing, report"). Only a human clears it, via the local
`/resume` command — no routine may ever delete `memory/HALT.md` itself.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Repository not accessible" | GitHub App not installed | Install it, grant access to this repo |
| `git push` fails, proxy/permission error | "Allow unrestricted branch pushes" is off | Enable it in the routine's environment |
| `scripts/alpaca.sh order ...` refuses with "REFUSING: ... not the paper-trading endpoint" | `ALPACA_ENDPOINT` points at the live API | This is the safety guard working correctly — fix the env var, don't bypass the script |
| `ALPACA_API_KEY not set` | Env var missing from routine env | Add it in the routine config, not `.env` |
| Routine did nothing and logged `UNSPECIFIED_SITUATION` | A situation genuinely isn't covered by `memory/TRADING-STRATEGY.md` | This is correct behavior per Section 0.3 — read the exception, decide manually, do not "fix" the routine into guessing |
| `market-open` found no `CANDIDATES.md` entry for today | `pre-market` didn't run or didn't commit | Check `git log origin/main`; re-run `pre-market` manually if needed — `market-open` will not run the screener inline |
| Yesterday's trades/EOD snapshot missing | Previous run didn't commit+push | Check `git log origin/main`; re-verify the commit step of the relevant routine |
| Push fails "fetch first" | Another run pushed in between | Prompt handles this with `git pull --rebase`; investigate only if it loops |
| `memory/HALT.md` exists and routines are all no-oping | A halt condition fired (Section 12) | Read the file, investigate, clear it with `/resume` only when you're sure it's safe to resume |
| Telegram message didn't arrive | `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` missing | Script falls back to `DAILY-SUMMARY.md`; add the vars |
| `screener.py` is slow or times out | Full market scan is a lot of API calls | See known limitations in `memory/TRADING-STRATEGY.md`; consider whether the routine's timeout budget needs to increase |
