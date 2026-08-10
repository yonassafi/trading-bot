---
description: Read-only snapshot of account, positions, open orders, stops, and QMS-01 risk budget
---

Print a clean ad-hoc snapshot. No state changes, no orders, no file writes.

1. bash scripts/halt.sh check (report halt state if any — read-only)
2. bash scripts/alpaca.sh account
3. bash scripts/alpaca.sh positions
4. bash scripts/alpaca.sh orders
5. Read memory/POSITIONS.json and memory/RISK-STATE.json

Format the output as a single concise summary:

Portfolio — <today's date>
Equity: $X | Cash: $X (X%) | Buying power: $X
Halt state: <none | HALTED: reason>

Positions: N/5 (QMS-01 Section 10 cap)
  SYM | Sh | Entry -> Now | Unrealized P&L | Stop
Total open risk: X.X% of equity (cap: 3.0%)

Open orders:
  TYPE | SYM | qty | stop/limit | order_id

Drawdown from peak: X.X% (halt threshold: 25.0%)

No commentary unless something is broken (position without a resting
stop, a stop above current price on a long, or open risk/position count
already at or over the QMS-01 caps).
