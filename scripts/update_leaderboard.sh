#!/usr/bin/env bash
# Update site/leaderboard.json and print a summary table to stdout.
# Usage: ./scripts/update_leaderboard.sh [--benchmark-dir DIR] [--benchmark-dir DIR] ...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_DIR}"

# Collect --benchmark-dir args
DIRS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --benchmark-dir)
      DIRS+=("--benchmark-dir" "$2")
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Default: all CLI_benchmark_* dirs under results/benchmarks/
if [[ ${#DIRS[@]} -eq 0 ]]; then
  for d in results/benchmarks/CLI_benchmark_*/; do
    [[ -d "$d" ]] && DIRS+=("--benchmark-dir" "$d")
  done
fi

if [[ ${#DIRS[@]} -eq 0 ]]; then
  echo "No benchmark directories found." >&2
  exit 1
fi

uv run llm-quest leaderboard "${DIRS[@]}"

# Print summary table from the generated JSON
python3 - <<'EOF'
import json, sys
from pathlib import Path

path = Path("site/leaderboard.json")
if not path.exists():
    print("site/leaderboard.json not found", file=sys.stderr)
    sys.exit(1)

data = json.loads(path.read_text())
results = data.get("results", [])

# Aggregate by model
from collections import defaultdict
agg = defaultdict(lambda: {"runs": 0, "wins": 0, "cost": 0.0})
for row in results:
    m = row["model"]
    runs = row["runs"]
    wins = round(row["success_rate"] * runs)
    agg[m]["runs"] += runs
    agg[m]["wins"] += wins
    agg[m]["cost"] += row["avg_cost_usd"] * runs

header = f"{'model':<40} {'runs':>6} {'wins':>6} {'success%':>9} {'cost_usd':>10}"
print(header)
print("-" * len(header))
for model, v in sorted(agg.items(), key=lambda x: -x[1]["wins"] / max(x[1]["runs"], 1)):
    runs = v["runs"]
    wins = v["wins"]
    pct = 100.0 * wins / runs if runs else 0.0
    cost = v["cost"]
    print(f"{model:<40} {runs:>6} {wins:>6} {pct:>8.1f}% {cost:>10.4f}")
EOF
