#!/bin/bash
# data-snapshot 브랜치에서 JSON 파일들을 받아옴 (없으면 main의 seed로 fallback)
# 사용법: bash scripts/fetch_from_snapshot.sh listed_stocks.json industry_mapping.json
set -e

if [ -z "$GH_REPO" ]; then
  echo "ERROR: GH_REPO 환경변수 없음"
  exit 1
fi

mkdir -p data

for FILENAME in "$@"; do
  URL_SNAP="https://raw.githubusercontent.com/${GH_REPO}/data-snapshot/${FILENAME}"
  URL_MAIN="https://raw.githubusercontent.com/${GH_REPO}/main/data/${FILENAME}"

  if curl -fsSL "$URL_SNAP" -o "data/${FILENAME}" 2>/dev/null && [ -s "data/${FILENAME}" ]; then
    SIZE=$(stat -c%s "data/${FILENAME}")
    echo "  [fetch] $FILENAME from data-snapshot ($SIZE bytes)"
  elif curl -fsSL "$URL_MAIN" -o "data/${FILENAME}" 2>/dev/null && [ -s "data/${FILENAME}" ]; then
    SIZE=$(stat -c%s "data/${FILENAME}")
    echo "  [fetch] $FILENAME from main (seed) ($SIZE bytes)"
  else
    echo "  [fetch] $FILENAME not found in either branch"
    rm -f "data/${FILENAME}"
  fi
done

exit 0
