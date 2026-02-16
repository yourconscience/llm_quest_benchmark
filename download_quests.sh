#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUESTS_DIR="${ROOT_DIR}/quests"
UPSTREAM_GIT_URL="https://gitlab.com/spacerangers/spacerangers.gitlab.io.git"
UPSTREAM_ZIP_URL="https://gitlab.com/spacerangers/spacerangers.gitlab.io/-/archive/master/spacerangers.gitlab.io-master.zip"

declare -a QUEST_MAP=(
  "SR 2.1.2121 eng|sr_2_1_2121_eng"
  "SR 2.1.2170|sr_2_1_2170_ru"
  "КР 1|kr_1_ru"
  "КР 2 2.1.2369|sr_2_2_1_2369_ru"
  "КР 2 Доминаторы|sr_2_dominators_ru"
  "КР 2 Доминаторы HD Революция Оригинальные|sr_2_revolution_ru"
  "КР 2 Доминаторы HD Революция Фанатские|sr_2_revolution_fan_ru"
  "КР 2 Доминаторы Перезагрузка|sr_2_reboot_ru"
  "Фанатские|fanmade_ru"
)

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

download_upstream_from_zip() {
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

  echo "Extracting quests archive with Python zipfile (UTF-safe)..."
  python - "$zip_path" "$TMP_DIR" <<'PY'
import sys
import zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
target_dir = Path(sys.argv[2])
with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(target_dir)
PY
}

download_upstream_from_git() {
  local repo_dir="${TMP_DIR}/spacerangers.gitlab.io"
  echo "Cloning quest source from GitLab..."
  git clone --depth 1 --filter=blob:none --sparse "${UPSTREAM_GIT_URL}" "${repo_dir}"
  git -C "${repo_dir}" sparse-checkout set borrowed/qm
}

copy_collection_qm_files() {
  local source_dir="$1"
  local target_dir="$2"
  mkdir -p "${target_dir}"

  # Some collections are nested one level deeper with the same directory name.
  local nested_dir="${source_dir}/$(basename "${source_dir}")"
  if [[ -d "${nested_dir}" ]]; then
    source_dir="${nested_dir}"
  fi

  local copied=0
  while IFS= read -r -d '' qm_file; do
    local base_name
    base_name="$(basename "${qm_file}")"
    local target_file="${target_dir}/${base_name}"

    if [[ -f "${target_file}" ]]; then
      local stem ext n
      stem="${base_name%.*}"
      ext=".${base_name##*.}"
      n=2
      while [[ -f "${target_dir}/${stem}__${n}${ext}" ]]; do
        n=$((n + 1))
      done
      target_file="${target_dir}/${stem}__${n}${ext}"
    fi

    cp -f "${qm_file}" "${target_file}"
    copied=$((copied + 1))
  done < <(find "${source_dir}" -type f \( -name '*.qm' -o -name '*.qmm' \) -print0 | sort -z)
  done < <(find "${source_dir}" -type f \( -name '*.qm' -o -name '*.qmm' \) -print0 | sort -z)

  printf '%s' "${copied}"
}

SOURCE_QM_ROOT=""
if [[ "${REFRESH}" -eq 0 && -d "${QUESTS_DIR}/spacerangers.gitlab.io/borrowed/qm" ]]; then
  echo "Using existing source tree from quests/spacerangers.gitlab.io/borrowed/qm"
  cp -R "${QUESTS_DIR}/spacerangers.gitlab.io/borrowed/qm" "${TMP_DIR}/qm_source"
  SOURCE_QM_ROOT="${TMP_DIR}/qm_source"
else
  if command -v git >/dev/null 2>&1; then
    download_upstream_from_git
    SOURCE_QM_ROOT="${TMP_DIR}/spacerangers.gitlab.io/borrowed/qm"
  else
    download_upstream_from_zip
    SOURCE_QM_ROOT="${TMP_DIR}/spacerangers.gitlab.io-master/borrowed/qm"
  fi
fi

if [[ ! -d "${SOURCE_QM_ROOT}" ]]; then
  echo "Error: source qm directory not found: ${SOURCE_QM_ROOT}" >&2
  exit 1
fi

echo "Rebuilding quests directory with flat normalized layout..."
find "${QUESTS_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

TOTAL=0
for mapping in "${QUEST_MAP[@]}"; do
  source_name="${mapping%%|*}"
  target_name="${mapping##*|}"
  source_path="${SOURCE_QM_ROOT}/${source_name}"
  target_path="${QUESTS_DIR}/${target_name}"

  if [[ ! -d "${source_path}" ]]; then
    echo "Warning: source collection missing, creating empty dir: ${source_name} -> ${target_name}" >&2
    mkdir -p "${target_path}"
    continue
  fi

  copied="$(copy_collection_qm_files "${source_path}" "${target_path}")"
  TOTAL=$((TOTAL + copied))
  echo "Prepared ${target_name} (${copied} files)"
done

# Keep a simple default smoke quest path for quick CLI checks.
if [[ -f "${QUESTS_DIR}/kr_1_ru/Boat.qm" ]]; then
  cp -f "${QUESTS_DIR}/kr_1_ru/Boat.qm" "${QUESTS_DIR}/Boat.qm"
fi

echo "Quest setup complete."
echo "Total copied quest files (.qm/.qmm): ${TOTAL}"
echo "Collections:"
for mapping in "${QUEST_MAP[@]}"; do
  echo "  - ${mapping##*|}"
done
