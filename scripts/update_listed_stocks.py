"""
DART CORPCODE.xml -> listed_stocks.json
- 매일 23:59 KST에 GitHub Actions에서 실행
- 종목코드를 가진 (= 상장된) 회사만 추출
- 시장 구분 포함 (KOSPI/KOSDAQ/KONEX/기타)

환경변수:
  DART_API_KEY = OpenDART API 키
"""

import io
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

API_KEY = os.environ.get("DART_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: DART_API_KEY 환경변수가 없습니다.")
    sys.exit(1)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "data")
OUT_PATH = os.path.join(OUT_DIR, "listed_stocks.json")
XML_PATH = os.path.join(OUT_DIR, "CORPCODE.xml")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
MARKET_MAP = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX", "E": "기타"}


def download_corp_code():
    print("[1/2] DART CORPCODE.xml 다운로드")
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()

    if data[:2] != b"PK":
        # zip이 아니면 에러 응답일 가능성
        print(f"  ERROR: ZIP 파일이 아닙니다. 응답: {data[:200]!r}")
        sys.exit(1)

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(OUT_DIR)
    size_kb = os.path.getsize(XML_PATH) // 1024
    print(f"  완료 ({size_kb:,} KB)")


def parse_listed():
    print("[2/2] 상장사 추출")
    tree = ET.parse(XML_PATH)
    root = tree.getroot()
    listed = []
    for item in root.findall("list"):
        stock = (item.findtext("stock_code", "") or "").strip()
        if not stock:
            continue
        corp = (item.findtext("corp_code", "") or "").strip()
        name = (item.findtext("corp_name", "") or "").strip()
        market_raw = (item.findtext("corp_cls", "") or "").strip()
        listed.append({
            "stock_code": stock.zfill(6),
            "corp_code": corp,
            "name": name,
            "market": MARKET_MAP.get(market_raw, "기타"),
            "market_raw": market_raw,
        })
    return listed


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    download_corp_code()
    listed = parse_listed()

    by_market = {}
    for c in listed:
        by_market[c["market"]] = by_market.get(c["market"], 0) + 1

    output = {
        "version": "1.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%d %H:%M:%S KST"),
        "source": "DART OpenAPI corpCode.xml",
        "count": len(listed),
        "by_market": by_market,
        "companies": listed,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 임시 XML 파일 정리
    try:
        os.remove(XML_PATH)
    except OSError:
        pass

    print(f"\n저장 완료: {OUT_PATH}")
    print(f"  - 상장사 총: {len(listed):,}개")
    print(f"  - 시장별: {by_market}")


if __name__ == "__main__":
    main()
