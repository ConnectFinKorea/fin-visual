#!/bin/bash
set -e

OUTPUT_NAME="$1"

if [ -z "$OUTPUT_NAME" ]; then
  echo "ERROR: 출력 파일명을 인자로 받아야 합니다."
  echo "사용법: bash scripts/push_to_snapshot.sh <filename.json>"
  exit 1
fi

DATA_FILE="data/$OUTPUT_NAME"

if [ ! -f "$DATA_FILE" ]; then
  echo "ERROR: $DATA_FILE 가 생성되지 않았습니다. push 건너뜀."
  exit 0
fi

if [ -z "$GH_PAT" ] || [ -z "$GH_REPO" ]; then
  echo "ERROR: GH_PAT 또는 GH_REPO 환경변수가 설정되지 않았습니다."
  exit 1
fi

cp "$DATA_FILE" "/tmp/$OUTPUT_NAME"

git config --global user.name "railway-bot"
git config --global user.email "railway-bot@noreply.com"
git config --global --add safe.directory "$(pwd)"

git remote set-url origin "https://${GH_PAT}@github.com/${GH_REPO}.git"

git fetch origin data-snapshot 2>/dev/null || true
if git show-ref --quiet refs/remotes/origin/data-snapshot; then
  git checkout -B data-snapshot origin/data-snapshot
else
  git checkout --orphan data-snapshot
  git rm -rf --cached . 2>/dev/null || true
fi

git clean -fdx

cp "/tmp/$OUTPUT_NAME" "./$OUTPUT_NAME"

git add "$OUTPUT_NAME"
if git diff --staged --quiet; then
  echo "변경사항 없음. push 건너뜀."
else
  git commit -m "data: update $OUTPUT_NAME ($(date -u +%Y-%m-%dT%H:%M:%SZ)) [skip ci]"
  git push origin data-snapshot
  echo "Push 완료: $OUTPUT_NAME -> data-snapshot"
fi
