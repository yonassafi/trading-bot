# Weekly Review — QMS-01 Breakout v1.1-paper

Friday reviews appended here. Per Section 0.4, this file **never**
proposes or makes strategy adjustments — reporting only. Per Section
0.3/0.4, no rule or parameter in `memory/TRADING-STRATEGY.md` is ever
changed based on these results.

Template for each entry:

## Week ending YYYY-MM-DD

### Stats
| Metric | Value |
|--------|-------|
| Starting equity | $X |
| Ending equity | $X |
| Week return | ±$X (±X%) |
| Trades this week | N (entries: N, exits: N) |
| Open positions | N/5 |
| Total open risk | X.X% of equity |

### Closed Trades This Week
| Ticker | Entry | Exit | R-multiple | Days Held | Exit Rule |

### Distribution Tracking (Section 11, running since inception)
| Metric | Value |
|--------|-------|
| Total closed trades | N |
| Win rate | X% |
| Average winning R | X.XXR |
| Average losing R | X.XXR |
| Largest winning R | X.XXR |
| % of total profit from single best trade | X% |

**Tail check (Section 11):** is the largest winner several times the
average winner? If not, report it plainly — it may mean exits are
cutting the tail. Do not act on this observation; report only.

### Exceptions This Week
Count of `UNSPECIFIED_SITUATION` / `STOP_TOO_WIDE` / HALT events logged
to `memory/EXCEPTIONS-LOG.md` this week, with a one-line pointer to each.

### Known Gaps Reminder
No earnings filtering, no sector cap, IEX-feed volume, best-effort
ADR/common-stock filtering, retrospective entry approximation — see
`memory/TRADING-STRATEGY.md` for full detail. Restated here each week so
they're never mistaken for having been silently fixed.
