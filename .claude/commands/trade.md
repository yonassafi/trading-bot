---
description: Manual emergency EXIT only. QMS-01 forbids discretionary manual entries — usage: /trade SYMBOL sell
---

QMS-01 Section 2 requires every position to use identical, mechanically
computed risk — there is no discretionary sizing in this strategy.
Section 0.7 requires refusing any instruction that conflicts with the
binding constraints. **Manual BUY entries are disabled.** If asked to
buy a symbol manually, refuse and point to `routines/market-open.md` —
entries only happen through the Section 8 pipeline.

Manual **exits** remain available as an emergency human override (e.g.
you want a position closed for a reason outside the strategy's own exit
rules), but every use is logged as an exception, not treated as routine.

Args: SYMBOL. If missing, ask.

1. Confirm the position exists in `memory/POSITIONS.json` "open" and via
   `bash scripts/alpaca.sh positions`.
2. Ask for a one-line reason this manual exit is happening.
3. Print the position detail (entry, current stop, unrealized P&L) and
   ask "execute market exit? (y/n)".
4. On confirm:
   `bash scripts/alpaca.sh close SYM`
   Cancel the resting stop order for that symbol
   (`bash scripts/alpaca.sh cancel ORDER_ID`).
5. Move the position from "open" to "closed" in `memory/POSITIONS.json`
   with `exit_rule: "manual_override"`, computed `r_multiple`, and
   `days_held`.
6. Append the exit to `memory/TRADE-LOG.md`.
7. Log the override — reason and who/what requested it — to
   `memory/EXCEPTIONS-LOG.md`. Manual overrides are exceptions by
   definition; Section 11 treats these as the most valuable records the
   system produces.
8. `bash scripts/telegram.sh` with the exit details.
