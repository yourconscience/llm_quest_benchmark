#!/usr/bin/env bash
set -euo pipefail

SKILL_SCRIPT="${HOME}/.codex/skills/doc-gardening/scripts/doc_garden.py"
MODE="${1:-audit}"
ROOT="${2:-.}"
FORMAT="${3:-markdown}"

if [[ ! -f "${SKILL_SCRIPT}" ]]; then
  echo "Global doc-gardening skill is not installed: ${SKILL_SCRIPT}" >&2
  echo "Install/create ~/.codex/skills/doc-gardening first." >&2
  exit 1
fi

case "${MODE}" in
  audit)
    python3 "${SKILL_SCRIPT}" audit --root "${ROOT}" --format "${FORMAT}"
    ;;
  init)
    python3 "${SKILL_SCRIPT}" init --root "${ROOT}"
    ;;
  *)
    echo "Usage: ./scripts/doc_gardening.sh [audit|init] [root] [format]" >&2
    exit 2
    ;;
esac
