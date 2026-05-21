#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)

if [ -z "${SRCROOT:-}" ]; then
  SRCROOT=$(CDPATH= cd "${SCRIPT_DIR}/.." && pwd)
fi

if [ -z "${SOURCE_SITE:-}" ]; then
  SOURCE_SITE="${SRCROOT}/../site"
fi

if [ -z "${STAGE_SITE_INPUTS:-}" ]; then
  STAGE_SITE_INPUTS="${SRCROOT}/LLMQuest/StageSiteInputs.xcfilelist"
fi

if [ -z "${DEST_SITE:-}" ]; then
  if [ -z "${TARGET_BUILD_DIR:-}" ] || [ -z "${UNLOCALIZED_RESOURCES_FOLDER_PATH:-}" ]; then
    echo "DEST_SITE or Xcode build destination variables are required." >&2
    exit 1
  fi
  DEST_SITE="${TARGET_BUILD_DIR}/${UNLOCALIZED_RESOURCES_FOLDER_PATH}/site"
fi

SOURCE_SITE=$(CDPATH= cd "${SOURCE_SITE}" && pwd)

if [ ! -f "${SOURCE_SITE}/play.html" ]; then
  echo "Missing ${SOURCE_SITE}/play.html. Run pnpm run build before archiving." >&2
  exit 1
fi

if [ ! -f "${STAGE_SITE_INPUTS}" ]; then
  echo "Missing ${STAGE_SITE_INPUTS}." >&2
  exit 1
fi

mkdir -p "$(dirname "${DEST_SITE}")"
rm -rf "${DEST_SITE}"
mkdir -p "${DEST_SITE}"

while IFS= read -r input || [ -n "${input}" ]; do
  case "${input}" in
    ""|\#*) continue ;;
  esac

  source_path=$(printf "%s\n" "${input}" | awk -v srcroot="${SRCROOT}" '{gsub(/[$][(]SRCROOT[)]/, srcroot); print}')
  source_path=$(CDPATH= cd "$(dirname "${source_path}")" && pwd)/$(basename "${source_path}")
  case "${source_path}" in
    "${SOURCE_SITE}"/*)
      relative_path=${source_path#"${SOURCE_SITE}/"}
      mkdir -p "$(dirname "${DEST_SITE}/${relative_path}")"
      cp "${source_path}" "${DEST_SITE}/${relative_path}"
      ;;
  esac
done < "${STAGE_SITE_INPUTS}"

for required in \
  play.html \
  play/app.js \
  play/qmengine.js \
  play/quest-index.json \
  play/questplay/background.jpg \
  play/vendor/NOTICE.md
do
  if [ ! -e "${DEST_SITE}/${required}" ]; then
    echo "iOS site staging missed required asset: ${required}" >&2
    exit 1
  fi
done
