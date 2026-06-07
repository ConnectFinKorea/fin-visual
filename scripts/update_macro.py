"""
Macro Eco 지표 수집 → data/macro.json

구현: Prime Rate(기준금리) + Bond(10년 국채), 4개국(중국 일부), 2015-01~ 월별.
추후 확장: inflation / unemployment — collect_*() 추가만 하면 됨.
(Macro Eco 섹션 전체를 이 한 스크립트 = Railway 단일 일일 서비스로 운영)

소스 (전부 공식 API, 스크래핑 없음 — 2026-06 라이브 검증):
  기준금리 미/일/중: BIS CBPOL (stats.bis.org SDMX v2, 월말값, 키 불필요)
  기준금리 한국:     한국은행 ECOS 722Y001/0101000
  10년 국채 미국:    FRED DGS10 (월평균 집계)
  10년 국채 일본:    FRED IRLTLT01JPM156N (월, OECD)
  10년 국채 한국:    한국은행 ECOS 721Y001/5050000 (월)
  (10년 국채 중국은 무료 공식 API 없음 → 제외)

환경변수:
  ECOS_API_KEY  (필수) 한국은행 ECOS 인증키
  FRED_API_KEY  (필수) FRED API 키 (10년 국채 미국·일본)

출력 data/macro.json:
  { schema, generated_at, generated_at_full,
    prime: { title, unit, source, start, labels[YYYY-MM…], series{Korea,US,Japan,China} },
    bond:  { title, unit, source, start, labels[YYYY-MM…], series{Korea,US,Japan} } }
"""

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

KST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "macro.json")

START = "2015-01"                       # 자료 수집 시작 (사용자 지정)
UA = "Mozilla/5.0 (FinVisual macro collector)"
TIMEOUT = 30


# ===================== HTTP =====================

def http_get(url):
    """plain text GET (gzip 회피: Accept-Encoding identity)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8")


# ===================== 유틸 =====================

def months_range(start, end):
    """'YYYY-MM' start~end(둘 다 포함) 월 라벨 리스트."""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out, y, m = [], sy, sm
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def align_series(series_map, labels, ffill):
    """labels 순서로 정렬. ffill=True → 직전값 유지(계단함수형 정책금리용),
    선행 결측은 null. ffill=False → 관측된 달만 값, 나머지 null(연속형 채권금리용)."""
    out, last = [], None
    for lb in labels:
        if lb in series_map and series_map[lb] is not None:
            last = series_map[lb]
            out.append(round(last, 4))
        elif ffill:
            out.append(None if last is None else round(last, 4))
        else:
            out.append(None)
    return out


# ===================== 소스별 fetch =====================

def bis_cbpol(country):
    """BIS 중앙은행 정책금리(월말) → {'YYYY-MM': float}. country in US/JP/CN/KR."""
    url = (f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/M.{country}"
           f"?startPeriod={START}&format=csv")
    rows = list(csv.reader(io.StringIO(http_get(url))))
    if not rows:
        raise RuntimeError(f"BIS {country}: 빈 응답")
    header = rows[0]
    ti, vi = header.index("TIME_PERIOD"), header.index("OBS_VALUE")
    out = {}
    for row in rows[1:]:
        if len(row) <= max(ti, vi):
            continue
        t, v = row[ti].strip(), row[vi].strip()
        if len(t) == 7 and v:                 # 'YYYY-MM'
            try:
                out[t] = float(v)
            except ValueError:
                pass
    if not out:
        raise RuntimeError(f"BIS {country}: 파싱 0건")
    return out


def ecos_monthly(table, item, api_key):
    """ECOS 월별 통계 (table/item) → {'YYYY-MM': float}."""
    start = START.replace("-", "")                      # 201501
    end = datetime.now(KST).strftime("%Y%m")
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/1000/"
           f"{table}/M/{start}/{end}/{item}")
    data = json.loads(http_get(url))
    if "StatisticSearch" not in data:
        raise RuntimeError(f"ECOS {table}/{item} 응답 오류: {data.get('RESULT', data)}")
    out = {}
    for row in data["StatisticSearch"]["row"]:
        t, v = row.get("TIME", ""), row.get("DATA_VALUE", "")
        if len(t) == 6 and v not in (None, ""):
            try:
                out[f"{t[:4]}-{t[4:]}"] = float(v)
            except ValueError:
                pass
    if not out:
        raise RuntimeError(f"ECOS {table}/{item}: 파싱 0건")
    return out


def fred_monthly(series_id, agg=None):
    """FRED 월별 관측 → {'YYYY-MM': float}. agg='avg'/'eop'면 월별 집계, None이면 원천 주기.
    '.'(결측)은 skip."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FRED_API_KEY 환경변수 미설정 (10년 국채 미국·일본)")
    params = (f"series_id={series_id}&api_key={key}&file_type=json"
              f"&observation_start={START}-01")
    if agg:
        params += f"&frequency=m&aggregation_method={agg}"
    data = json.loads(http_get(f"https://api.stlouisfed.org/fred/series/observations?{params}"))
    out = {}
    for o in data.get("observations", []):
        v = o.get("value", ".")
        if v and v != ".":
            try:
                out[o["date"][:7]] = float(v)
            except ValueError:
                pass
    if not out:
        raise RuntimeError(f"FRED {series_id}: 파싱 0건")
    return out


