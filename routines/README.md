# Cloud Routines

These five prompts are the production path. Each one gets pasted verbatim
into a Claude Code cloud routine (Routines → New Routine → paste into the
prompt field). Do not paraphrase — the env-var check block and the
commit-and-push step are load-bearing.

## Cron schedules (set your local timezone; example below is America/Chicago)

| Routine | Cron | When |
|---|---|---|
| pre-market.md | `0 6 * * 1-5` | 6:00 AM weekdays |
| market-open.md | `30 8 * * 1-5` | 8:30 AM weekdays (market open) |
| midday.md | `0 12 * * 1-5` | Noon weekdays |
| daily-summary.md | `0 15 * * 1-5` | 3:00 PM weekdays (market close) |
| weekly-review.md | `0 16 * * 5` | 4:00 PM Fridays only |

## One-time prerequisites (do once, before creating any routine)

1. **Install the Claude GitHub App** on this repo (least privilege — this
   repo only). Gives the cloud container permission to clone and push.
2. **Enable "Allow unrestricted branch pushes"** in each routine's
   environment settings. Without it, `git push origin main` silently fails
   with a proxy error — the #1 first-time setup failure.
3. **Set environment variables on the routine itself** (not in a `.env`
   file — there is no `.env` in cloud mode):
   - `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (required)
   - `ALPACA_ENDPOINT` (optional; defaults to paper trading URL)
   - `ALPACA_DATA_ENDPOINT` (optional; defaults to data URL)
   - `PERPLEXITY_API_KEY` (required for research workflows)
   - `PERPLEXITY_MODEL` (optional; defaults to `sonar`)
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (required for notifications)

## The mental model

Each firing is an ephemeral container: clone `main`, run the prompt, commit,
push, destroy. If a run doesn't commit and push, everything it did
evaporates — the next run will never see it. Git is the only memory.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Repository not accessible" | GitHub App not installed | Install it, grant access to this repo |
| `git push` fails, proxy/permission error | "Allow unrestricted branch pushes" is off | Enable it in the routine's environment |
| `ALPACA_API_KEY not set` | Env var missing from routine env | Add it in the routine config, not `.env` |
| Agent creates a `.env` file anyway | Prompt was paraphrased | Re-paste the routine `.md` exactly |
| Yesterday's trades missing today | Previous run didn't commit+push | Check `git log origin/main`; re-verify the commit step |
| Push fails "fetch first" | Another run pushed in between | Prompt handles this with `git pull --rebase`; investigate only if it loops |
| Telegram message didn't arrive | `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` missing | Script falls back to `DAILY-SUMMARY.md`; add the vars |
| Perplexity calls didn't happen | `PERPLEXITY_API_KEY` missing | Script exits 3, agent falls back to WebSearch |
| Alpaca rejects stop with PDT error | Same-day stop on same-day buy | Prompt's fallback ladder handles this; re-check STEP 5 if not cascading |
