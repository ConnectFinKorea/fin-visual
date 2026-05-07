"""
DART 단일회사 주요계정(fnlttSinglAcntAll) -> data/revenue.json
- 매월 1회 자동 실행 (GitHub Actions)
- 상장사별로 가장 최근 정기보고서의 매출액 + 전기 매출액 추출
- 보고서 종류 자동 판단:
    1분기(11013) / 반기(11012) / 3분기(11014) / 사업보고서(11011)
  현재 시점에서 공시되어 있을 가능성이 높은 순으로 시도하고
  데이터 없으면 직전 보고서로 fallback.

환경변수:
  DART_API_KEY = OpenDART API 키
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

API_KEY = os.environ.get("DART_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: DART_API_KEY 환경변수 없음")
    sys.exit(1)

KST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
LISTED_PATH = os.path.join(DATA_DIR, "listed_stocks.json")
INDUSTRY_PATH = os.path.join(DATA_DIR, "industry_mapping.json")
OUT_PATH = os.path.join(DATA_DIR, "revenue.json")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
WORKERS = 4              # DART 일일 한도 20,000회 → 보수적
TIMEOUT = 15
MAX_RETRY = 3
SLEEP_SEC = 0.05         # 호출 간격 (워커별)
MIN_SUCCESS_RATIO = 0.50 # 정상 수집률 기대치. 신규상장/특수목적법인 등 누락 감안

# 보고서 코드:
#   11013 = 1분기 (1Q)   결산 03-31
#   11012 = 반기  (H1)   결산 06-30
#   11014 = 3분기 (3Q)   결산 09-30
#   11011 = 사업보고서   결산 12-31

# 매출액 항목 후보 (DART account_nm). 우선순위 순서대로:
#   1) 매출액         — 일반 제조/유통업
#   2) 수익(매출액)   — IFRS 표시 변형
#   3) 영업수익       — 지주사 / 금융권 / 리츠
#   4) 매출           — 단순 표기 회사
REVENUE_ACCOUNT_NAMES = ["매출액", "수익(매출액)", "영업수익", "매출"]


def get_target_reports(now_kst):
    """
    현재 시점에서 시도할 (bsns_year, reprt_code) 우선순위 리스트.
    DART 공시 마감(법정 기한) 이후로 데이터 조회 가능 → 마감 + 약간의 여유 둠.
      1Q : 5/15까지
      반기: 8/14까지
      3Q : 11/14까지
      연간: 다음해 3/31까지
    """
    y, m, d = now_kst.year, now_kst.month, now_kst.day
    candidates = []
    today = (m, d)
    if today >= (11, 16):
        # 3Q 공시 후
        candidates += [(y, "11014"), (y, "11012"), (y, "11013"), (y - 1, "11011")]
    elif today >= (8, 16):
        # 반기 공시 후
        candidates += [(y, "11012"), (y, "11013"), (y - 1, "11011"), (y - 1, "11014")]
    elif today >= (5, 17):
        # 1Q 공시 후
        candidates += [(y, "11013"), (y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012")]
    elif today >= (4, 1):
        # 작년 사업보고서 공시 후
        candidates += [(y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012"), (y - 1, "11013")]
    else:
        # 1월 ~ 3월 말: 작년 사업보고서 아직 공시 전 → 작년 3분기까지가 최신
        candidates += [(y - 1, "11014"), (y - 1, "11012"), (y - 1, "11013"), (y - 2, "11011")]
    return candidates


def _http_get_json(url):
    """DART API 호출 → JSON dict (status='000' 정상)"""
    delay = 0.5
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503):
                time.sleep(delay * 2)
        except Exception as e:
            last_err = str(e)
        if attempt < MAX_RETRY - 1:
            time.sleep(delay)
            delay *= 1.5
    return {"status": "999", "_err": last_err}


def fetch_revenue(corp_code, year, reprt_code):
    """
    fnlttSinglAcntAll 호출 (CFS 우선, OFS fallback) → list 항목 반환 or None.
    """
    base = (
        f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
        f"?crtfc_key={API_KEY}&corp_code={corp_code}"
        f"&bsns_year={year}&reprt_code={reprt_code}"
    )
    for fs_div in ("CFS", "OFS"):  # 연결재무 우선, 없으면 별도재무
        data = _http_get_json(base + f"&fs_div={fs_div}")
        status = data.get("status")
        if status == "000" and data.get("list"):
            return data["list"]
        if status not in ("013", "020"):
            # 013: 데이터 없음, 020: 사용한도 초과 등
            # 그 외 코드는 재시도 의미 없음
            continue
    return None


def parse_amount(s):
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def extract_cumulative(items):
    """
    DART 응답의 list 에서 매출액 항목을 찾아 누적 매출 반환.
    REVENUE_ACCOUNT_NAMES 우선순위 순서대로 첫 매치 사용.
    누적 우선(thstrm_add_amount) → 없으면 thstrm_amount.
      - 1Q 보고서: 누적 = 1Q 단독
      - 반기 보고서: 누적 = H1 (Q1+Q2)
      - 3Q 보고서: 누적 = 1-3Q
      - 사업보고서: 누적 = 연간
    반환: int | None
    """
    if not items:
        return None
    # account_nm → item 매핑 (먼저 등장하는 것 채택)
    by_name = {}
    for it in items:
        nm = (it.get("account_nm") or "").strip()
        if nm in REVENUE_ACCOUNT_NAMES and nm not in by_name:
            by_name[nm] = it
    if not by_name:
        return None
    # 우선순위대로 선택
    target = None
    for name in REVENUE_ACCOUNT_NAMES:
        if name in by_name:
            target = by_name[name]
            break
    if not target:
        return None
    val = parse_amount(target.get("thstrm_add_amount"))
    if val is None:
        val = parse_amount(target.get("thstrm_amount"))
    return val


def fetch_cum(corp_code, year, reprt_code, cache):
    """누적 매출 조회 (캐시 활용). int | None."""
    key = (year, reprt_code)
    if key in cache:
        return cache[key]
    items = fetch_revenue(corp_code, year, reprt_code)
    val = extract_cumulative(items)
    cache[key] = val
    return val


def compute_periods(corp_code, year, current_reprt, cache):
    """
    현재 보고서를 기준으로 회사의 보고 빈도(분기/반기/연간)를 자동 판별하고,
    당기 단독 + 전기 단독 매출을 계산해 반환.

    회사 유형 판별:
      - 1Q 누적이 존재 → 분기 보고 회사
      - 반기 누적만 존재 (1Q 없음) → 반기 보고 회사
      - 사업보고서만 존재 → 연간 보고 회사

    반환: dict | None
    """
    cur_cum = fetch_cum(corp_code, year, current_reprt, cache)
    if cur_cum is None:
        return None

    # === 1Q 보고서 (분기 회사) ===
    if current_reprt == "11013":
        # 당기 = 1Q 단독 = 1Q 누적
        # 전기 = 전년 4Q = 전년 사업 - 전년 3Q 누적
        prev_annual = fetch_cum(corp_code, year - 1, "11011", cache)
        prev_3q = fetch_cum(corp_code, year - 1, "11014", cache)
        if prev_annual is None or prev_3q is None:
            return None
        return {
            "kind": "분기",
            "current":  {"revenue": cur_cum, "report_date": f"{year}-03-31",
                         "report_type": f"{year} 1Q"},
            "previous": {"revenue": prev_annual - prev_3q, "report_date": f"{year - 1}-12-31",
                         "report_type": f"{year - 1} 4Q"},
        }

    # === 반기 보고서 ===
    if current_reprt == "11012":
        # 1Q 존재 여부로 분기 vs 반기 회사 판별
        q1 = fetch_cum(corp_code, year, "11013", cache)
        if q1 is not None:
            # 분기 회사 → 당기 = 2Q (반기 - 1Q), 전기 = 1Q
            return {
                "kind": "분기",
                "current":  {"revenue": cur_cum - q1, "report_date": f"{year}-06-30",
                             "report_type": f"{year} 2Q"},
                "previous": {"revenue": q1, "report_date": f"{year}-03-31",
                             "report_type": f"{year} 1Q"},
            }
        # 반기 회사 → 당기 = H1, 전기 = 전년 H2 (= 전년 사업 - 전년 반기)
        prev_annual = fetch_cum(corp_code, year - 1, "11011", cache)
        prev_h1 = fetch_cum(corp_code, year - 1, "11012", cache)
        if prev_annual is None or prev_h1 is None:
            return None
        return {
            "kind": "반기",
            "current":  {"revenue": cur_cum, "report_date": f"{year}-06-30",
                         "report_type": f"{year} H1"},
            "previous": {"revenue": prev_annual - prev_h1, "report_date": f"{year - 1}-12-31",
                         "report_type": f"{year - 1} H2"},
        }

    # === 3Q 보고서 (분기 회사 한정) ===
    if current_reprt == "11014":
        h1 = fetch_cum(corp_code, year, "11012", cache)
        q1 = fetch_cum(corp_code, year, "11013", cache)
        if h1 is None or q1 is None:
            return None
        return {
            "kind": "분기",
            "current":  {"revenue": cur_cum - h1, "report_date": f"{year}-09-30",
                         "report_type": f"{year} 3Q"},
            "previous": {"revenue": h1 - q1, "report_date": f"{year}-06-30",
                         "report_type": f"{year} 2Q"},
        }

    # === 사업보고서 (연간) ===
    if current_reprt == "11011":
        # 3Q + 반기 + 1Q 모두 존재 → 분기 회사
        q3 = fetch_cum(corp_code, year, "11014", cache)
        h1 = fetch_cum(corp_code, year, "11012", cache)
        if q3 is not None and h1 is not None:
            q1 = fetch_cum(corp_code, year, "11013", cache)
            if q1 is None:
                return None
            return {
                "kind": "분기",
                "current":  {"revenue": cur_cum - q3, "report_date": f"{year}-12-31",
                             "report_type": f"{year} 4Q"},
                "previous": {"revenue": q3 - h1, "report_date": f"{year}-09-30",
                             "report_type": f"{year} 3Q"},
            }
        # 반기만 존재 → 반기 회사
        if h1 is not None:
            return {
                "kind": "반기",
                "current":  {"revenue": cur_cum - h1, "report_date": f"{year}-12-31",
                             "report_type": f"{year} H2"},
                "previous": {"revenue": h1, "report_date": f"{year}-06-30",
                             "report_type": f"{year} H1"},
            }
        # 연간 회사 → 당기 = 당해, 전기 = 전년
        prev_annual = fetch_cum(corp_code, year - 1, "11011", cache)
        if prev_annual is None:
            return None
        return {
            "kind": "연간",
            "current":  {"revenue": cur_cum, "report_date": f"{year}-12-31",
                         "report_type": f"{year}"},
            "previous": {"revenue": prev_annual, "report_date": f"{year - 1}-12-31",
                         "report_type": f"{year - 1}"},
        }

    return None


def load_universe():
    """listed_stocks.json 우선, 없으면 industry_mapping.json"""
    if os.path.exists(LISTED_PATH):
        path = LISTED_PATH
    elif os.path.exists(INDUSTRY_PATH):
        path = INDUSTRY_PATH
        print(f"  주의: listed_stocks.json 없음 → industry_mapping.json 사용")
    else:
        print(f"ERROR: {LISTED_PATH} / {INDUSTRY_PATH} 둘 다 없음")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for c in data.get("companies", []):
        cc = (c.get("corp_code") or "").strip()
        sc = (c.get("stock_code") or "").strip().zfill(6)
        nm = c.get("name") or ""
        if cc and sc and len(sc) == 6 and sc.isdigit():
            out.append({"corp_code": cc, "stock_code": sc, "name": nm})
    return out


def main():
    now_kst = datetime.now(timezone.utc).astimezone(KST)
    print(f"[현재 시각] {now_kst.isoformat()}")

    universe = load_universe()
    print(f"  Universe: {len(universe):,}개 상장사")

    candidates = get_target_reports(now_kst)
    print(f"  보고서 후보 (우선순위): {candidates}")

    t0 = time.monotonic()
    results = []
    failed = []

    def task(c):
        cc, sc, nm = c["corp_code"], c["stock_code"], c["name"]
        cache = {}
        # 후보 보고서 순회. 가장 최근 가용 보고서 발견 시 그 기준으로 QoQ/HoH/YoY 계산.
        for year, rcode in candidates:
            result = compute_periods(cc, year, rcode, cache)
            time.sleep(SLEEP_SEC)
            if result and result["current"]["revenue"] is not None:
                return {
                    "stock_code": sc,
                    "name": nm,
                    "kind": result["kind"],   # 분기/반기/연간
                    "current": result["current"],
                    "previous": result["previous"],
                }
        return None

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(task, c): c for c in universe}
        done = 0
        for fut in as_completed(futures):
            c = futures[fut]
            done += 1
            try:
                r = fut.result()
            except Exception as e:
                r = None
                print(f"  예외 {c['stock_code']}: {e}")
            if r:
                results.append(r)
            else:
                failed.append(c["stock_code"])
            if done % 200 == 0:
                pct = done / len(universe) * 100
                print(f"  진행 {done:,}/{len(universe):,} ({pct:.1f}%) 성공 {len(results):,}")

    elapsed = time.monotonic() - t0
    success_ratio = len(results) / len(universe) if universe else 0
    print(f"\n  완료: 성공 {len(results):,} / 실패 {len(failed):,} "
          f"(성공률 {success_ratio*100:.1f}%, 소요 {elapsed/60:.1f}분)")

    if success_ratio < MIN_SUCCESS_RATIO:
        print(f"\n[비정상 감지] 성공률 {success_ratio*100:.1f}% < {MIN_SUCCESS_RATIO*100:.0f}%")
        print(f"  DART 차단/장애 의심 → revenue.json 갱신 건너뜀")
        if failed[:5]:
            print(f"  실패 샘플: {failed[:5]}")
        sys.exit(1)

    out = {
        "generated_at": now_kst.isoformat(),
        "source": "DART OpenAPI fnlttSinglAcntAll",
        "count": len(results),
        "universe_size": len(universe),
        "success_ratio": round(success_ratio, 4),
        "elapsed_min": round(elapsed / 60, 1),
        "companies": results,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_PATH) // 1024
    print(f"\n저장 완료: {OUT_PATH} ({size_kb:,} KB)")


if __name__ == "__main__":
    main()
