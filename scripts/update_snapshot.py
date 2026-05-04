"""
Naver Finance 시장별 시가총액 페이지 크롤링 -> snapshot.json

설계:
- 평일 09-16시 KST 정시에 GitHub Actions에서 실행 (cron 지연 5-15분 수용)
- 한국 공휴일 + 임시 휴장일이면 즉시 종료
- KOSPI/KOSDAQ/KONEX 의 marketValue 페이지 endpoint 를 모든 페이지 병렬 fetch
  (~3초 내 완료되므로 시점 차이로 인한 누락 사실상 0)
- listed_stocks.json (DART) 과 대조해 누락 종목 명시적 로그

생성 데이터 형식 (frontend app.js 가 기대하는 구조):
{
  "timestamp": "2026-05-04T09:00:00+09:00",
  "fetched_at": "...",
  "count": 2769,
  "items": [
    {"code": "005930", "name": "삼성전자", "mcap": 4.55e14, "change": 1.33, "market": "KOSPI"}
  ]
}
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

try:
    import holidays
    HAS_HOLIDAYS = True
except ImportError:
    HAS_HOLIDAYS = False

KST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
LISTED_PATH = os.path.join(DATA_DIR, "listed_stocks.json")
INDUSTRY_PATH = os.path.join(DATA_DIR, "industry_mapping.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "snapshot.json")

UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Mobile Safari/537.36"
WORKERS = 5
TIMEOUT = 15
PAGE_SIZE = 100
MAX_PAGES_PER_MARKET = 30   # 안전 상한 (KOSPI ~9, KOSDAQ ~18, KONEX ~2)
MARKETS = ["KOSPI", "KOSDAQ", "KONEX"]

# 추가 KRX 임시 휴장일 (holidays 라이브러리가 못 잡는 경우)
EXTRA_KRX_HOLIDAYS = {
    # "2026-06-03": "대통령 선거일",
}


# ============================== 휴장 판단 ==============================

def check_holiday(today_kst):
    weekday = today_kst.weekday()
    if weekday >= 5:
        return True, f"주말 ({['월','화','수','목','금','토','일'][weekday]}요일)"
    if HAS_HOLIDAYS:
        kr_holidays = holidays.KR(years=today_kst.year)
        if today_kst in kr_holidays:
            return True, f"공휴일: {kr_holidays.get(today_kst)}"
    key = today_kst.strftime("%Y-%m-%d")
    if key in EXTRA_KRX_HOLIDAYS:
        return True, f"KRX 임시 휴장: {EXTRA_KRX_HOLIDAYS[key]}"
    return False, ""


# ============================== 외부 데이터 ==============================

def load_listed_codes():
    """DART listed_stocks.json -> {code: name}"""
    if not os.path.exists(LISTED_PATH):
        print(f"  주의: {LISTED_PATH} 없음. 검증 단계 생략.")
        return {}
    with open(LISTED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for c in data.get("companies", []):
        sc = (c.get("stock_code", "") or "").strip().zfill(6)
        if sc and len(sc) == 6 and sc.isdigit():
            out[sc] = c.get("name", "")
    return out


def load_industry_market():
    """industry_mapping.json -> {code: market}"""
    if not os.path.exists(INDUSTRY_PATH):
        return {}
    with open(INDUSTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for c in data.get("companies", []):
        sc = (c.get("stock_code", "") or "").strip().zfill(6)
        mkt = c.get("market", "")
        if sc and mkt:
            out[sc] = mkt
    return out


# ============================== HTTP ==============================

def parse_number(s):
    """'76,300' -> 76300.0, None 처리"""
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str):
        s = s.replace(",", "").replace("%", "").strip()
        if not s or s == "-":
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://m.stock.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.code, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return -1, str(e)


# ============================== 페이지 fetch ==============================

def fetch_page(market, page):
    """
    Naver marketValue 페이지 한 장 fetch.
    Returns: (market, page, list[dict] | None)
    """
    url = (
        f"https://m.stock.naver.com/api/stocks/marketValue/{market}"
        f"?page={page}&pageSize={PAGE_SIZE}"
    )
    status, body = _http_get(url)
    if status != 200:
        return market, page, None, f"HTTP {status}"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return market, page, None, "JSON 파싱 실패"

    # 응답 구조: {"stocks": [...]} 또는 {"data": {"stocks": [...]}}
    stocks = None
    if isinstance(data, dict):
        if isinstance(data.get("stocks"), list):
            stocks = data["stocks"]
        elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("stocks"), list):
            stocks = data["data"]["stocks"]
        elif isinstance(data.get("items"), list):
            stocks = data["items"]
    if stocks is None:
        return market, page, None, f"stocks 배열 없음 (top keys: {list(data.keys())[:8]})"

    return market, page, stocks, None


def parse_stock_item(s, market):
    """marketValue 페이지의 한 종목 dict -> 표준 형식"""
    code = s.get("itemCode") or s.get("stockCode") or s.get("code")
    if not code:
        return None
    code = str(code).strip().zfill(6)
    if len(code) != 6 or not code.isdigit():
        return None

    name = s.get("stockName") or s.get("itemName") or s.get("name") or ""
    mcap_raw = parse_number(s.get("marketValue") or s.get("marketCap"))
    chg = parse_number(s.get("fluctuationsRatio") or s.get("changeRate"))
    close = parse_number(s.get("closePrice") or s.get("currentPrice") or s.get("price"))

    if mcap_raw is None or mcap_raw < 1:
        return None

    # marketValue 단위는 억원 (Naver 표준)
    return {
        "code": code,
        "name": name,
        "mcap": mcap_raw * 1e8,
        "change": chg if chg is not None else 0.0,
        "close": close,
        "market": market,
    }


# ============================== 메인 ==============================

def main():
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc.astimezone(KST)
    today_kst = now_kst.date()

    print(f"[현재 시각]")
    print(f"  UTC : {now_utc.isoformat()}")
    print(f"  KST : {now_kst.isoformat()}")

    is_holiday, reason = check_holiday(today_kst)
    if is_holiday:
        print(f"\n[휴장] {reason} -> 스냅샷 갱신 건너뜀")
        sys.exit(0)
    print(f"  -> 영업일")

    # ============ 외부 메타데이터 ============
    print(f"\n[외부 메타데이터 로드]")
    listed = load_listed_codes()
    print(f"  DART 상장 종목: {len(listed):,}개")
    market_by_code = load_industry_market()
    print(f"  industry_mapping 시장구분: {len(market_by_code):,}개")

    # ============ 첫 페이지 진단 ============
    print(f"\n[진단] KOSPI 1페이지 응답 구조 확인")
    m, p, stocks, err = fetch_page("KOSPI", 1)
    if stocks is None:
        print(f"  ERROR: {err}")
        sys.exit(1)
    if not stocks:
        print(f"  ERROR: KOSPI 1페이지가 비어있음")
        sys.exit(1)
    sample = stocks[0]
    print(f"  첫 종목 키: {list(sample.keys())[:15]}")
    parsed = parse_stock_item(sample, "KOSPI")
    if not parsed:
        print(f"  ERROR: 파싱 실패. raw 샘플 = {json.dumps(sample, ensure_ascii=False)[:300]}")
        sys.exit(1)
    print(f"  파싱 OK: {parsed['name']} mcap={parsed['mcap']:.3e} chg={parsed['change']}%")

    # ============ 모든 페이지 병렬 fetch ============
    print(f"\n[전 페이지 병렬 fetch] markets={MARKETS}, workers={WORKERS}, max_pages={MAX_PAGES_PER_MARKET}")
    t0 = time.monotonic()

    all_items_by_code = {}
    page_results = {}  # (market, page) -> stocks count

    # 모든 시장 × 모든 페이지 task 생성
    tasks = [(m, p) for m in MARKETS for p in range(1, MAX_PAGES_PER_MARKET + 1)]

    # 마켓별 "더 이상 없음"을 감지하기 위해 끝페이지 추적
    market_done_after = {m: MAX_PAGES_PER_MARKET for m in MARKETS}

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(fetch_page, m, p): (m, p) for m, p in tasks}
        for fut in as_completed(futures):
            market, page = futures[fut]
            try:
                _, _, stocks, err = fut.result()
            except Exception as e:
                print(f"  페이지 예외 {market} p{page}: {e}")
                continue

            if stocks is None:
                # HTTP 에러 - 스킵
                continue
            if not stocks:
                # 빈 페이지 - 이 시장은 여기서 끝
                if page < market_done_after[market]:
                    market_done_after[market] = page
                continue

            page_results[(market, page)] = len(stocks)
            for s in stocks:
                item = parse_stock_item(s, market)
                if item:
                    # 중복 시 첫 결과 유지 (같은 종목이 다른 시장에 중복 노출되는 경우)
                    if item["code"] not in all_items_by_code:
                        all_items_by_code[item["code"]] = item

    elapsed = time.monotonic() - t0
    items = list(all_items_by_code.values())

    print(f"  완료: {elapsed:.1f}초, 종목 {len(items):,}개")
    for m in MARKETS:
        last_page = market_done_after[m]
        pages_with_data = sorted(p for (mk, p) in page_results.keys() if mk == m)
        total_in_market = sum(page_results[(m, p)] for p in pages_with_data)
        print(f"    {m}: 페이지 1-{max(pages_with_data) if pages_with_data else 0}, 총 {total_in_market}개 (끝 페이지 {last_page})")

    if not items:
        print(f"\n  ERROR: 수집된 종목 0개")
        sys.exit(1)

    # ============ DART 대조 검증 ============
    if listed:
        got = set(all_items_by_code.keys())
        listed_set = set(listed.keys())
        missing = listed_set - got
        extra = got - listed_set
        coverage = len(listed_set & got) / len(listed_set) * 100 if listed_set else 0
        print(f"\n[DART 대조]")
        print(f"  DART 상장 {len(listed_set):,}개 / Naver 수집 {len(got):,}개 / 교집합 {len(listed_set & got):,}개 ({coverage:.1f}%)")
        if missing:
            print(f"  DART에 있으나 Naver에 없음: {len(missing):,}개 (샘플 5개: {sorted(missing)[:5]})")
        if extra:
            print(f"  Naver에 있으나 DART에 없음: {len(extra):,}개 (샘플 5개: {sorted(extra)[:5]})")

    # ============ market 보정: industry_mapping 우선 ============
    for it in items:
        mapped = market_by_code.get(it["code"])
        if mapped:
            it["market"] = mapped

    # ============ snapshot.json 작성 ============
    output = {
        "timestamp": now_kst.isoformat(),
        "fetched_at": now_kst.strftime("%Y-%m-%d %H:%M:%S KST"),
        "count": len(items),
        "elapsed_sec": round(elapsed, 1),
        "source": "Naver m.stock.naver.com marketValue paginated API",
        "items": items,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(SNAPSHOT_PATH) // 1024
    print(f"\n저장 완료: {SNAPSHOT_PATH} ({size_kb:,} KB)")
    print(f"  종목수 {len(items):,} / 시각 {output['fetched_at']}")


if __name__ == "__main__":
    main()
