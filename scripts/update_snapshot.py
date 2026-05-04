"""
Naver Finance 종목별 시세 크롤링 -> snapshot.json
- 평일 09-16시 KST 정시에 GitHub Actions에서 실행 (cron 지연 5-15분 수용)
- 한국 공휴일 + 임시 휴장일이면 즉시 종료
- listed_stocks.json 의 모든 종목코드를 universe 로 사용 (누락 0 보장 설계)

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
import random
import re
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
TIMEOUT = 10
MAX_RETRY = 3
MIN_SUCCESS_RATIO = 0.80  # 성공률이 이보다 낮으면 의심 -> 저장 안 함

# 추가 KRX 임시 휴장일 (holidays 라이브러리가 못 잡는 경우)
# 형식: "YYYY-MM-DD": "사유"
EXTRA_KRX_HOLIDAYS = {
    # "2026-06-03": "대통령 선거일",  # 예시
}


# ============================== 휴장 판단 ==============================

def check_holiday(today_kst):
    """
    오늘이 한국 휴장일인지 확인.
    Returns: (is_holiday: bool, reason: str)
    """
    # 1. 주말
    weekday = today_kst.weekday()
    if weekday >= 5:
        return True, f"주말 ({['월','화','수','목','금','토','일'][weekday]}요일)"

    # 2. holidays 라이브러리 (한국 공휴일)
    if HAS_HOLIDAYS:
        kr_holidays = holidays.KR(years=today_kst.year)
        if today_kst in kr_holidays:
            return True, f"공휴일: {kr_holidays.get(today_kst)}"

    # 3. 하드코딩된 KRX 임시 휴장일
    key = today_kst.strftime("%Y-%m-%d")
    if key in EXTRA_KRX_HOLIDAYS:
        return True, f"KRX 임시 휴장: {EXTRA_KRX_HOLIDAYS[key]}"

    return False, ""


# ============================== Universe 로드 ==============================

def load_universe():
    """
    종목 universe 로드.
    - listed_stocks.json: 종목코드 목록 (일일 DART 갱신)
    - industry_mapping.json: 시장구분 포함 (월 1회 갱신, "기타" 필터에 사용)

    동작:
    1) listed_stocks가 있으면 universe 기준, 없으면 industry_mapping 사용
    2) industry_mapping이 있으면 그것의 market 필드로 "기타" 필터 적용
       (industry_mapping이 없으면 필터 없이 전부 시도)
    """
    # 1) industry_mapping 으로부터 stock_code -> market dict 구축 (있을 경우)
    market_by_code = {}
    if os.path.exists(INDUSTRY_PATH):
        with open(INDUSTRY_PATH, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        for c in mapping.get("companies", []):
            sc = (c.get("stock_code", "") or "").strip().zfill(6)
            mkt = c.get("market", "")
            if sc and mkt:
                market_by_code[sc] = mkt
        print(f"  industry_mapping 로드: {len(market_by_code):,}개 시장구분")

    # 2) universe source 결정
    if os.path.exists(LISTED_PATH):
        with open(LISTED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        source = "listed_stocks.json"
    elif os.path.exists(INDUSTRY_PATH):
        with open(INDUSTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        source = "industry_mapping.json (fallback)"
    else:
        print(f"ERROR: {LISTED_PATH} 또는 {INDUSTRY_PATH} 둘 다 없습니다.")
        sys.exit(1)

    companies = data.get("companies", [])
    universe = []
    skipped_invalid = 0
    skipped_etc = 0
    skipped_unknown = 0  # industry_mapping 없을 때만 발생

    for c in companies:
        stock = (c.get("stock_code", "") or "").strip().zfill(6)
        if not stock or len(stock) != 6 or not stock.isdigit():
            skipped_invalid += 1
            continue

        # 시장구분: industry_mapping 우선, 없으면 c["market"], 그것도 없으면 unknown
        market = market_by_code.get(stock) or c.get("market", "") or ""

        # "기타" 분류는 비상장/특수목적 등이라 Naver에 없을 가능성 높음 -> 스킵
        if market == "기타":
            skipped_etc += 1
            continue

        universe.append({
            "code": stock,
            "name": c.get("name", ""),
            "market": market,  # "" 가능 (신규 상장으로 매핑 미반영). 프론트가 보충.
        })

    print(f"  Universe 소스: {source}")
    print(f"  Universe 로드: {len(universe):,}개")
    print(f"    제외 - 무효 코드: {skipped_invalid:,}개")
    print(f"    제외 - 기타 분류: {skipped_etc:,}개")
    return universe


# ============================== Naver API ==============================

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


def fetch_stock(code):
    """
    Naver mobile integration API 호출.
    응답 구조 (확인된 것):
      stockName, closePrice, compareToPreviousClosePrice,
      fluctuationsRatio, marketValue (단위: 억원)
    """
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://m.stock.naver.com/",
        "Accept": "application/json",
    })
    delay = 0.5
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            return parse_response(code, data)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                return None  # 폐지 종목 등
            if e.code == 429:
                time.sleep(delay * 3)  # rate limit 시 더 길게 대기
        except Exception as e:
            last_err = str(e)
        if attempt < MAX_RETRY - 1:
            time.sleep(delay + random.random() * 0.2)
            delay *= 1.6
    return None


def parse_response(code, data):
    """
    Naver 응답 -> 표준 형식.
    필드는 응답 변형에 대응하기 위해 다중 후보 검색.
    """
    if not isinstance(data, dict):
        return None

    # nested 가능: stockInfo, dealTrendInfo, ...
    candidates = [data]
    for key in ("stockInfo", "stock", "data"):
        v = data.get(key)
        if isinstance(v, dict):
            candidates.append(v)

    def pick(*names):
        for src in candidates:
            for n in names:
                if n in src and src[n] is not None and src[n] != "":
                    return src[n]
        return None

    name = pick("stockName", "itemName", "name", "korName")
    close = parse_number(pick("closePrice", "now", "price", "currentPrice"))
    chg = parse_number(pick("fluctuationsRatio", "fluctuationRatio", "changeRate"))
    mcap_raw = parse_number(pick("marketValue", "marketCap", "marketCapacity"))

    if mcap_raw is None:
        return None

    # marketValue 단위 추론: 1조 미만 종목도 있으니 휴리스틱
    # Naver 모바일은 보통 억 단위 (예: 삼성전자 = 4,553,879)
    # 4,553,879 억 = 455조 -> 억 단위 맞음
    # 매우 작은 회사여도 억 단위로 100단위 (=100억) 정도는 됨
    # 따라서 mcap_raw 가 너무 작으면 (< 1) 무시, 그 외엔 *1e8
    if mcap_raw < 1:
        return None
    mcap_krw = mcap_raw * 1e8

    return {
        "code": code,
        "name": name or "",
        "mcap": mcap_krw,
        "change": chg if chg is not None else 0.0,
        "close": close,
    }


# ============================== 메인 ==============================

def main():
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc.astimezone(KST)
    today_kst = now_kst.date()

    print(f"[현재 시각]")
    print(f"  UTC : {now_utc.isoformat()}")
    print(f"  KST : {now_kst.isoformat()}")

    # 1. 휴장 체크 (옵션 A)
    is_holiday, reason = check_holiday(today_kst)
    if is_holiday:
        print(f"\n[휴장] {reason} -> 스냅샷 갱신 건너뜀")
        sys.exit(0)
    print(f"  -> 영업일")

    # 2. Universe 로드
    print(f"\n[Universe 로드]")
    universe = load_universe()
    if not universe:
        print("ERROR: 빈 universe")
        sys.exit(1)

    # 3. 병렬 fetch
    print(f"\n[Naver 시세 조회] workers={WORKERS}, 종목수={len(universe):,}")
    t0 = time.monotonic()

    items = []
    failed = []
    code_to_meta = {u["code"]: u for u in universe}

    def task(u):
        return u["code"], fetch_stock(u["code"])

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(task, u) for u in universe]
        done = 0
        for fut in as_completed(futures):
            code, result = fut.result()
            done += 1
            if result:
                meta = code_to_meta.get(code, {})
                result["market"] = meta.get("market", "")
                # name 비어 있으면 DART 이름으로 보충
                if not result.get("name"):
                    result["name"] = meta.get("name", "")
                items.append(result)
            else:
                failed.append(code)
            if done % 500 == 0:
                pct = done / len(universe) * 100
                print(f"  진행 {done:,}/{len(universe):,} ({pct:.1f}%) 성공 {len(items):,}")

    elapsed = time.monotonic() - t0
    success_ratio = len(items) / len(universe) if universe else 0
    print(f"\n  완료: 성공 {len(items):,} / 실패 {len(failed):,} (성공률 {success_ratio*100:.1f}%, 소요 {elapsed:.1f}초)")

    # 4. 안전장치 (옵션 C): 성공률 너무 낮으면 의심 -> 저장 안 함
    if success_ratio < MIN_SUCCESS_RATIO:
        print(f"\n[비정상 감지] 성공률 {success_ratio*100:.1f}% < {MIN_SUCCESS_RATIO*100:.0f}%")
        print(f"  Naver 차단/장애 의심 -> snapshot.json 갱신 건너뜀")
        if failed[:5]:
            print(f"  실패 샘플: {failed[:5]}")
        sys.exit(1)

    # 5. snapshot.json 작성
    output = {
        "timestamp": now_kst.isoformat(),
        "fetched_at": now_kst.strftime("%Y-%m-%d %H:%M:%S KST"),
        "count": len(items),
        "universe_size": len(universe),
        "success_ratio": round(success_ratio, 4),
        "elapsed_sec": round(elapsed, 1),
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
