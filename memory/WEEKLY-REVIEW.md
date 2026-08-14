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

---

## Week ending 2026-08-14

### Stats
| Metric | Value |
|--------|-------|
| Starting equity | $100,000.00 |
| Ending equity | $100,000.00 |
| Week return | $0.00 (0.00%) |
| Trades this week | 0 (entries: 0, exits: 0) |
| Open positions | 0/5 |
| Total open risk | 0.0% of equity |

Halt state: clear (`scripts/halt.sh check` exit 0, no `memory/HALT.md`).
Broker state at Friday close: `equity 100000`, `cash 100000`,
`long_market_value 0`, `positions []` (paper account PA3K1AR3CU5S,
`balance_asof 2026-08-13`).

Starting equity is the Day 0 pre-launch baseline in
`memory/TRADE-LOG.md`; ending equity is the live account pull. See the
first observation below — no EOD snapshots exist in the trade log for
this week, so the week's equity path could not be read from the log as
STEP 4 assumes.

### Closed Trades This Week
| Ticker | Entry | Exit | R-multiple | Days Held | Exit Rule |
|--------|-------|------|------------|-----------|-----------|
| _none_ | — | — | — | — | — |

### Distribution Tracking (Section 11, running since inception)
| Metric | Value |
|--------|-------|
| Total closed trades | 0 |
| Win rate | n/a — no closed trades |
| Average winning R | n/a — no closed trades |
| Average losing R | n/a — no closed trades |
| Largest winning R | n/a — no closed trades |
| % of total profit from single best trade | n/a — no closed trades |

`memory/POSITIONS.json` is `{"open": {}, "closed": []}`. Every
distribution metric is undefined; none has been estimated or substituted.

**Tail check (Section 11):** cannot be computed — there is no winner and
no average winner. No conclusion is drawn about whether exits cut the
tail. Reported, not acted on.

### Exceptions This Week
11 entries in `memory/EXCEPTIONS-LOG.md` dated this week (10 on
2026-08-10 / 2026-08-11; none 08-12 or 08-13; one logged by this review
on 08-14).

Section 11 classes:
- `UNSPECIFIED_SITUATION` — 4 (one a recurrence, one logged by this run)
- `STOP_TOO_WIDE` — 0
- HALT — 0
- OTHER / defect — 7

Pointers:
1. 2026-08-10 21:00 ET — UNSPECIFIED_SITUATION — `screener.py` exited 1
   on `account_equity()`, curl 403 from the proxy egress block.
2. 2026-08-10 21:00 ET — OTHER — pre-market fired 21:00 ET vs the
   `0 7 * * 1-5` ET slot; cron appears set in UTC.
3. 2026-08-10 21:14 ET — UNSPECIFIED_SITUATION (recurrence) — identical
   403 egress failure to entry 1.
4. 2026-08-10 21:25 ET — UNSPECIFIED_SITUATION — one universe symbol
   dropped with no disqualifying rule recorded; symbol not captured.
5. 2026-08-10 21:26 ET — OTHER — Telegram Step 5 alert 400, from
   `parse_mode: Markdown` in `scripts/telegram.sh`.
6. 2026-08-10 21:31 ET — OTHER — duplicate screener section from two
   off-schedule runs ~2 minutes apart.
7. 2026-08-10 21:33 ET — OTHER — push rejected on detached HEAD; the
   documented `pull --rebase` recovery does not fix it.
8. 2026-08-11 — DEFECT — `routines/daily-summary.md` STEP 7 hardcoded
   phase-P&L starting equity of 10000, 10x low vs the funded 100000.
9. 2026-08-11 03:01 ET — OTHER — market-open fired 03:01 ET, before the
   09:30-10:00 opening range existed; no trading impact (0 candidates).
10. 2026-08-11 — DEFECT — Section 6.1 tie-break degenerated the
    consolidation window (H = most recent qualifying bar, not the
    impulse peak).
11. 2026-08-14 17:15 ET — UNSPECIFIED_SITUATION — `memory/TRADING-STRATEGY.md`
    still carries the pre-amendment §15 ("`market-open` DISABLED, do not
    re-enable without real-time SIP"; 10:20 ET "rejected"; 10:05
    stop-limit approximation) while `docs/` §15 lifted the suspension for
    the amended confirmed-hold market entry and adopted 10:20 ET. Logged
    by this run per CLAUDE.md; `docs/` wins, neither file touched.

### Observations (reporting only — no action taken, no rule changed)
- **No EOD snapshots this week.** `memory/TRADE-LOG.md` still contains
  only the Day 0 pre-launch baseline. STEP 4 of `routines/weekly-review.md`
  sources the week's equity path from this week's EOD snapshots, and
  there are none, so equity was taken from the Day 0 baseline and the
  live account instead. `memory/RISK-STATE.json` likewise still has
  `peak_equity_date: null` and `last_updated_date: null`, i.e. no
  `daily-summary` run has committed. Recorded as an observation, not a
  change.
- **Zero entries is the expected outcome, not a screener miss.**
  `market-open` remains **disabled** per §15's "Suspension lifted for the
  amended §8 — 2026-08-11 (b)": the confirmed-hold market entry rule is
  executable on free SIP, but re-enabling is a deliberate operator act
  pending end-to-end verification. Nothing here is a rule to apply.
- **Screener ran all four sessions with regime PASS.** Stage B counts:
  08-11 = 1 (FBRX), 08-12 = 1, 08-13 = 1, 08-14 = 0. Universe 5909-5911,
  Stage A 1068-1109. Pipeline produced candidates every day; no entry
  could follow while §8 is disabled.
- **Mirror drift on §15 (logged as UNSPECIFIED_SITUATION, exception 11).**
  `memory/TRADING-STRATEGY.md` still states the original §15 suspension
  and its "do not re-enable without real-time SIP" / "10:20 ET rejected"
  terms; `docs/` §15 supersedes both. No trading impact — `market-open`
  is disabled under either text. Neither file was edited. The "Known Gaps
  Reminder" below is restated verbatim by instruction and therefore still
  names "IEX-feed volume", though the screener moved to `feed=sip` on
  2026-08-11; it is reprinted unchanged rather than silently corrected.
- **Distribution tracking has no data yet.** Section 11's running record
  starts at the first closed trade. Until then the tail check that
  Section 1 depends on cannot say anything either way.

### Known Gaps Reminder
No earnings filtering, no sector cap, IEX-feed volume, best-effort
ADR/common-stock filtering, retrospective entry approximation — see
`memory/TRADING-STRATEGY.md` for full detail. Restated here each week so
they're never mistaken for having been silently fixed.
