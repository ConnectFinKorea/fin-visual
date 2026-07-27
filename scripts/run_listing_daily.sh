#!/bin/bash
# Railway 'Listing/Daily' 진입점. 매일 23:00 KST(=14:00 UTC) cron 으로 실행.
# KIND 에서 신규상장/상장폐지(최근 3개월, 스팩 제외)를 수집 → data/listing.json
# → data-snapshot 브랜치 push.
#
# 필요 환경변수:
#   GH_PAT   data-snapshot push용 GitHub PAT
#   GH_REPO  ConnectFinKorea/fin-visual
#
# 동작:
#   - 최초 실행: data-snapshot 에 listing.json 이 없어 3개월 전체를 부트스트랩.
#   - 이후 매일: 기존 listing.json 을 읽어 "당일" 자료만 병합, 3개월 초과분은 잘라냄.

set -u

echo "================================================================"
echo "[Listing/Daily] 시작 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "================================================================"

if python scripts/update_listing.py; then
  bash scripts/push_to_snapshot.sh listing.json
else
  echo "  WARN: listing 수집 실패 — push 건너뜀"
  exit 1
fi

echo ""
echo "[Listing/Daily] 종료 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
