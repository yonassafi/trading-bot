# Trade Log — QMS-01 Breakout v1.1-paper

Schema per `memory/TRADING-STRATEGY.md` Section 11. Entries and exits are
appended here; the authoritative machine-readable state for open
positions lives in `memory/POSITIONS.json`.

## Entry format
```
### YYYY-MM-DD — ENTRY SYMBOL
Timestamp: HH:MM:SS ET | ORH: $X | Fill: $X | Stop: $X
Risk/share: $X | Shares: N | Account risk: X.XX% | Equity: $X
Reference SMA: N | Portfolio state: N/5 positions, X.X% total open risk
Entry mechanism: retrospective_10ET_approximation
```

## Exit format
```
### YYYY-MM-DD — EXIT SYMBOL
Timestamp: HH:MM:SS ET | Price: $X | Triggering rule: <stop|stop_too_wide|partial|trailing_sma>
R-multiple: X.XX | Days held: N
```

## Daily EOD snapshot format
```
### YYYY-MM-DD — EOD Snapshot
Regime: PASS/FAIL | Equity: $X | Day P&L: ±$X (±X%) | Phase P&L: ±$X (±X%)
Open positions: N/5 | Total open risk: X.X% of equity
Entries today: N | Trades this week: N
```

---

## Day 0 — EOD Snapshot (pre-launch baseline)
**Equity:** $10,000.00 | **Cash:** $10,000.00 (100%) | **Day P&L:** $0 | **Phase P&L:** $0

No positions yet. QMS-01 launches tomorrow. NOTE: as of this commit, the
connected Alpaca paper account still shows its default $100,000 balance —
reset it to $10,000 via the Alpaca paper dashboard before the first real
`pre-market`/`market-open` run, or `daily-summary`'s Day P&L math on day
one will be off by the difference.
