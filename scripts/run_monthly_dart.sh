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
#    Financials보다 먼저 돌려서 신규 상장사가 후속 단계에 즉시 반영되도록.
echo ""
echo "================================================================"
echo "[1/2] Industry Mapping (DART corpCode.xml + KSIC 11차)"
echo "================================================================"
if python scripts/fetch_dart_industry.py; then
  bash scripts/push_to_snapshot.sh industry_mapping.json
else
  echo "  WARN: industry_mapping 실패 — 직전 매핑 유지하고 다음 단계 진행"
fi

# 2. Financials (통합) — 종목당 fnlttSinglAcntAll 보고서를 한 번만 호출해
#    매출(분기/반기/연간 단독) + 재무상태표/손익계산서 연말값을 동시 추출.
#    (구 update_revenue.py + update_financial_status.py 의 중복 호출 제거판)
#    한도 도달/저성공 시에도 exit 0 (cron 'crashed' 제거 방지). 자체 self-heal·재개 내장.
echo ""
echo "================================================================"
echo "[2/2] Financials (매출 + BS/IS 통합, DART fnlttSinglAcntAll)"
echo "================================================================"
LAST_EXIT=0
if python scripts/update_financials.py; then
  bash scripts/push_to_snapshot.sh revenue.json
  bash scripts/push_to_snapshot.sh financial_status.json
else
  echo "  WARN: financials 실패 (치명적 오류)"
  LAST_EXIT=1
fi

echo ""
echo "[Monthly DART/M] 종료 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit $LAST_EXIT
