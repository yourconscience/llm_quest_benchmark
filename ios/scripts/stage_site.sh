#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)

if [ -z "${SOURCE_SITE:-}" ]; then
  if [ -n "${SRCROOT:-}" ]; then
    SOURCE_SITE="${SRCROOT}/../site"
  else
    SOURCE_SITE="${SCRIPT_DIR}/../../site"
  fi
fi

if [ -z "${DEST_SITE:-}" ]; then
  if [ -z "${TARGET_BUILD_DIR:-}" ] || [ -z "${UNLOCALIZED_RESOURCES_FOLDER_PATH:-}" ]; then
    echo "DEST_SITE or Xcode build destination variables are required." >&2
    exit 1
  fi
  DEST_SITE="${TARGET_BUILD_DIR}/${UNLOCALIZED_RESOURCES_FOLDER_PATH}/site"
fi

if [ ! -f "${SOURCE_SITE}/play.html" ]; then
  echo "Missing ${SOURCE_SITE}/play.html. Run pnpm run build before archiving." >&2
  exit 1
fi

mkdir -p "$(dirname "${DEST_SITE}")"
rm -rf "${DEST_SITE}"
mkdir -p "${DEST_SITE}/play"

cp "${SOURCE_SITE}/play.html" "${DEST_SITE}/play.html"
cp "${SOURCE_SITE}/play/app.js" "${DEST_SITE}/play/app.js"
cp "${SOURCE_SITE}/play/qmengine.js" "${DEST_SITE}/play/qmengine.js"
cp "${SOURCE_SITE}/play/qmengine.js.LICENSE.txt" "${DEST_SITE}/play/qmengine.js.LICENSE.txt"

find "${SOURCE_SITE}/play" -maxdepth 1 -type f -name "*.json" -exec cp {} "${DEST_SITE}/play/" \;

for directory in questplay quests vendor; do
  cp -R "${SOURCE_SITE}/play/${directory}" "${DEST_SITE}/play/"
done

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
