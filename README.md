# Trading Bot

An autonomous, Git-memory swing-trading agent built on Claude Code. Stocks
only, paper trading, hard risk rules enforced before every order. See
`memory/TRADING-STRATEGY.md` for the rulebook and `routines/README.md` for
how the scheduled workflows are wired up.

## Quickstart (local)

1. `cp env.template .env` and fill in your Alpaca (paper), Perplexity, and
   Telegram credentials. `.env` is gitignored — never commit it.
2. Open this repo in Claude Code.
3. Run `/portfolio` to confirm the Alpaca connection works (account +
   positions should print cleanly).
4. Ad-hoc commands live in `.claude/commands/`: `/portfolio`, `/trade`,
   `/pre-market`, `/market-open`, `/midday`, `/daily-summary`,
   `/weekly-review`.

## How it works

- **Memory lives in Git.** Every piece of state — strategy rules, trade
  history, research, weekly reviews — is a markdown file in `memory/`,
  committed to `main`. There is no database.
- **Three wrapper scripts** (`scripts/alpaca.sh`, `scripts/perplexity.sh`,
  `scripts/telegram.sh`) are the only way the agent touches the outside
  world. Never call these APIs with raw `curl`.
- **Cloud routines** (`routines/*.md`) are the production path: five prompts
  pasted verbatim into Claude Code cloud routines, cron-scheduled on
  weekdays. Each firing is a fresh, stateless container — if it doesn't
  `git commit && git push`, it didn't happen.

## Setting up cloud routines

Cloud routine creation happens in the Claude Code web UI (not something this
CLI session can do for you). For each of the five prompts in `routines/`:

1. Routines → New Routine, select this repo, branch `main`.
2. Add the env vars listed at the top of that routine's env-check block.
3. Enable "Allow unrestricted branch pushes" (without it, `git push` fails
   silently).
4. Set the cron schedule (see `routines/README.md` for the five schedules).
5. Paste the routine's `.md` file contents verbatim into the prompt field.
6. Save, then click "Run now" once to verify before trusting the schedule.
