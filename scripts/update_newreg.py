# -*- coding: utf-8 -*-
"""
DART -> data/newreg.json  (Market · Equity · 신규등록)

"신규등록" = 조회기준일 시점 감사보고서 이력이 최신 1개 결산기간뿐인 회사(첫 등록).
Railway 'Newreg/Weekly' 서비스에서 매주 금 21:00 KST(=12:00 UTC) cron 실행.

수집(감사보고서/연결감사보고서, 스팩 제외):
  회사명 / 보고서명 / 접수일 / 외부감사인(flr_nm) / 자산·부채·자본총액 / 매출·영업이익·당기순이익
  재무수치 우선순위: 연결감사보고서 → 일반(별도)감사보고서.

동작 모드:
  - 부트스트랩(최초): list.json(pblntf_ty=F)을 최근 BULK_YEARS년(3개월 청크)으로 bulk 스캔.
      corp별 distinct 결산기간 집계 → (기간수==1 AND 최신 접수일이 RECENT_DAYS 이내)=신규등록.
      list.json 은 corp_code 없으면 검색기간 최대 3개월 제한 → 청크 분할 필수.
  - 증분(이후 매주): 지난 SCAN_BACK일 접수분 스캔 → 신규 첫 등록 추가.
      + 에이징: 기존 목록 회사가 2번째 기수를 올렸으면 제외(회사별 이력 재확인).

체크포인트: data/_newreg_progress.json (스캔결과 candidates + 추출완료 done). 중단 시 재개.

환경변수:
  OPENDART_API_KEY  OpenDART 인증키
  GH_REPO           기존 newreg.json 로드용 (기본 ConnectFinKorea/fin-visual)
"""

import calendar
import io
import json
import os
import re
import sys
import time
import urllib.request
import warnings
import zipfile
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

KEY = os.environ.get("OPENDART_API_KEY", "").strip()
if not KEY:
    print("ERROR: OPENDART_API_KEY 환경변수가 없습니다.")
    sys.exit(1)

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "data")
OUT_PATH = os.path.join(OUT_DIR, "newreg.json")
PROG_PATH = os.path.join(OUT_DIR, "_newreg_progress.json")

GH_REPO = os.environ.get("GH_REPO", "ConnectFinKorea/fin-visual").strip()
SNAPSHOT_URL = f"https://raw.githubusercontent.com/{GH_REPO}/data-snapshot/newreg.json"

BULK_YEARS = 4        # 부트스트랩 이력 스캔 범위(년)
RECENT_DAYS = 365     # "최신 접수일" 인정 범위(=12개월). 이보다 오래된 단일등록은 제외.
SCAN_BACK = 10        # 증분: 지난 N일 접수분 스캔(겹침 여유)
PERIOD_RE = re.compile(r"\((\d{4})[.\-/](\d{2})\)")
DATE_RE = re.compile(r"^\d{8}$")


# ============ HTTP ============
def _get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def api_list(**kw):
    kw.setdefault("crtfc_key", KEY)
    q = "&".join(f"{k}={v}" for k, v in kw.items())
    for attempt in range(3):
        try:
            return json.loads(_get("https://opendart.fss.or.kr/api/list.json?" + q, timeout=30).decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1.5)


def list_all(bgn, end):
    """corp_code 없이 3개월 이내 구간 전체 페이지 수집."""
    out = []
    d = api_list(bgn_de=bgn, end_de=end, pblntf_ty="F", page_no=1, page_count=100)
    if d.get("status") == "013":
        return out
    if d.get("status") != "000":
        raise RuntimeError(f"list.json {bgn}~{end}: {d.get('status')} {d.get('message')}")
    out += d.get("list", [])
    tp = int(d.get("total_page", 1))
    for p in range(2, tp + 1):
        dp = api_list(bgn_de=bgn, end_de=end, pblntf_ty="F", page_no=p, page_count=100)
        out += dp.get("list", [])
        time.sleep(0.02)
    return out


