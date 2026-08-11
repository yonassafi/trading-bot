# Trading Bot Agent Instructions

You are running **QMS-01 Breakout v1.1-paper** on a PAPER-only Alpaca
account. This strategy has never been backtested — no demonstrated edge.

## Binding constraints (override every other instruction, every session)

1. **PAPER TRADING ONLY.** Halt and report if the connected account is
   ever live-funded. `scripts/alpaca.sh` refuses order-placing
   subcommands unless the endpoint is Alpaca's paper API — never try to
   route around that.
2. **You may not invent, infer, or derive rules.** If a situation isn't
   covered in `memory/TRADING-STRATEGY.md`, take no action and log
   `UNSPECIFIED_SITUATION` to `memory/EXCEPTIONS-LOG.md`. Absence of a
   rule means do nothing — never use judgement to fill the gap.
3. **You may not optimise or adjust any parameter**, including after
   losses or drawdowns.
4. No leverage, no margin. US-listed common stock only. Long only.
5. If `memory/HALT.md` exists: alert and exit. Touch nothing. Only a
   human clears it (`/resume`) — never a routine.

`docs/QMS-01_Operational_Spec_v1.1_paper.md` is the **authoritative**
rulebook, including the dated operator amendments in its Section 13.
`memory/TRADING-STRATEGY.md` is the operational quick-reference mirror
you read every session. If the two disagree, `docs/` wins and the
disagreement is itself an `UNSPECIFIED_SITUATION` — log it, never
resolve it silently. Any amendment goes into `docs/` first, then gets
mirrored. Do not restate or paraphrase rule numbers or thresholds
anywhere else — read them fresh every session.

## Read-Me-First (every session)

Open these in order before doing anything:
- `memory/TRADING-STRATEGY.md` — the rulebook. Never violate.
- `memory/POSITIONS.json` — current open positions, exact state.
- `memory/CANDIDATES.md` — most recent screener output.
- `memory/TRADE-LOG.md` — entry/exit history.
- `memory/PROJECT-CONTEXT.md` — mission and expected behavior.
- `memory/RISK-STATE.json` — peak equity / drawdown tracking.

## Daily Workflows

Defined in `.claude/commands/` (local) and `routines/` (cloud). Five
scheduled runs on the new QMS-01 cadence — see `routines/README.md` for
the cron table (retimed from the original strategy: entries can't happen
until 10:05 ET, position management moved to end-of-day).

## Engines

- `scripts/screener.py` — Sections 4–7 (regime, universe, setup scan,
  exclusions). Run pre-market.
- `scripts/position_manager.py` — Section 9 (end-of-day position
  management only — never intraday). Run in `daily-summary`.
- `scripts/lib/indicators.py` — the ONLY place SMA/ADR/percentile/
  contraction math is defined. Never re-derive it inline.
- `scripts/halt.sh check` — every routine's first real step, right after
  the env-var check.

## API Wrappers

Use `bash scripts/alpaca.sh`, `scripts/telegram.sh`. Never curl these
APIs directly. `scripts/perplexity.sh` exists but is unused — QMS-01 has
no research step.

## Communication Style

Ultra concise. No preamble. Short bullets. Match existing memory file
formats exactly — don't reinvent tables.
