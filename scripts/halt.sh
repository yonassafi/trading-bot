#!/usr/bin/env bash
# QMS-01 Section 12 kill-switch. memory/HALT.md absent = normal operation.
# Usage: bash scripts/halt.sh check
#   exit 0, no output  -> not halted, proceed normally
#   exit 1, prints reason -> halted, routine must alert and stop (no
#     trading, no position management — Section 12: "stop trading, close
#     nothing, report")
#
# Only a human clears this (.claude/commands/resume.md). No routine may
# ever delete memory/HALT.md itself.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HALT_FILE="$ROOT/memory/HALT.md"

cmd="${1:-check}"

case "$cmd" in
  check)
    if [[ -f "$HALT_FILE" ]]; then
      echo "HALTED. Contents of memory/HALT.md:" >&2
      cat "$HALT_FILE" >&2
      exit 1
    fi
    exit 0
    ;;
  *)
    echo "Usage: bash scripts/halt.sh check" >&2
    exit 1
    ;;
esac
