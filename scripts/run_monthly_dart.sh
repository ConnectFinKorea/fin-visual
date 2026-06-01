#!/bin/bash
# Railway 'Monthly DART/M' 통합 파이프라인 진입점.
# 매월 1일 cron으로 실행되어 industry_mapping → revenue → financial_status 순서로 갱신.
# 각 단계는 독립 실패 모드: 앞 단계가 실패해도 다음 단계는 진행함.
# 마지막 단계 종료 코드를 그대로 리턴.

set -u

echo "================================================================"
echo "[Monthly DART/M] 시작 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "================================================================"

# 0. 외부 의존 데이터 (data-snapshot 브랜치)를 data/ 폴더로 수신.
#    listed_stocks.json: Revenue/Financial이 universe로 사용.
#    industry_mapping.json: fetch_dart_industry.py 실패 시 fallback으로 보존.
echo ""
echo "[0/3] 의존 데이터 수신"
bash scripts/fetch_from_snapshot.sh listed_stocks.json industry_mapping.json

# 1. Industry Mapping — DART corpCode.xml + company.json 산업코드 → KSIC 11차 매핑.
#    Revenue/Financial보다 먼저 돌려서 신규 상장사가 후속 단계에 즉시 반영되도록.
echo ""
echo "================================================================"
echo "[1/3] Industry Mapping (DART corpCode.xml + KSIC 11차)"
echo "================================================================"
if python scripts/fetch_dart_industry.py; then
  bash scripts/push_to_snapshot.sh industry_mapping.json
else
  echo "  WARN: industry_mapping 실패 — 직전 매핑 유지하고 다음 단계 진행"
fi

# 2. Revenue — 가장 최근 정기보고서 기준 당기/전기 매출액 (분기/반기/연간 자동 판별).
echo ""
echo "================================================================"
echo "[2/3] Revenue (DART fnlttSinglAcntAll 매출액)"
echo "================================================================"
if python scripts/update_revenue.py; then
  bash scripts/push_to_snapshot.sh revenue.json
else
  echo "  WARN: revenue 실패 — 다음 단계 진행"
fi

# 3. Financial Status — 사업보고서 기준 BS 3계정 + IS 10계정 (직전/직직전 연도말).
echo ""
echo "================================================================"
echo "[3/3] Financial Status (DART 사업보고서 BS/IS)"
echo "================================================================"
LAST_EXIT=0
if python scripts/update_financial_status.py; then
  bash scripts/push_to_snapshot.sh financial_status.json
else
  echo "  WARN: financial_status 실패"
  LAST_EXIT=1
fi

echo ""
echo "[Monthly DART/M] 종료 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit $LAST_EXIT