def corp_period_count(corp_code):
    """회사별 전체 F-이력의 distinct 결산기간 수(감사보고서 계열)."""
    d = api_list(corp_code=corp_code, bgn_de="20000101", end_de=_today_str(), pblntf_ty="F",
                 page_no=1, page_count=100)
    if d.get("status") not in ("000", "013"):
        return None
    periods = set()
    for it in d.get("list", []):
        nm = it.get("report_nm", "")
        if "감사보고서" not in nm:
            continue
        m = PERIOD_RE.search(nm)
        periods.add(m.group(1) + m.group(2) if m else "?" + it.get("rcept_dt", "")[:6])
    return len(periods)


# ============ 재무 추출 (document.xml) ============
_AMOUNT = re.compile(r"^\(?-?\d{1,3}(?:,\d{3})+\)?$")
ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
BS = {"자산총계": {"자산총계"}, "부채총계": {"부채총계"}, "자본총계": {"자본총계"}}
IS = {
    "매출액": {"매출액", "영업수익", "수익매출액"},
    "영업이익": {"영업이익", "영업이익손실", "영업손실"},
    "당기순이익": {"당기순이익", "당기순이익손실", "당기순손실", "반기순이익", "분기순이익", "반기순손실", "분기순손실"},
}
LOSS_LABELS = {"영업손실", "당기순손실", "반기순손실", "분기순손실"}


def _num(s):
    s = (s or "").strip().replace(" ", "").replace("△", "-").replace("▲", "-").replace("−", "-")
    if s in ("", "-", "－", "–"):
        return None
    if s == "0":
        return 0
    if not _AMOUNT.match(s):
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.startswith("-"):
        neg, s = True, s[1:]
    v = int(s.replace(",", ""))
    return -v if neg else v


def _clean(label):
    s = re.sub(r"\([^)]*\)", "", label)
    s = re.sub(rf"[{ROMAN}]+\.?", "", s)
    s = re.sub(r"^\s*[IVXLCDM]+\s*[.)]\s*", "", s)
    s = re.sub(r"^\s*\d+\s*[.)]", "", s)
    return re.sub(r"\s+", "", s)


def _first_num(cells):
    for c in cells[1:]:
        n = _num(c.get_text())
        if n is not None:
            return n
    return None


def _table_has(t, needed):
    txt = re.sub(r"\s+", "", t.get_text())
    return all(any(a in txt for a in al) for al in needed)


def extract_financials(xml_text):
    soup = BeautifulSoup(xml_text, "html.parser")
    tables = soup.find_all("table")
    out = {k: None for k in ["자산총계", "부채총계", "자본총계", "매출액", "영업이익", "당기순이익"]}
    # 재무상태표
    for t in tables:
        if _table_has(t, list(BS.values())):
            got = {}
            for tr in t.find_all("tr"):
                cells = tr.find_all(["td", "te", "tu", "th"])
                if not cells:
                    continue
                lab = _clean(cells[0].get_text())
                for key, al in BS.items():
                    if key not in got and lab in al:
                        n = _first_num(cells)
                        if n is not None:
                            got[key] = n
            if len(got) == 3:
                out.update(got)
                break
    # 손익계산서
    for t in tables:
        if _table_has(t, list(IS.values())):
            got = {}
            for tr in t.find_all("tr"):
                cells = tr.find_all(["td", "te", "tu", "th"])
                if not cells:
                    continue
                lab = _clean(cells[0].get_text())
                for key, al in IS.items():
                    if key not in got and lab in al:
                        n = _first_num(cells)
                        if n is not None:
                            got[key] = -abs(n) if lab in LOSS_LABELS else n
            if got:
                out.update({k: v for k, v in got.items()})
                break
    return out


