# Exceptions Log — QMS-01 Breakout v1.1-paper

Per `memory/TRADING-STRATEGY.md` Section 11: "the most valuable records
the system produces." Every `UNSPECIFIED_SITUATION`, `STOP_TOO_WIDE`,
HALT event, and any instance of uncertainty about applying a rule is
logged here — never silently resolved by the agent's own judgement.

QMS-01 has no research step (unlike the prior strategy this repo used to
run) — this file replaces what was `RESEARCH-LOG.md`.

Format each entry:

## YYYY-MM-DD HH:MM ET — <UNSPECIFIED_SITUATION | STOP_TOO_WIDE | HALT | other>
**Routine:** pre-market | market-open | daily-summary | weekly-review
**Symbol (if applicable):**
**What happened:**
**Rule that doesn't cover this / was ambiguous:**
**Action taken:** (should almost always be "none" for UNSPECIFIED_SITUATION,
per Section 0.3 — absence of a rule means do nothing)
