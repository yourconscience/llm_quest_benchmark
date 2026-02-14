#!/usr/bin/env bash
set -euo pipefail

# Run baseline + prompt variants and emit a combined markdown report.
# Usage:
#   ./scripts/run_provider_matrix.sh
#   ./scripts/run_provider_matrix.sh results/benchmarks/report_provider_matrix.md

REPORT_PATH="${1:-results/benchmarks/report_provider_matrix.md}"
BENCHMARK_DIR="results/benchmarks"

CONFIGS=(
  "configs/benchmarks/provider_suite_matrix_reasoning.yaml"
  "configs/benchmarks/provider_suite_matrix_consequence.yaml"
  "configs/benchmarks/provider_suite_matrix_objective.yaml"
)

mkdir -p "$(dirname "$REPORT_PATH")"

declare -a BENCHMARK_IDS=()

for cfg in "${CONFIGS[@]}"; do
  echo "Running benchmark: $cfg"
  uv run llm-quest benchmark --config "$cfg"
  latest_id="$(ls -1t "$BENCHMARK_DIR" | head -n 1)"
  BENCHMARK_IDS+=("$latest_id")
  echo "Captured benchmark ID: $latest_id"
done

declare -a REPORT_CMD=("uv" "run" "llm-quest" "benchmark-report")
for id in "${BENCHMARK_IDS[@]}"; do
  REPORT_CMD+=("--benchmark-id" "$id")
done
REPORT_CMD+=("--output" "$REPORT_PATH")

echo "Generating report: $REPORT_PATH"
"${REPORT_CMD[@]}"
echo "Done. Benchmarks: ${BENCHMARK_IDS[*]}"
