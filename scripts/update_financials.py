"""
DART 단일회사 주요계정(fnlttSinglAcntAll) 통합 수집
  → data/revenue.json + data/financial_status.json (한 번의 패스로 둘 다 생성)

기존 update_revenue.py + update_financial_status.py 를 통합한 스크립트.
종목당 보고서를 '공유 캐시'로 한 번만 호출해 매출(분기/반기/연간 단독)과
재무상태표(BS)·손익계산서(IS) 연말값을 동시에 추출 → DART 호출 수 대폭 절감
(특히 연간 사업보고서를 양 작업이 중복 호출하던 것을 제거).

안정성:
  - 체크포인트 재개(Railway 시간제한 대비)
  - DART 일일 한도(status 020) 감지 시 우아하게 중단 → 다음 실행에서 이어서 수집
    (한도로 미처리된 종목은 실패로 기록하지 않아 체크포인트 오염 없음)
  - 교착(전체 시도했으나 저성공률) 자동 감지 → 체크포인트 self-heal 리셋
  - 모든 정상 종료는 exit 0 (cron 서비스가 'crashed'로 제거되지 않도록)
  - 완료 마커: 직전 성공 갱신 후 REFRESH_INTERVAL_DAYS 내엔 재수집 건너뜀(한도 보호)
    · 환경변수 FORCE_REFRESH=1 로 마커 무시하고 강제 재수집 가능

환경변수:
  DART_API_KEY   = OpenDART API 키 (필수)
  FORCE_REFRESH  = 1 이면 완료 마커 무시
"""

import json
import os
import re
import sys
import threading
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
REVENUE_OUT = os.path.join(DATA_DIR, "revenue.json")
FIN_OUT = os.path.join(DATA_DIR, "financial_status.json")
PROGRESS_PATH = os.path.join(DATA_DIR, "_financials_progress.json")  # 통합 체크포인트 (gitignore)
DONE_PATH = os.path.join(DATA_DIR, "_financials_done.json")          # 완료 마커 (gitignore)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
WORKERS = 4              # 동시 워커 (버스트성 429 회피 위해 보수적으로)
TIMEOUT = 15
MAX_RETRY = 3
SLEEP_SEC = 0.1          # 종목 처리 후 간격 (워커별)
SAVE_EVERY = 200
MIN_SUCCESS_RATIO = 0.50 # 정상 수집률 기대치 미만이면 해당 출력 갱신 보류
REFRESH_INTERVAL_DAYS = 25  # 직전 성공 갱신 후 이 기간 내엔 재수집 건너뜀

# DART 일일 한도(status 020) 감지 → set 되면 모든 워커가 즉시 중단
_QUOTA_HIT = threading.Event()

# ============ 매출액(IS) 계정 후보 ============
REVENUE_ACCOUNT_NAMES = ["매출액", "수익(매출액)", "영업수익", "매출"]

# ============ 재무상태표(BS) / 손익계산서(IS) 계정 후보 ============
BS_ACCOUNTS = {
    "자산총계": ["자산총계"],
    "부채총계": ["부채총계"],
    "자본총계": ["자본총계"],
}
IS_ACCOUNTS = {
    "매출액":            ["매출액", "수익(매출액)", "영업수익", "매출"],
    "매출원가":          ["매출원가", "영업비용"],
    "판매관리비":        ["판매비와관리비", "판매관리비", "판매및관리비"],
    "영업이익":          ["영업이익", "영업이익(손실)"],
    "영업외수익":        ["영업외수익"],
    "영업외비용":        ["영업외비용"],
    "영업외손익":        ["영업외손익"],
    "법인세차감전손익":  [
        "법인세차감전순이익", "법인세비용차감전순이익",
        "법인세비용차감전계속사업이익", "법인세비용차감전순손익",
        "법인세차감전계속사업이익", "법인세차감전순손익",
        "법인세비용차감전순손익(손실)",
    ],
    "법인세":            ["법인세비용", "법인세"],
    "당기순이익":        ["당기순이익", "당기순이익(손실)", "연결당기순이익"],
}


# ===================== 공통: HTTP / 보고서 캐시 =====================

def _http_get_json(url):
    """DART API 호출 → JSON dict. status '020'(한도초과) 감지 시 전역 중단 신호."""
    delay = 0.5
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("status") == "020":
                _QUOTA_HIT.set()   # 일일 한도 초과 → 더 부르지 않도록
            return data
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


