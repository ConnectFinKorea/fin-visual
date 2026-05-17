"""
DART 단일회사 주요계정(fnlttSinglAcntAll) → data/financial_status.json
- 매월 1회 자동 실행 (GitHub Actions)
- 가장 최신 사업보고서(11011) 기준 직전·직직전 연도말 BS/IS 추출
- 재무상태표 3계정 + 손익계산서 10계정
- 직전 연도 사업보고서 미공시(1~3월) → 그 전 연도로 폴백
- 체크포인트/재개 지원 (update_revenue.py와 동일 구조)

환경변수: DART_API_KEY
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
OUT_PATH = os.path.join(DATA_DIR, "financial_status.json")
PROGRESS_PATH = os.path.join(DATA_DIR, "_financial_progress.json")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
WORKERS = 8
TIMEOUT = 15
MAX_RETRY = 3
SLEEP_SEC = 0.05
SAVE_EVERY = 200
MIN_SUCCESS_RATIO = 0.50

# 계정명 후보 (DART account_nm). 우선순위 순서대로 첫 매치 채택.
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
        "법인세차감전순이익",
        "법인세비용차감전순이익",
        "법인세비용차감전계속사업이익",
        "법인세비용차감전순손익",
        "법인세차감전계속사업이익",
        "법인세차감전순손익",
        "법인세비용차감전순손익(손실)",
    ],
    "법인세":            ["법인세비용", "법인세"],
    "당기순이익":        ["당기순이익", "당기순이익(손실)", "연결당기순이익"],
}


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


def fetch_report(corp_code, year):
    """사업보고서(11011) 호출. CFS 우선, OFS fallback. list | None."""
    base = (
        f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
        f"?crtfc_key={API_KEY}&corp_code={corp_code}"
        f"&bsns_year={year}&reprt_code=11011"
    )
    for fs_div in ("CFS", "OFS"):
        data = _http_get_json(base + f"&fs_div={fs_div}")
        status = data.get("status")
        if status == "000" and data.get("list"):
            return data["list"]
        if status not in ("013", "020"):
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


def extract_accounts(items, accounts_map, sj_div_set):
    """
    items: DART list 응답.
    accounts_map: {라벨: [account_nm 후보, ...]}
    sj_div_set: 추출 대상 sj_div 집합 ({"BS"} 또는 {"IS", "CIS"})
    반환: {라벨: {"y0": int|None, "y1": int|None}}
      y0 = thstrm_amount (직전 연도말)
      y1 = frmtrm_amount (직직전 연도말)
    """
    # 1차: account_nm → item dict (sj_div 필터, 먼저 등장 우선)
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
    """영업외손익 직접 보고가 없으면 영업외수익 − 영업외비용으로 계산."""
    no = is_data.get("영업외손익", {"y0": None, "y1": None})
    inc = is_data.get("영업외수익", {"y0": None, "y1": None})
    exp = is_data.get("영업외비용", {"y0": None, "y1": None})
    for k in ("y0", "y1"):
        if no.get(k) is None and inc.get(k) is not None and exp.get(k) is not None:
            no[k] = inc[k] - exp[k]
    is_data["영업외손익"] = no
    return is_data


def fetch_one(corp_code, year):
    """직전·직직전 연도말 BS/IS 추출. year 사업보고서 우선, 실패시 year-1 폴백."""
    for y in (year, year - 1):
        items = fetch_report(corp_code, y)
        if not items:
            continue
        bs = extract_accounts(items, BS_ACCOUNTS, {"BS"})
        is_ = extract_accounts(items, IS_ACCOUNTS, {"IS", "CIS"})
        is_ = compute_nonop_net(is_)
        # 영업이익은 모든 회사 필수 — 둘 다 None이면 IS 파싱 실패로 간주
        if is_["영업이익"]["y0"] is not None or is_["영업이익"]["y1"] is not None:
            return {"report_year": y, "bs": bs, "is": is_}
    return None


def load_universe():
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


def main():
    import threading
    now_kst = datetime.now(timezone.utc).astimezone(KST)
    print(f"[현재 시각] {now_kst.isoformat()}")

    # 사업보고서 법정 마감 = 다음해 3/31.
    # 4월 이후라면 (y-1) 보고서가 모두 공시되어 있어야 함.
    # 1~3월이면 (y-2) 보고서까지가 안전.
    target_year = now_kst.year - 1 if now_kst.month >= 4 else now_kst.year - 2

    universe = load_universe()
    print(f"  Universe: {len(universe):,}개 상장사")
    print(f"  사업보고서 1순위 연도: {target_year}, 2순위: {target_year - 1}")

    progress = load_progress()
    if progress:
        prior_success = sum(1 for v in progress.values() if v)
        print(f"  체크포인트 복원: 시도 {len(progress):,}개 / 성공 {prior_success:,}개")
    else:
        print(f"  체크포인트 없음 → 처음부터 시작")

    pending = [c for c in universe if c["corp_code"] not in progress]
    print(f"  이번 실행 처리 대상: {len(pending):,}개")

    t0 = time.monotonic()

    def task(c):
        cc, sc, nm = c["corp_code"], c["stock_code"], c["name"]
        r = fetch_one(cc, target_year)
        time.sleep(SLEEP_SEC)
        if r is None:
            return cc, None
        return cc, {
            "stock_code": sc,
            "name": nm,
            "report_year": r["report_year"],
            "bs": r["bs"],
            "is": r["is"],
        }

    save_lock = threading.Lock()

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
                    cc, r = c["corp_code"], None
                    print(f"  예외 {c['stock_code']}: {e}")
                progress[cc] = r

                if done % SAVE_EVERY == 0:
                    with save_lock:
                        save_progress(progress)
                    cur_success = sum(1 for v in progress.values() if v)
                    pct_total = len(progress) / len(universe) * 100
                    print(f"  진행 (이번 {done:,}/{len(pending):,}) "
                          f"전체 {len(progress):,}/{len(universe):,} "
                          f"({pct_total:.1f}%) 누적성공 {cur_success:,} [저장]")
        with save_lock:
            save_progress(progress)

    elapsed = time.monotonic() - t0
    results = [v for v in progress.values() if v is not None]
    success_ratio = len(results) / len(universe) if universe else 0
    print(f"\n  최종: 성공 {len(results):,} / 전체 {len(universe):,} "
          f"(성공률 {success_ratio*100:.1f}%, 이번 실행 소요 {elapsed/60:.1f}분)")

    if success_ratio < MIN_SUCCESS_RATIO:
        print(f"\n[비정상 감지] 성공률 {success_ratio*100:.1f}% < {MIN_SUCCESS_RATIO*100:.0f}%")
        print(f"  financial_status.json 갱신 건너뜀. 진행 파일은 유지.")
        sys.exit(1)

    out = {
        "generated_at": now_kst.isoformat(),
        "source": "DART OpenAPI fnlttSinglAcntAll (사업보고서)",
        "target_year": target_year,
        "count": len(results),
        "universe_size": len(universe),
        "success_ratio": round(success_ratio, 4),
        "elapsed_min": round(elapsed / 60, 1),
        "companies": results,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    clear_progress()
    size_kb = os.path.getsize(OUT_PATH) // 1024
    print(f"\n저장 완료: {OUT_PATH} ({size_kb:,} KB)")
    print(f"  체크포인트 파일 삭제 — 다음 월간 실행은 fresh start")


if __name__ == "__main__":
    main()
