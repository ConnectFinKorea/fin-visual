#!/bin/bash
# Railway 'Newreg/Weekly' 진입점. 매주 금 21:00 KST(=12:00 UTC) cron 으로 실행.
# DART 에서 '신규등록'(감사보고서 이력이 최신 1개 기간뿐인 회사)을 수집 → data/newreg.json
# → data-snapshot 브랜치 push.
#
# 필요 환경변수:
#   OPENDART_API_KEY  OpenDART 인증키
#   GH_PAT            data-snapshot push용 GitHub PAT
#   GH_REPO           ConnectFinKorea/fin-visual
#
# 동작:
#   - 최초 실행: data-snapshot 에 newreg.json 이 없어 최근 4년 bulk 스캔으로 부트스트랩.
#       (호출량 많음, 수십 분. 체크포인트 data/_newreg_progress.json 로 중단 시 재개)
#   - 이후 매주: 지난 주 신규 접수분 추가 + 기존 목록 중 2기수 올린 회사 제외.

set -u

echo "================================================================"
echo "[Newreg/Weekly] 시작 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "================================================================"

if python scripts/update_newreg.py; then
  bash scripts/push_to_snapshot.sh newreg.json
else
  echo "  WARN: newreg 수집 실패 — push 건너뜀"
  exit 1
fi

echo ""
echo "[Newreg/Weekly] 종료 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