def fetch_report_items(corp_code, year, reprt_code):
    """fnlttSinglAcntAll 호출(CFS 우선, OFS fallback) → list 항목 or None.
    한도(020) 감지 시 즉시 None."""
    if _QUOTA_HIT.is_set():
        return None
    base = (
        f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
        f"?crtfc_key={API_KEY}&corp_code={corp_code}"
        f"&bsns_year={year}&reprt_code={reprt_code}"
    )
    for fs_div in ("CFS", "OFS"):       # 연결 우선, 없으면 별도
        if _QUOTA_HIT.is_set():
            return None
        data = _http_get_json(base + f"&fs_div={fs_div}")
        status = data.get("status")
        if status == "000" and data.get("list"):
            return data["list"]
        if status == "020":             # 한도 초과 → OFS 시도 무의미
            return None
        # 013(데이터 없음) 등은 다음 fs_div 시도
    return None


def get_report(corp_code, year, reprt_code, cache):
    """(year, reprt_code) 보고서 list 를 캐시와 함께 반환. 매출·BS/IS 가 공유."""
    key = (year, reprt_code)
    if key in cache:
        return cache[key]
    items = fetch_report_items(corp_code, year, reprt_code)
    cache[key] = items
    return items


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


# ===================== 매출액(Revenue) 추출 =====================

