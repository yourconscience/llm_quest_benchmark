#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUESTS_DIR="${ROOT_DIR}/quests"
UPSTREAM_ZIP_URL="https://gitlab.com/spacerangers/spacerangers.gitlab.io/-/archive/master/spacerangers.gitlab.io-master.zip"
UPSTREAM_ROOT="${QUESTS_DIR}/spacerangers.gitlab.io"
UPSTREAM_QM_DIR="${UPSTREAM_ROOT}/borrowed/qm"

REFRESH=0
if [[ "${1:-}" == "--refresh" ]]; then
  REFRESH=1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${QUESTS_DIR}"

download_upstream() {
  echo "Downloading quests archive from GitLab..."
  local zip_path="${TMP_DIR}/spacerangers.gitlab.io-master.zip"
  if command -v curl >/dev/null 2>&1; then
    curl -L "${UPSTREAM_ZIP_URL}" -o "${zip_path}"
  elif command -v wget >/dev/null 2>&1; then
    wget "${UPSTREAM_ZIP_URL}" -O "${zip_path}"
  else
    echo "Error: either curl or wget is required." >&2
    exit 1
  fi

  echo "Extracting quests archive..."
  unzip -q "${zip_path}" -d "${TMP_DIR}"

  rm -rf "${UPSTREAM_ROOT}"
  mv "${TMP_DIR}/spacerangers.gitlab.io-master" "${UPSTREAM_ROOT}"
}

link_or_copy_alias() {
  local source_rel="$1"
  local alias_rel="$2"
  local source_path="${QUESTS_DIR}/${source_rel}"
  local alias_path="${QUESTS_DIR}/${alias_rel}"

  if [[ ! -d "${source_path}" ]]; then
    echo "Warning: source path not found, skipping alias ${alias_rel}: ${source_rel}" >&2
    return
  fi

  rm -rf "${alias_path}"
  (
    cd "${QUESTS_DIR}"
    if ln -s "${source_rel}" "${alias_rel}" 2>/dev/null; then
      return
    fi
  )

  # Filesystem does not support symlinks (or permissions forbid): fallback to copy.
  cp -R "${source_path}" "${alias_path}"
}

if [[ "${REFRESH}" -eq 1 || ! -d "${UPSTREAM_QM_DIR}" ]]; then
  download_upstream
else
  echo "Using existing quest tree at ${UPSTREAM_QM_DIR}"
fi

echo "Preparing normalized quest aliases..."
link_or_copy_alias "spacerangers.gitlab.io/borrowed/qm/КР 1" "kr_1_ru"
link_or_copy_alias "spacerangers.gitlab.io/borrowed/qm/SR 2.1.2121 eng" "sr_2_1_2121_eng"

# Optional compatibility aliases for older configs.
link_or_copy_alias "kr_1_ru" "kr1"
link_or_copy_alias "sr_2_1_2121_eng" "kr_2_en"

# Keep legacy root smoke quest available for quick commands.
if [[ -f "${QUESTS_DIR}/kr_1_ru/Boat.qm" ]]; then
  cp -f "${QUESTS_DIR}/kr_1_ru/Boat.qm" "${QUESTS_DIR}/Boat.qm"
fi

echo "Quest setup complete."
echo "Total .qm files under ${QUESTS_DIR}: $(find "${QUESTS_DIR}" -type f -name '*.qm' | wc -l | tr -d ' ')"
echo "Normalized aliases:"
echo "  - ${QUESTS_DIR}/kr_1_ru"
echo "  - ${QUESTS_DIR}/sr_2_1_2121_eng"
