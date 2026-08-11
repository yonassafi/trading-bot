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

## Cron schedule

**Cloud routine crons are UTC only — there is no timezone field.** The ET
times below are what the strategy specifies; the UTC column is what is
actually deployed. Minimum interval is 1 hour.

| Routine | ET | Cron (UTC, EDT) | What it does |
|---|---|---|---|
| `pre-market.md` | 07:00 Mon-Fri | `0 11 * * 1-5` | Runs `scripts/screener.py`: regime check, universe filter, setup scan, ranks candidates. No trading. |
| `market-open.md` | 10:05 Mon-Fri | `5 14 * * 1-5` | Must fire strictly after the 09:30-10:00 ET opening-range window closes. Checks the retrospective ORH trigger, sizes, places entries + resting stops. |
| `midday.md` | 12:30 Mon-Fri | `30 16 * * 1-5` | No trading — QMS-01's Section 9 is end-of-day only. A no-op heartbeat that only alerts if a position is missing its resting stop. Safe to disable entirely. |
| `daily-summary.md` | 16:10 Mon-Fri | `10 20 * * 1-5` | Reconciles fills, runs `scripts/position_manager.py` (Section 9.2-9.4), checks the 25%-drawdown halt condition, posts the EOD summary. |
| `weekly-review.md` | Fri 16:45 | `45 20 * * 5` | Distribution-tracking report only. Never modifies `memory/TRADING-STRATEGY.md`. |

### DST is a live hazard, not a nuisance

US DST ends **Sunday Nov 1, 2026**; ET goes from UTC-4 to UTC-5. If the
UTC crons above are not shifted **+1 hour**, `market-open` fires at 09:05
ET — an hour *before* the 09:30-10:00 opening range it reads
retrospectively even exists. EST values:

| Routine | Cron (UTC, EST) |
|---|---|
| `pre-market.md` | `0 12 * * 1-5` |
| `market-open.md` | `5 15 * * 1-5` |
| `midday.md` | `30 17 * * 1-5` |
| `daily-summary.md` | `10 21 * * 1-5` |
| `weekly-review.md` | `45 21 * * 5` |

A one-time routine `qms01-dst-shift-2026-11` is scheduled for
`2026-11-01T18:00:00Z` to apply this automatically and alert via Telegram
either way. The reverse shift (EST->EDT, -1 hour) is due **Sunday Mar 14,
2027** and needs a new one-time routine.

Every scheduled slot lands before 00:00 UTC in both EDT and EST, so
`DATE=$(date +%Y-%m-%d)` inside the UTC container always equals the ET
calendar date. An off-hours *manual* run does not have that property and
will stamp tomorrow's date — expect a spurious "schedule
misconfiguration" exception if you trigger one late in the evening ET.

## One-time prerequisites

1. **Install the Claude GitHub App** on this repo (least privilege — this
   repo only).
2. **Allow network egress to these hosts** in the routine environment's
   network policy:
   - `paper-api.alpaca.markets`
   - `data.alpaca.markets`
   - `api.telegram.org`

   Verified 2026-08-11 across two runs: the proxy refuses CONNECT to all
   three with a 403. Until they are allowlisted no routine can trade,
   manage a position, **or raise an alert** — the Telegram block means a
   failure on a live position leaves no trace outside this repo.
   `github.com` is already permitted (push works).

   **This cannot be fixed from the repository.** `.claude/settings.json`
   sets `sandbox.network.allowedDomains` for these three hosts, and it
   made no difference — the denial is the *routine environment's* egress
   policy, which deliberately ignores repo-level settings so a repo
   cannot widen its own network access. The allowlist file is kept only
   as a declaration of which hosts the bot needs. The fix must be applied
   to the environment itself (claude.ai/code -> environment -> network /
   custom domains), and may require an org administrator.

   (An older revision of this file listed "Allow unrestricted branch
   pushes" as prerequisite #2. That setting no longer exists in the
   console and push works without it. Removed.)
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
| `connect_rejected <host>:443` / proxy 403 on any Alpaca or Telegram call | Environment network policy blocks egress | Allowlist the three hosts in prerequisite #2. Do not work around it by changing data sources — Alpaca is not substitutable |
| `scripts/alpaca.sh order ...` refuses with "REFUSING: ... not the paper-trading endpoint" | `ALPACA_ENDPOINT` points at the live API | This is the safety guard working correctly — fix the env var, don't bypass the script |
| `ALPACA_API_KEY not set` | Env var missing from routine env | Add it in the routine config, not `.env` |
| Routine did nothing and logged `UNSPECIFIED_SITUATION` | A situation genuinely isn't covered by `memory/TRADING-STRATEGY.md` | This is correct behavior per Section 0.3 — read the exception, decide manually, do not "fix" the routine into guessing |
| `market-open` found no `CANDIDATES.md` entry for today | `pre-market` didn't run or didn't commit | Check `git log origin/main`; re-run `pre-market` manually if needed — `market-open` will not run the screener inline |
| Yesterday's trades/EOD snapshot missing | Previous run didn't commit+push | Check `git log origin/main`; re-verify the commit step of the relevant routine |
| Push fails "fetch first" | Another run pushed in between | Prompt handles this with `git pull --rebase`; investigate only if it loops |
| `memory/HALT.md` exists and routines are all no-oping | A halt condition fired (Section 12) | Read the file, investigate, clear it with `/resume` only when you're sure it's safe to resume |
| Telegram message didn't arrive | `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` missing | Script falls back to `DAILY-SUMMARY.md`; add the vars |
| `screener.py` is slow or times out | Full market scan is a lot of API calls | See known limitations in `memory/TRADING-STRATEGY.md`; consider whether the routine's timeout budget needs to increase |