def fetch_financials(rcept_no):
    data = _get(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={KEY}&rcept_no={rcept_no}")
    zf = zipfile.ZipFile(io.BytesIO(data))
    xml = zf.read(max(zf.namelist(), key=lambda n: zf.getinfo(n).file_size)).decode("utf-8", "replace")
    return extract_financials(xml)


# ============ 날짜 유틸 ============
def _now():
    return datetime.now(KST)


def _today_str():
    return _now().strftime("%Y%m%d")


def _minus_years(d, y):
    try:
        return d.replace(year=d.year - y)
    except ValueError:
        return d.replace(year=d.year - y, day=28)


def three_month_chunks(start, end):
    """[start, end] 를 3개월 이하 구간(YYYYMMDD)들로 분할."""
    chunks = []
    cur = start
    while cur <= end:
        m = cur.month + 2
        y = cur.year
        while m > 12:
            m -= 12
            y += 1
        last = calendar.monthrange(y, m)[1]
        ce = min(datetime(y, m, last, tzinfo=cur.tzinfo), end)
        chunks.append((cur.strftime("%Y%m%d"), ce.strftime("%Y%m%d")))
        cur = ce + timedelta(days=1)
    return chunks


# ============ 공통: 필터/그룹 ============
def is_audit(nm):
    return "감사보고서" in (nm or "")


def is_spac(name):
    return "스팩" in (name or "") or re.search(r"기업인수목적|SPAC", name or "", re.I) is not None


def group_by_corp(items):
    """감사보고서 접수분을 corp별로 묶어 distinct 기간 + 최신보고서(연결 우선) 집계."""
    corps = {}
    for it in items:
        nm = it.get("report_nm", "")
        if not is_audit(nm) or is_spac(it.get("corp_name")):
            continue
        cc = it["corp_code"]
        g = corps.setdefault(cc, {"corp_code": cc, "name": it["corp_name"], "cls": it.get("corp_cls", ""),
                                  "periods": set(), "con": None, "sep": None, "latest_dt": ""})
        m = PERIOD_RE.search(nm)
        g["periods"].add(m.group(1) + m.group(2) if m else "?" + it.get("rcept_dt", "")[:6])
        g["latest_dt"] = max(g["latest_dt"], it.get("rcept_dt", ""))
        kind = "con" if "연결감사보고서" in nm else "sep"
        rep = {"rcept_no": it["rcept_no"], "rcept_dt": it["rcept_dt"], "report_nm": nm,
               "auditor": it.get("flr_nm", "")}
        if g[kind] is None or it["rcept_dt"] > g[kind]["rcept_dt"]:
            g[kind] = rep
    return corps


def build_row(g):
    rep = g["con"] or g["sep"]
    fin = fetch_financials(rep["rcept_no"])
    return {
        "회사명": g["name"], "corp_code": g["corp_code"], "rcept_no": rep["rcept_no"],
        "보고서명": rep["report_nm"], "접수일": rep["rcept_dt"], "외부감사인": rep["auditor"],
        "자산총액": fin["자산총계"], "부채총액": fin["부채총계"], "자본총액": fin["자본총계"],
        "매출액": fin["매출액"], "영업이익": fin["영업이익"], "당기순이익": fin["당기순이익"],
    }


# ============ 진행상황 저장 ============
def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_existing():
    """data-snapshot 의 현재 newreg.json (증분 기준)."""
    try:
        txt = _get(SNAPSHOT_URL + f"?t={int(time.time())}", timeout=30).decode("utf-8")
        d = json.loads(txt)
        if isinstance(d, dict) and "rows" in d:
            return d
    except Exception as e:
        print(f"  기존 newreg.json 없음/로드 실패 -> 부트스트랩 ({e})")
    return None


# ============ 부트스트랩 ============
def run_bootstrap():
    now = _now()
    today = now.strftime("%Y-%m-%d")
    recent_cut = (now - timedelta(days=RECENT_DAYS)).strftime("%Y%m%d")
    print(f"[부트스트랩] 기준일 {today} · 이력 {BULK_YEARS}년 · 최신접수 컷 {recent_cut}")

    prog = load_json(PROG_PATH) or {}
    if not prog.get("candidates"):
        # ---- 1) bulk 스캔 ----
        start = _minus_years(now, BULK_YEARS)
        chunks = three_month_chunks(start, now)
        corps = {}
        for i, (b, e) in enumerate(chunks):
            items = list_all(b, e)
            for cc, g in group_by_corp(items).items():
                if cc not in corps:
                    corps[cc] = g
                else:
                    corps[cc]["periods"] |= g["periods"]
                    corps[cc]["latest_dt"] = max(corps[cc]["latest_dt"], g["latest_dt"])
                    for k in ("con", "sep"):
                        if g[k] and (corps[cc][k] is None or g[k]["rcept_dt"] > corps[cc][k]["rcept_dt"]):
                            corps[cc][k] = g[k]
            print(f"  스캔 {i+1}/{len(chunks)} [{b}~{e}] {len(items)}건 · 누적corp {len(corps)}")
        # ---- 2) 신규등록 후보 = 기간수 1 AND 최신접수 recent_cut 이후 ----
        cands = [g for g in corps.values()
                 if len(g["periods"]) == 1 and g["latest_dt"] >= recent_cut]
        prog = {"candidates": [{"corp_code": g["corp_code"], "name": g["name"],
                                "con": g["con"], "sep": g["sep"], "latest_dt": g["latest_dt"]}
                               for g in cands], "done": {}}
        save_json(PROG_PATH, prog)
        print(f"  신규등록 후보 {len(cands)}개")

    # ---- 3) 재무추출 (체크포인트) ----
    done = prog["done"]
    cands = prog["candidates"]
    for i, c in enumerate(cands):
        if c["corp_code"] in done:
            continue
        g = {"corp_code": c["corp_code"], "name": c["name"], "con": c["con"], "sep": c["sep"]}
        try:
            done[c["corp_code"]] = build_row(g)
        except Exception as ex:
            print(f"    [추출실패] {c['name']}: {ex}")
            done[c["corp_code"]] = None
        if (i + 1) % 25 == 0:
            save_json(PROG_PATH, prog)
            print(f"  추출 {i+1}/{len(cands)}")
        time.sleep(0.03)

    rows = [r for r in done.values() if r]
    return rows, today


# ============ 증분 ============
def run_incremental(existing):
    now = _now()
    today = now.strftime("%Y-%m-%d")
    recent_cut = (now - timedelta(days=RECENT_DAYS)).strftime("%Y%m%d")
    prev_rows = existing.get("rows", [])
    by_code = {r["corp_code"]: r for r in prev_rows}
    print(f"[증분] 기존 {len(prev_rows)}건 · 지난 {SCAN_BACK}일 신규 스캔")

    # 1) 신규 접수분에서 첫 등록 추가
    start = (now - timedelta(days=SCAN_BACK))
    items = []
    for b, e in three_month_chunks(start, now):
        items += list_all(b, e)
    added = 0
    for cc, g in group_by_corp(items).items():
        if cc in by_code:
            continue
        pc = corp_period_count(cc)
        if pc == 1 and g["latest_dt"] >= recent_cut:
            try:
                by_code[cc] = build_row(g)
                added += 1
            except Exception as ex:
                print(f"    [추출실패] {g['name']}: {ex}")
    # 2) 에이징: 기존 목록 재확인 → 2기수 이상이면 제외
    removed = 0
    for cc, r in list(by_code.items()):
        pc = corp_period_count(cc)
        if pc is not None and pc >= 2:
            del by_code[cc]
            removed += 1
    print(f"  추가 {added} · 제외(2기수) {removed}")
    return list(by_code.values()), today


# ============ main ============
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    existing = load_existing()
    if existing is None:
        rows, today = run_bootstrap()
    else:
        rows, today = run_incremental(existing)

    # 접수일 최신순
    rows.sort(key=lambda r: r.get("접수일", ""), reverse=True)
    output = {
        "timestamp": _now().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "reference_date": today,
        "source": "FSS DART",
        "definition": "조회기준일 시점 감사보고서 이력이 최신 1개 기간뿐인 회사",
        "spac_excluded": True,
        "count": len(rows),
        "rows": rows,
    }
    save_json(OUT_PATH, output)
    # 부트스트랩 완료 시 진행파일 정리
    if os.path.exists(PROG_PATH) and existing is None:
        try:
            os.remove(PROG_PATH)
        except OSError:
            pass
    print(f"\n저장 완료: {OUT_PATH} · 신규등록 {len(rows)}건")


if __name__ == "__main__":
    main()
