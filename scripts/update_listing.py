# -*- coding: utf-8 -*-
"""
KIND -> data/listing.json  (Market · Equity · 신규상장/폐지)

Railway 'Listing/Daily' 서비스에서 매일 23:00 KST(=14:00 UTC) cron 으로 실행.

수집 대상 (최근 3개월, 스팩(SPAC) 제외):
  - 신규상장 : 회사명 / 상장일 / 업종
      소스: KIND 상장법인목록 corpList.do (현재 상장 중 전체 목록에서 상장일 필터)
  - 상장폐지 : 회사명 / 폐지일자 / 폐지사유  (사유 무관 전체)
      소스: KIND 상장폐지현황 delcompany.do (fromDate~toDate 범위 조회)

동작 모드:
  - 부트스트랩(최초): data-snapshot 에 listing.json 이 없으면 최근 3개월 전체를 수집.
  - 증분(이후 매일): 기존 listing.json 을 불러와 "당일" 자료만 추가 병합하고,
      3개월보다 오래된 항목은 잘라냄(rolling window). 매번 3개월 전체를 재수집하지 않음.

환경변수:
  GH_REPO   기존 데이터를 읽어올 repo (기본 ConnectFinKorea/fin-visual)
            push 는 run_listing_daily.sh -> push_to_snapshot.sh 가 GH_PAT/GH_REPO 로 수행.
"""

import calendar
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "data")
OUT_PATH = os.path.join(OUT_DIR, "listing.json")

GH_REPO = os.environ.get("GH_REPO", "ConnectFinKorea/fin-visual").strip()
SNAPSHOT_LISTING_URL = (
    f"https://raw.githubusercontent.com/{GH_REPO}/data-snapshot/listing.json"
)

# 신규상장: 상장법인목록 다운로드 (searchType 13/14 = 시장구분, 합쳐서 union)
CORP_LIST_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType={st}"
# 상장폐지: 폐지현황 조회 (fromDate~toDate)
DEL_URL = (
    "https://kind.krx.co.kr/investwarn/delcompany.do"
    "?method=searchDelCompanySub&forward=delcompany_down"
    "&currentPageSize=3000&pageIndex=1&fromDate={f}&toDate={t}"
)

SPAC_RE = re.compile(r"스팩|기업인수목적|SPAC", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_spac(name: str) -> bool:
    return bool(SPAC_RE.search(name or ""))


def fetch_text(url: str, encoding: str = "euc-kr") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    return raw.decode(encoding, errors="replace")


def _cell(tds, i):
    return re.sub(r"\s+", " ", tds[i].get_text(strip=True)).strip() if i < len(tds) else ""


def load_existing():
    """data-snapshot 의 현재 listing.json 을 읽는다. 없으면 None (부트스트랩)."""
    try:
        url = SNAPSHOT_LISTING_URL + f"?t={int(time.time())}"
        txt = fetch_text(url, encoding="utf-8")
        data = json.loads(txt)
        if isinstance(data, dict) and ("new_listings" in data or "delistings" in data):
            return data
    except Exception as e:
        print(f"  기존 listing.json 없음/로드 실패 -> 부트스트랩 ({e})")
    return None


def crawl_new_listings(cutoff: str, upto: str):
    """상장일이 [cutoff, upto] 범위인 신규상장 (스팩 제외). dict[(name,date)] = row."""
    out = {}
    for st in ("13", "14"):
        html = fetch_text(CORP_LIST_URL.format(st=st))
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue
            name = _cell(tds, 0)
            sector = _cell(tds, 3)
            ldate = _cell(tds, 5)
            if not DATE_RE.match(ldate):
                continue
            if not (cutoff <= ldate <= upto):
                continue
            if is_spac(name):
                continue
            out[(name, ldate)] = {"name": name, "date": ldate, "sector": sector}
    return list(out.values())


def crawl_delistings(from_date: str, to_date: str):
    """폐지일자가 [from_date, to_date] 범위인 상장폐지 (사유 무관, 스팩 제외)."""
    html = fetch_text(DEL_URL.format(f=from_date, t=to_date))
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        name = _cell(tds, 1)     # 번호(0) 회사명(1) 종목코드(2) 폐지일자(3) 폐지사유(4) 비고(5)
        ddate = _cell(tds, 3)
        reason = _cell(tds, 4)
        if not DATE_RE.match(ddate):
            continue
        if not (from_date <= ddate <= to_date):
            continue
        if is_spac(name):
            continue
        out[(name, ddate)] = {"name": name, "date": ddate, "reason": reason}
    return list(out.values())


def merge_prune(existing_list, incoming_list, cutoff: str, key_fields):
    """기존 + 신규 병합(동일 키 덮어쓰기) 후 date < cutoff 인 항목 제거."""
    def key(r):
        return tuple(r.get(k, "") for k in key_fields)
    merged = {key(r): r for r in (existing_list or [])}
    for r in incoming_list:
        merged[key(r)] = r
    kept = [r for r in merged.values() if r.get("date", "") >= cutoff]
    kept.sort(key=lambda r: r.get("date", ""), reverse=True)
    return kept


def minus_3_months(d: datetime) -> datetime:
    m = d.month - 3
    y = d.year
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return d.replace(year=y, month=m, day=day)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    cutoff = minus_3_months(now).strftime("%Y-%m-%d")
    print(f"[Listing] 기준일 {today} · 3개월 cutoff {cutoff}")

    existing = load_existing()
    bootstrap = existing is None

    if bootstrap:
        print("[모드] 부트스트랩 — 최근 3개월 전체 수집")
        new_items = crawl_new_listings(cutoff, today)
        del_items = crawl_delistings(cutoff, today)
    else:
        print("[모드] 증분 — 당일 자료만 병합")
        new_today = crawl_new_listings(today, today)
        del_today = crawl_delistings(today, today)
        print(f"  당일 신규상장 {len(new_today)}건 · 당일 상장폐지 {len(del_today)}건")
        new_items = merge_prune(existing.get("new_listings", []), new_today, cutoff, ("name", "date"))
        del_items = merge_prune(existing.get("delistings", []), del_today, cutoff, ("name", "date"))

    new_items.sort(key=lambda r: r["date"], reverse=True)
    del_items.sort(key=lambda r: r["date"], reverse=True)

    output = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "reference_date": today,
        "source": "KRX KIND",
        "window_months": 3,
        "spac_excluded": True,
        "new_listings": new_items,
        "delistings": del_items,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    today_new = sum(1 for r in new_items if r["date"] == today)
    today_del = sum(1 for r in del_items if r["date"] == today)
    print(f"\n저장 완료: {OUT_PATH}")
    print(f"  신규상장 총 {len(new_items)}건 (당일 {today_new}건)")
    print(f"  상장폐지 총 {len(del_items)}건 (당일 {today_del}건)")


if __name__ == "__main__":
    main()