# ===================== 지표: Prime Rate =====================

def collect_prime():
    api_key = os.environ.get("ECOS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ECOS_API_KEY 환경변수 미설정 (한국 기준금리)")
        sys.exit(1)

    print("[prime] 수집 — BIS CBPOL(US/JP/CN) + ECOS(KR)")
    src = {
        "US": bis_cbpol("US"),
        "Japan": bis_cbpol("JP"),
        "China": bis_cbpol("CN"),
        "Korea": ecos_monthly("722Y001", "0101000", api_key),
    }
    latest = max(max(d) for d in src.values())
    labels = months_range(START, latest)
    series = {name: align_series(d, labels, ffill=True) for name, d in src.items()}

    for name, d in src.items():
        mx = max(d)
        print(f"  {name:6s}: {len(d):3d}건  최신 {mx} = {d[mx]}")
    print(f"  타임라인 {labels[0]}~{labels[-1]} ({len(labels)}개월)")

    return {
        "title": "Prime Rate (기준금리)",
        "unit": "%",
        "source": "BIS, 한국은행(ECOS)",
        "start": START,
        "labels": labels,
        "series": {k: series[k] for k in ("Korea", "US", "Japan", "China")},
    }


# ===================== 지표: 10년 국채 =====================

def collect_bond():
    api_key = os.environ.get("ECOS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ECOS_API_KEY 환경변수 미설정 (한국 국고채)")
        sys.exit(1)

    print("[bond] 수집 — FRED(US DGS10 월평균 · JP IRLTLT01) + ECOS(KR 5050000). 중국 제외")
    src = {
        "US": fred_monthly("DGS10", agg="avg"),
        "Japan": fred_monthly("IRLTLT01JPM156N"),
        "Korea": ecos_monthly("721Y001", "5050000", api_key),
    }
    latest = max(max(d) for d in src.values())
    labels = months_range(START, latest)
    # 채권금리는 연속형 → forward-fill 안 함(관측 없는 달은 null)
    series = {name: align_series(d, labels, ffill=False) for name, d in src.items()}

    for name, d in src.items():
        mx = max(d)
        print(f"  {name:6s}: {len(d):3d}건  최신 {mx} = {d[mx]}")
    print(f"  타임라인 {labels[0]}~{labels[-1]} ({len(labels)}개월)")

    return {
        "title": "10Y Government Bond",
        "unit": "%",
        "source": "FRED(US·JP), 한국은행(ECOS)",
        "start": START,
        "labels": labels,
        "series": {k: series[k] for k in ("Korea", "US", "Japan")},   # 중국 제외
    }


# ===================== main =====================

def main():
    now = datetime.now(KST)
    out = {
        "schema": 1,
        "generated_at": now.strftime("%Y-%m-%d"),
        "generated_at_full": now.isoformat(),
        "prime": collect_prime(),
        "bond": collect_bond(),
        # 추후: "inflation": collect_inflation(), "unemp": collect_unemp(),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"저장 완료: {OUT_PATH} ({max(1, os.path.getsize(OUT_PATH) // 1024)} KB)")


if __name__ == "__main__":
    main()