def get_target_reports(now_kst):
    """현재 시점에서 시도할 (bsns_year, reprt_code) 우선순위 리스트."""
    y, m, d = now_kst.year, now_kst.month, now_kst.day
    today = (m, d)
    if today >= (11, 16):
        return [(y, "11014"), (y, "11012"), (y, "11013"), (y - 1, "11011")]
    if today >= (8, 16):
        return [(y, "11012"), (y, "11013"), (y - 1, "11011"), (y - 1, "11014")]
    if today >= (5, 17):
        return [(y, "11013"), (y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012")]
    if today >= (4, 1):
        return [(y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012"), (y - 1, "11013")]
    return [(y - 1, "11014"), (y - 1, "11012"), (y - 1, "11013"), (y - 2, "11011")]


def extract_cumulative(items):
    """list 에서 매출액 항목 누적 매출 반환. 누적(thstrm_add_amount) 우선."""
    if not items:
        return None
    by_name = {}
    for it in items:
        nm = (it.get("account_nm") or "").strip()
        if nm in REVENUE_ACCOUNT_NAMES and nm not in by_name:
            by_name[nm] = it
    if not by_name:
        return None
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
    """누적 매출 조회 (공유 보고서 캐시 활용). int | None."""
    return extract_cumulative(get_report(corp_code, year, reprt_code, cache))


def compute_periods(corp_code, year, current_reprt, cache):
    """현재 보고서 기준 당기/전기 단독 매출 계산. dict | None."""
    cur_cum = fetch_cum(corp_code, year, current_reprt, cache)
    if cur_cum is None:
        return None

    # === 1Q 보고서 (분기 회사) ===
    if current_reprt == "11013":
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
        q1 = fetch_cum(corp_code, year, "11013", cache)
        if q1 is not None:
            return {
                "kind": "분기",
                "current":  {"revenue": cur_cum - q1, "report_date": f"{year}-06-30",
                             "report_type": f"{year} 2Q"},
                "previous": {"revenue": q1, "report_date": f"{year}-03-31",
                             "report_type": f"{year} 1Q"},
            }
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
        if h1 is not None:
            return {
                "kind": "반기",
                "current":  {"revenue": cur_cum - h1, "report_date": f"{year}-12-31",
                             "report_type": f"{year} H2"},
                "previous": {"revenue": h1, "report_date": f"{year}-06-30",
                             "report_type": f"{year} H1"},
            }
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


def compute_revenue(corp_code, cache, candidates):
    """후보 보고서를 우선순위대로 시도해 당기/전기 단독 매출 산출. dict | None."""
    for year, rcode in candidates:
        result = compute_periods(corp_code, year, rcode, cache)
        if result and result["current"]["revenue"] is not None:
            return {
                "kind": result["kind"],
                "current": result["current"],
                "previous": result["previous"],
            }
    return None


# ===================== 재무상태표/손익계산서(Financial) 추출 =====================

def extract_accounts(items, accounts_map, sj_div_set):
    """items 에서 라벨별 {y0, y1} 추출. y0=thstrm(당기), y1=frmtrm(전기)."""
    matched = {}
    for it in items or []:
        sj = (it.get("sj_div") or "").strip()
        if sj not in sj_div_set:
            continue
        nm = (it.get("account_nm") or "").strip()
        if nm and nm not in matched:
            matched[nm] = it

    out = {}
    for label, names in accounts_map.items():
        target = None
        for n in names:
            if n in matched:
                target = matched[n]
                break
        if target is None:
            out[label] = {"y0": None, "y1": None}
        else:
            out[label] = {
                "y0": parse_amount(target.get("thstrm_amount")),
                "y1": parse_amount(target.get("frmtrm_amount")),
            }
    return out


def compute_nonop_net(is_data):
    """영업외손익 미보고 시 영업외수익 − 영업외비용으로 계산."""
    no = is_data.get("영업외손익", {"y0": None, "y1": None})
    inc = is_data.get("영업외수익", {"y0": None, "y1": None})
    exp = is_data.get("영업외비용", {"y0": None, "y1": None})
    for k in ("y0", "y1"):
        if no.get(k) is None and inc.get(k) is not None and exp.get(k) is not None:
            no[k] = inc[k] - exp[k]
    is_data["영업외손익"] = no
    return is_data


def _end_date(s):
    """DART 기간 문자열 → 기말일 'YYYY.MM.DD'.
    '2024.12.31 현재' → '2024.12.31', '2024.01.01 ~ 2024.12.31' → '2024.12.31'."""
    if not s:
        return None
    s = str(s)
    if "~" in s:
        s = s.split("~")[-1]
    m = re.search(r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", s)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{y}.{int(mo):02d}.{int(d):02d}"


def extract_period_dates(items):
    """당기(y0)/전기(y1) 기준일(기말일) 추출. BS 우선, 없으면 IS."""
    y0 = y1 = None
    for sj_target in (("BS",), ("IS", "CIS")):
        for it in items or []:
            if (it.get("sj_div") or "").strip() not in sj_target:
                continue
            if y0 is None:
                y0 = _end_date(it.get("thstrm_dt"))
            if y1 is None:
                y1 = _end_date(it.get("frmtrm_dt"))
            if y0 and y1:
                return y0, y1
        if y0 and y1:
            break
    return y0, y1


def compute_financial(corp_code, cache, target_year):
    """연간 사업보고서(11011) 연말 BS/IS 추출. 공유 캐시 재사용. dict | None."""
    for y in (target_year, target_year - 1):
        items = get_report(corp_code, y, "11011", cache)
        if not items:
            continue
        bs = extract_accounts(items, BS_ACCOUNTS, {"BS"})
        is_ = extract_accounts(items, IS_ACCOUNTS, {"IS", "CIS"})
        is_ = compute_nonop_net(is_)
        if is_["영업이익"]["y0"] is not None or is_["영업이익"]["y1"] is not None:
            y0_date, y1_date = extract_period_dates(items)
            return {
                "report_year": y, "bs": bs, "is": is_,
                "y0_date": y0_date, "y1_date": y1_date,
            }
    return None


# ===================== 유니버스 / 체크포인트 / 완료마커 =====================

def load_universe():
    if os.path.exists(LISTED_PATH):
        path = LISTED_PATH
    elif os.path.exists(INDUSTRY_PATH):
        path = INDUSTRY_PATH
        print("  주의: listed_stocks.json 없음 → industry_mapping.json 사용")
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


def load_progress():
    if not os.path.exists(PROGRESS_PATH):
        return {}
    try:
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"  주의: 진행 파일 손상 ({e}), 무시")
    return {}


def save_progress(progress):
    tmp = PROGRESS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, PROGRESS_PATH)


def clear_progress():
    if os.path.exists(PROGRESS_PATH):
        try:
            os.remove(PROGRESS_PATH)
        except OSError:
            pass


def write_done_marker(now_kst, rev_n, fin_n):
    try:
        with open(DONE_PATH, "w", encoding="utf-8") as f:
            json.dump({"date": now_kst.isoformat(), "revenue": rev_n, "financial": fin_n},
                      f, ensure_ascii=False)
    except OSError:
        pass


def recently_done(now_kst):
    """직전 성공 갱신이 REFRESH_INTERVAL_DAYS 내면 True (FORCE_REFRESH 시 항상 False)."""
    if os.environ.get("FORCE_REFRESH", "").strip() in ("1", "true", "True"):
        return False
    if not os.path.exists(DONE_PATH):
        return False
    try:
        with open(DONE_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        last = datetime.fromisoformat(d["date"])
        return (now_kst - last).days < REFRESH_INTERVAL_DAYS
    except Exception:
        return False


# ===================== 출력 =====================

def write_revenue_json(now_kst, records, universe_size):
    companies = []
    for cc, rec in records:
        rev = rec["rev"]
        if not rev:
            continue
        companies.append({
            "stock_code": rec["stock_code"],
            "name": rec["name"],
            "kind": rev["kind"],
            "current": rev["current"],
            "previous": rev["previous"],
        })
    out = {
        "generated_at": now_kst.isoformat(),
        "source": "DART OpenAPI fnlttSinglAcntAll (통합)",
        "count": len(companies),
        "universe_size": universe_size,
        "success_ratio": round(len(companies) / universe_size, 4) if universe_size else 0,
        "companies": companies,
    }
    with open(REVENUE_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return len(companies)


def write_financial_json(now_kst, records, universe_size, target_year):
    companies = []
    for cc, rec in records:
        fin = rec["fin"]
        if not fin:
            continue
        companies.append({
            "stock_code": rec["stock_code"],
            "name": rec["name"],
            "report_year": fin["report_year"],
            "bs": fin["bs"],
            "is": fin["is"],
            "y0_date": fin["y0_date"],
            "y1_date": fin["y1_date"],
        })
    out = {
        "generated_at": now_kst.isoformat(),
        "source": "DART OpenAPI fnlttSinglAcntAll (사업보고서, 통합)",
        "target_year": target_year,
        "count": len(companies),
        "universe_size": universe_size,
        "success_ratio": round(len(companies) / universe_size, 4) if universe_size else 0,
        "companies": companies,
    }
    with open(FIN_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return len(companies)


# ===================== main =====================

def main():
    now_kst = datetime.now(timezone.utc).astimezone(KST)
    print(f"[현재 시각] {now_kst.isoformat()}")

    universe = load_universe()
    n_uni = len(universe)
    print(f"  Universe: {n_uni:,}개 상장사")
    if n_uni == 0:
        print("ERROR: universe 비어있음")
        sys.exit(1)

    candidates = get_target_reports(now_kst)
    target_year = now_kst.year - 1 if now_kst.month >= 4 else now_kst.year - 2
    print(f"  매출 후보 보고서: {candidates}")
    print(f"  재무 사업보고서 연도: {target_year} (실패 시 {target_year - 1})")

    os.makedirs(DATA_DIR, exist_ok=True)
    progress = load_progress()

    # ---- self-heal: 전체 시도했으나 저성공률(교착) → 체크포인트 리셋 ----
    if progress:
        attempted_all = all(c["corp_code"] in progress for c in universe)
        rev_ok = sum(1 for v in progress.values() if v and v.get("rev"))
        fin_ok = sum(1 for v in progress.values() if v and v.get("fin"))
        print(f"  체크포인트 복원: {len(progress):,}개 / 매출성공 {rev_ok:,} / 재무성공 {fin_ok:,}")
        if attempted_all and (rev_ok / n_uni < MIN_SUCCESS_RATIO
                              or fin_ok / n_uni < MIN_SUCCESS_RATIO):
            print("  [self-heal] 전체 시도·저성공률(교착) 감지 → 체크포인트 리셋, 처음부터 재수집")
            progress = {}
            clear_progress()
    else:
        print("  체크포인트 없음 → 처음부터 시작")

    # ---- 완료 마커 쿨다운: 최근 성공 갱신 + 진행 중인 작업 없음 → 건너뜀 ----
    if not progress and recently_done(now_kst):
        print(f"  최근 {REFRESH_INTERVAL_DAYS}일 내 갱신 완료됨 → 이번 실행 건너뜀 "
              f"(강제: FORCE_REFRESH=1)")
        sys.exit(0)

    pending = [c for c in universe if c["corp_code"] not in progress]
    print(f"  이번 실행 처리 대상: {len(pending):,}개")

    t0 = time.monotonic()
    save_lock = threading.Lock()

    def task(c):
        cc, sc, nm = c["corp_code"], c["stock_code"], c["name"]
        if _QUOTA_HIT.is_set():
            return cc, "SKIP"
        cache = {}
        rev = compute_revenue(cc, cache, candidates)
        fin = compute_financial(cc, cache, target_year)
        time.sleep(SLEEP_SEC)
        if _QUOTA_HIT.is_set():
            # 처리 중 한도 도달 → 통째로 다음 실행에서 재시도 (pending 유지)
            return cc, "SKIP"
        return cc, {"stock_code": sc, "name": nm, "rev": rev, "fin": fin}

    if pending:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(task, c): c for c in pending}
            done = 0
            for fut in as_completed(futures):
                c = futures[fut]
                done += 1
                try:
                    cc, r = fut.result()
                except Exception as e:
                    cc, r = c["corp_code"], {"stock_code": c["stock_code"],
                                            "name": c["name"], "rev": None, "fin": None}
                    print(f"  예외 {c['stock_code']}: {e}")
                if r == "SKIP":
                    continue   # 한도로 미처리 → pending 유지
                progress[cc] = r

                if done % SAVE_EVERY == 0:
                    with save_lock:
                        save_progress(progress)
                    rok = sum(1 for v in progress.values() if v and v.get("rev"))
                    fok = sum(1 for v in progress.values() if v and v.get("fin"))
                    print(f"  진행 (이번 {done:,}/{len(pending):,}) 누적 {len(progress):,}/{n_uni:,} "
                          f"매출 {rok:,} 재무 {fok:,} [저장]")
        with save_lock:
            save_progress(progress)

    elapsed = time.monotonic() - t0

    # ---- 한도 도달: 부분 저장 후 정상 종료(다음 실행 이어서 수집) ----
    if _QUOTA_HIT.is_set():
        remaining = sum(1 for c in universe if c["corp_code"] not in progress)
        rok = sum(1 for v in progress.values() if v and v.get("rev"))
        fok = sum(1 for v in progress.values() if v and v.get("fin"))
        print(f"\n[DART 일일 한도 도달] 이번 실행 중단 — 미처리 {remaining:,}개는 다음 실행에서 이어서 수집.")
        print(f"  현재 누적: 매출 {rok:,} / 재무 {fok:,} / 전체 {n_uni:,}  (소요 {elapsed/60:.1f}분)")
        sys.exit(0)   # 한도는 정상 상황 — crash 아님

    # ---- 미완료(예외적): 전체 시도 못 했으면 진행 저장 후 종료(다음 실행 재개) ----
    if not all(c["corp_code"] in progress for c in universe):
        print("\n  일부 미처리 — 진행 저장 후 종료 (다음 실행 재개)")
        sys.exit(0)

    # ---- 전체 시도 완료: 출력 생성 ----
    records = [(cc, v) for cc, v in progress.items() if v]
    rev_n = sum(1 for _, v in records if v.get("rev"))
    fin_n = sum(1 for _, v in records if v.get("fin"))
    rev_ratio = rev_n / n_uni
    fin_ratio = fin_n / n_uni
    print(f"\n  최종: 매출 {rev_n:,} ({rev_ratio*100:.1f}%) / 재무 {fin_n:,} ({fin_ratio*100:.1f}%) "
          f"/ 전체 {n_uni:,}  (소요 {elapsed/60:.1f}분)")

    if rev_ratio < MIN_SUCCESS_RATIO or fin_ratio < MIN_SUCCESS_RATIO:
        # 저성공 → 기존 출력 보존(갱신 보류). 진행 파일 유지 → 다음 실행 self-heal 재시도.
        print(f"\n[비정상 감지] 성공률 미달({MIN_SUCCESS_RATIO*100:.0f}%) → json 갱신 보류, 기존 데이터 유지.")
        print("  다음 실행에서 체크포인트 self-heal 후 재시도.")
        sys.exit(0)   # crash-loop 방지

    wrote_rev = write_revenue_json(now_kst, records, n_uni)
    wrote_fin = write_financial_json(now_kst, records, n_uni, target_year)
    clear_progress()
    write_done_marker(now_kst, wrote_rev, wrote_fin)
    print(f"\n저장 완료:")
    print(f"  - revenue.json          {wrote_rev:,}개")
    print(f"  - financial_status.json {wrote_fin:,}개")
    print(f"  체크포인트 정리 + 완료 마커 기록 (향후 {REFRESH_INTERVAL_DAYS}일 내 재실행은 건너뜀)")


if __name__ == "__main__":
    main()
