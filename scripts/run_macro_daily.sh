#!/bin/bash
# Railway 'Macro Eco/Daily' 진입점. 매일 cron 으로 실행.
# Macro Eco 전 지표(현재 Prime Rate)를 한 번에 수집 → data/macro.json → data-snapshot 브랜치 push.
# (무료 Railway 서비스 5개 한도 때문에 Macro Eco 는 이 단일 서비스로 통합 운영)
#
# 필요 환경변수:
#   ECOS_API_KEY  한국은행 ECOS 인증키 (한국 기준금리·국고채)
#   FRED_API_KEY  FRED API 키 (미국·일본 10년 국채)
#   GH_PAT        data-snapshot push용 GitHub PAT
#   GH_REPO       ConnectFinKorea/fin-visual

set -u

echo "================================================================"
echo "[Macro Eco/Daily] 시작 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "================================================================"

if python scripts/update_macro.py; then
  bash scripts/push_to_snapshot.sh macro.json
else
  echo "  WARN: macro 수집 실패 — push 건너뜀"
  exit 1
fi

echo ""
echo "[Macro Eco/Daily] 종료 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
