"""
Macro Eco 지표 수집 → data/macro.json

현재 구현: Prime Rate(기준금리) 4개국, 2015-01~ 월별.
추후 확장: bond(10Y) / inflation(CPI YoY) / unemployment — collect_*() 추가만 하면 됨.
(Macro Eco 섹션 전체를 이 한 스크립트 = Railway 단일 일일 서비스로 운영)

소스 (전부 공식 API, 스크래핑 없음 — 2026-06-07 라이브 검증):
  미국·일본·중국 정책금리: BIS CBPOL  (stats.bis.org SDMX v2, 월말값, 키 불필요)
  한국 기준금리:           한국은행 ECOS 722Y001/0101000 (월, env ECOS_API_KEY)

환경변수:
  ECOS_API_KEY  (필수) 한국은행 ECOS 인증키

출력 data/macro.json:
  { schema, generated_at, generated_at_full,
    prime: { title, unit, source, start, labels[YYYY-MM…], series{Korea,US,Japan,China} } }
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


def forward_fill(series_map, labels):
    """labels 순서로 forward-fill. 정책금리는 계단함수라 직전값 유지가 정확.
    선행 결측(데이터 시작 전)은 null 유지 → 라인이 실제 데이터 시작점부터 그려짐.
    (예: 일본은 BIS상 2013~2016.9 '정책금리 없음' 구간이라 그 이전은 null)"""
    out, last = [], None
    for lb in labels:
        if lb in series_map and series_map[lb] is not None:
            last = series_map[lb]
        out.append(None if last is None else round(last, 4))
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


def ecos_base_rate(api_key):
    """한국은행 기준금리(월) 722Y001/0101000 → {'YYYY-MM': float}."""
    start = START.replace("-", "")                      # 201501
    end = datetime.now(KST).strftime("%Y%m")
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/1000/"
           f"722Y001/M/{start}/{end}/0101000")
    data = json.loads(http_get(url))
    if "StatisticSearch" not in data:
        raise RuntimeError(f"ECOS 응답 오류: {data.get('RESULT', data)}")
    out = {}
    for row in data["StatisticSearch"]["row"]:
        t, v = row.get("TIME", ""), row.get("DATA_VALUE", "")
        if len(t) == 6 and v not in (None, ""):
            try:
                out[f"{t[:4]}-{t[4:]}"] = float(v)
            except ValueError:
                pass
    if not out:
        raise RuntimeError("ECOS: 파싱 0건")
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
        "Korea": ecos_base_rate(api_key),
    }

    latest = max(max(d) for d in src.values())          # 가장 최신 월
    labels = months_range(START, latest)
    series = {name: forward_fill(d, labels) for name, d in src.items()}

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


# ===================== main =====================

def main():
    now = datetime.now(KST)
    out = {
        "schema": 1,
        "generated_at": now.strftime("%Y-%m-%d"),
        "generated_at_full": now.isoformat(),
        "prime": collect_prime(),
        # 추후: "bond": collect_bond(), "inflation": collect_inflation(), "unemp": collect_unemp(),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"저장 완료: {OUT_PATH} ({max(1, os.path.getsize(OUT_PATH) // 1024)} KB)")


if __name__ == "__main__":
    main()
