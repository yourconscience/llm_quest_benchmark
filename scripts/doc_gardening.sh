#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
FORMAT="${2:-markdown}"

uv run python skills/doc-gardening/scripts/stale_docs_scan.py --root "${ROOT}" --format "${FORMAT}"
