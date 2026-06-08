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


def ecos_monthly(table, item, api_key, start=None):
    """ECOS 월별 통계 (table/item) → {'YYYY-MM': float}. start='YYYY-MM'(기본 START)."""
    start = (start or START).replace("-", "")           # 201501
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


def fred_monthly(series_id, agg=None, start=None):
    """FRED 월별 관측 → {'YYYY-MM': float}. agg='avg'/'eop'면 월별 집계, None이면 원천 주기.
    start='YYYY-MM'(기본 START). '.'(결측)은 skip."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FRED_API_KEY 환경변수 미설정 (10년 국채·미국 CPI)")
    params = (f"series_id={series_id}&api_key={key}&file_type=json"
              f"&observation_start={start or START}-01")
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


# ===================== 지표: GDP 성장률 / Inflation (분기) =====================

def quarters_range(start, end):
    """'YYYY-Qn' start~end(포함) 분기 라벨."""
    sy, sq = start.split("-Q"); ey, eq = end.split("-Q")
    sy, sq, ey, eq = int(sy), int(sq), int(ey), int(eq)
    out, y, q = [], sy, sq
    while (y, q) <= (ey, eq):
        out.append(f"{y}-Q{q}")
        q += 1
        if q > 4:
            q, y = 1, y + 1
    return out


def _oecd_csv(url):
    """OECD SDMX csvfilewithlabels → [dict(헤더라벨→값)]."""
    rows = list(csv.reader(io.StringIO(http_get(url))))
    if not rows:
        return []
    header = rows[0]
    return [dict(zip(header, r)) for r in rows[1:]]


def oecd_qna_gdp_nsa(area):
    """OECD QNA 명목 GDP(현재가격·자국통화·원계열) 분기 레벨 → {'YYYY-Qn': float}.
    YoY 계산 위해 2014-Q1부터 수집. area = USA/JPN/KOR/CHN."""
    df = "OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_NATIO_CURR"
    url = (f"https://sdmx.oecd.org/public/rest/data/{df}/Q..{area}...B1GQ......."
           f"?startPeriod=2014-Q1&format=csvfilewithlabels")
    out = {}
    for d in _oecd_csv(url):
        if d.get("Price base") != "Current prices":
            continue
        if "Neither" not in d.get("Adjustment", ""):       # 원계열(NSA)만
            continue
        t, v = d.get("TIME_PERIOD", ""), d.get("OBS_VALUE", "")
        if t and v and t not in out:
            try:
                out[t] = float(v)
            except ValueError:
                pass
    if not out:
        raise RuntimeError(f"OECD QNA {area}: 명목GDP 파싱 0건")
    return out


def gdp_yoy(levels):
    """분기 레벨 {'YYYY-Qn': v} → 전년동기대비 증가율(%) {'YYYY-Qn': yoy}."""
    out = {}
    for q, v in levels.items():
        y, qq = q.split("-Q")
        prev = f"{int(y) - 1}-Q{qq}"
        if levels.get(prev):
            out[q] = round((v / levels[prev] - 1) * 100, 2)
    return out


def oecd_cpi_gy_monthly(area, g20=False):
    """OECD CPI 전년동월비(월) {'YYYY-MM': %}. 일본=COICOP2018, 중국=G20 prices.
    (미국·한국은 C2018에 없음 → FRED/ECOS 지수에서 계산)"""
    df = ("OECD.SDD.TPS,DSD_G20_PRICES@DF_G20_PRICES,1.0" if g20
          else "OECD.SDD.TPS,DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL,1.0")
    url = (f"https://sdmx.oecd.org/public/rest/data/{df}/{area}.M.N.CPI.PA._T.N.GY"
           f"?startPeriod=2015-01&format=csvfilewithlabels")
    out = {}
    for d in _oecd_csv(url):
        t, v = d.get("TIME_PERIOD", ""), d.get("OBS_VALUE", "")
        if len(t) == 7 and v:
            try:
                out[t] = float(v)
            except ValueError:
                pass
    return out


def index_to_monthly_yoy(idx):
    """월별 지수 {'YYYY-MM': v} → 전년동월비(%) {'YYYY-MM': yoy}."""
    out = {}
    for ym, v in idx.items():
        y, m = ym.split("-")
        prev = f"{int(y) - 1}-{m}"
        if idx.get(prev):
            out[ym] = (v / idx[prev] - 1) * 100
    return out


def monthly_yoy_to_quarterly(monthly):
    """월별 % {'YYYY-MM': pct} → 분기평균 {'YYYY-Qn': pct}."""
    buckets = {}
    for ym, v in monthly.items():
        y, m = ym.split("-")
        buckets.setdefault(f"{y}-Q{(int(m) - 1) // 3 + 1}", []).append(v)
    return {q: round(sum(xs) / len(xs), 2) for q, xs in buckets.items()}


def ecos_quarterly(table, item, api_key, start="2014"):
    """ECOS 분기 통계 → {'YYYY-Qn': float}. TIME 'YYYYQn' → 'YYYY-Qn'."""
    end = datetime.now(KST).strftime("%Y") + "Q4"
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/500/"
           f"{table}/Q/{start}Q1/{end}/{item}")
    data = json.loads(http_get(url))
    if "StatisticSearch" not in data:
        raise RuntimeError(f"ECOS {table}/{item} 응답 오류: {data.get('RESULT', data)}")
    out = {}
    for row in data["StatisticSearch"]["row"]:
        t, v = row.get("TIME", ""), row.get("DATA_VALUE", "")
        if "Q" in t and v not in (None, ""):
            try:
                out[f"{t[:4]}-Q{t[-1]}"] = float(v)
            except ValueError:
                pass
    return out


def collect_gdp_inflation():
    ecos_key = os.environ.get("ECOS_API_KEY", "").strip()
    if not ecos_key:
        print("ERROR: ECOS_API_KEY 미설정 (한국 GDP·CPI)")
        sys.exit(1)
    areas = {"Korea": "KOR", "US": "USA", "Japan": "JPN", "China": "CHN"}
    print("[gdpcpi] 명목GDP YoY + CPI YoY (분기, 중국 포함)")
    print("  소스 — GDP: 한국=ECOS(200Y102/60211), 미·일·중=OECD QNA / CPI: 미=FRED, 한=ECOS, 일=OECD C2018, 중=OECD G20")
    gdp, cpi = {}, {}
    for name, iso in areas.items():
        # 명목 GDP 전년동기대비(%)
        if name == "Korea":
            gdp[name] = ecos_quarterly("200Y102", "60211", ecos_key)   # ECOS 직접(명목·원계열·전년동기비)
        else:
            gdp[name] = gdp_yoy(oecd_qna_gdp_nsa(iso))                 # OECD 레벨 → YoY 계산
        # CPI 전년동월비(%) → 분기평균
        if name == "US":
            cpi_m = index_to_monthly_yoy(fred_monthly("CPIAUCSL", start="2014-01"))
        elif name == "Korea":
            cpi_m = index_to_monthly_yoy(ecos_monthly("901Y009", "0", ecos_key, start="2014-01"))
        elif name == "Japan":
            cpi_m = oecd_cpi_gy_monthly(iso, g20=False)
        else:  # China
            cpi_m = oecd_cpi_gy_monthly(iso, g20=True)
        cpi[name] = monthly_yoy_to_quarterly(cpi_m)

        gl = max(gdp[name]) if gdp[name] else "-"
        cl = max(cpi[name]) if cpi[name] else "-"
        print(f"  {name:6s}: GDP {len(gdp[name])}q(~{gl}={gdp[name].get(gl, '-')}) "
              f"CPI {len(cpi[name])}q(~{cl}={cpi[name].get(cl, '-')})")

    end = max(max(d) for d in gdp.values() if d)            # GDP 최신 분기를 끝으로
    labels = quarters_range("2015-Q1", end)
    return {
        "title": "GDP / Inflation",
        "unit": "%",
        "source": "OECD · FRED · 한국은행(ECOS)",
        "freq": "Q",
        "start": "2015-Q1",
        "labels": labels,
        "gdp": {n: [gdp[n].get(q) for q in labels] for n in areas},
        "cpi": {n: [cpi[n].get(q) for q in labels] for n in areas},
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
        "gdpcpi": collect_gdp_inflation(),
        # 추후: "unemp": collect_unemp(),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"저장 완료: {OUT_PATH} ({max(1, os.path.getsize(OUT_PATH) // 1024)} KB)")


if __name__ == "__main__":
    main()
