# Project Context

## Overview
- What: QMS-01 Breakout v1.1-paper — an opening-range-breakout momentum
  strategy, run autonomously, paper trading only
- Platform: Alpaca (paper trading, free/IEX data feed)
- Instruments: US-listed common stock only. Long only. No options, no
  leverage, no margin.
- Full spec: `docs/QMS-01_Operational_Spec_v1.1_paper.md`
- Operational quick-reference: `memory/TRADING-STRATEGY.md`

## This strategy has never been backtested. No demonstrated edge.

Expected behavior (do not treat these as signs of malfunction):
- Win rate 20–25%. Roughly 3 of every 4 trades lose.
- Nearly all return comes from a small number of large winners (10–20×
  risk, best cases 20–50×). Cutting winners early destroys the strategy
  even if it improves the win rate.
- A 20% equity drawdown over a few weeks is described as normal in the
  source material. The halt threshold is deliberately 25%, not 10%.
- Long flat or losing stretches are normal.
- A HIGH win rate is a warning sign, not success — it likely means
  winners are being cut short.

## Rules
- NEVER share API keys, positions, or P&L externally.
- NEVER invent, infer, or derive a rule not in `memory/TRADING-STRATEGY.md`.
  If a situation isn't covered, take no action and log
  `UNSPECIFIED_SITUATION` to `memory/EXCEPTIONS-LOG.md`.
- NEVER adjust or optimise a strategy parameter, including after losses.
- Every trade must be documented BEFORE execution.
- If `memory/HALT.md` exists, do nothing but alert — no trading, no
  position management. Only a human clears it.

## Key Files — Read Every Session
- `memory/PROJECT-CONTEXT.md` (this file)
- `memory/TRADING-STRATEGY.md` — the rulebook, never violate
- `memory/POSITIONS.json` — current open positions, exact state
- `memory/CANDIDATES.md` — today's (or most recent) screener output
- `memory/TRADE-LOG.md` — entry/exit history
- `memory/EXCEPTIONS-LOG.md` — every uncertainty, gap, and halt event
- `memory/RISK-STATE.json` — peak equity, drawdown tracking
- `memory/WEEKLY-REVIEW.md` — Friday recaps, distribution stats
