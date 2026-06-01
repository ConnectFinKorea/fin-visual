"""
TheBell Deal > M&A 섹션 상위 10개 기사 스크래핑 → data/news_thebell.json
- URL: https://www.thebell.co.kr/front/free/Contents/NewsList.asp?Code=0103
- 무료/유료 구분 자동 감지 (자물쇠 아이콘/CSS class/URL 패턴 휴리스틱)
- 주기적 GitHub Actions 실행
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 미설치. 워크플로에서 `pip install beautifulsoup4` 필요.")
    sys.exit(1)

KST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "news_thebell.json")

# Deal(01) > M&A(03) 리스트 페이지. NewsList.asp가 무료/유료 기사 공용 진입점.
LIST_URL = "https://www.thebell.co.kr/front/NewsList.asp?Code=0103"
BASE_URL = "https://www.thebell.co.kr"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TOP_N = 10
TIMEOUT = 25


def fetch_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Referer": "https://www.thebell.co.kr/",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
    # thebell은 최근 UTF-8 사용. 과거 EUC-KR 호환을 위해 폴백.
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _text(el):
    return el.get_text(" ", strip=True) if el else ""


def parse_listing(html_str):
    """
    TheBell M&A 리스트 파싱 (실측 HTML 기반, 2026-06):
      <dl>
        <a href="/front/newsview.asp?code=0103&key=...">
          <dt>제목</dt>
          <dd>요약</dd>
        </a>
        <dd class="userBox">
          <a href="/search/search.asp?...&part=REPORTER">
            <span class="user">기자명</span>
          </a>
          <span class="date">2026-06-01 15:39:57</span>
        </dd>
        <!-- 무료 기사일 때만 추가: -->
        <div class="freeTimeText">
          <img src=".../time_icon.png" alt="무료시간표시">Jun 01, 2026
        </div>
      </dl>

    사이드바 '인기뉴스'도 같은 newsview.asp URL을 쓰지만 anchor 안에 <dt>가 없어
    구분 가능. <dt>가 있는 anchor만 메인 리스트 entry로 채택.

    유료/무료:
      무료 = <dl> 안에 'freeTimeText' 클래스 또는 img alt="무료시간표시" 존재
      유료 = 기본값 (위 marker 없음)
    """
    soup = BeautifulSoup(html_str, "html.parser")

    anchors = soup.find_all("a", href=re.compile(r"newsview\.asp\?code=0103", re.I))
    print(f"  newsview anchor 매치: {len(anchors)}개 (사이드바 인기뉴스 포함)")

    items = []
    seen_urls = set()
    for a in anchors:
        # 메인 리스트 entry 판별: anchor 안에 <dt> 존재
        dt = a.find("dt")
        if not dt:
            continue

        href = a.get("href", "").strip()
        if not href:
            continue
        if href.startswith("/"):
            href = BASE_URL + href
        elif not href.lower().startswith("http"):
            continue
        if href in seen_urls:
            continue

        title = _text(dt)
        if not title or len(title) < 3:
            continue

        # 요약 — anchor 안의 <dd>
        dd = a.find("dd")
        summary = _text(dd)[:300] if dd else ""

        # 부모 <dl>에서 기자/일시/무료표시 찾기
        dl = a.find_parent("dl")
        meta = ""
        is_paid = True  # 기본값 = 유료
        if dl:
            reporter_span = dl.find("span", class_="user")
            date_span = dl.find("span", class_="date")
            reporter = _text(reporter_span)
            datetime_text = _text(date_span)
            if reporter or datetime_text:
                meta = f"{reporter} · {datetime_text}".strip(" ·")

            # 무료 marker: freeTimeText 클래스
            if dl.find(class_="freeTimeText"):
                is_paid = False
            else:
                for img in dl.find_all("img"):
                    src = (img.get("src") or "").lower()
                    alt = (img.get("alt") or "")
                    if "time_icon" in src or "무료시간" in alt:
                        is_paid = False
                        break

        items.append({
            "title": title,
            "url": href,
            "summary": summary,
            "meta": meta,
            "is_paid": is_paid,
        })
        seen_urls.add(href)
        if len(items) >= TOP_N:
            break

    print(f"  메인 entry 추출: {len(items)}개")
    return items


def main():
    now_kst = datetime.now(timezone.utc).astimezone(KST)
    print(f"[현재 시각] {now_kst.isoformat()}")
    print(f"[fetch] {LIST_URL}")

    try:
        html_str = fetch_html(LIST_URL)
    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code} {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: fetch 실패: {e}")
        sys.exit(1)

    print(f"  HTML {len(html_str):,} bytes")
    items = parse_listing(html_str)
    print(f"  파싱 결과 {len(items)}개")

    if not items:
        print("\nERROR: 기사 0건 — HTML 구조 변경/차단 의심. 디버그용 앞 3000자:")
        print(html_str[:3000])
        sys.exit(1)

    print("\n상위 항목 미리보기:")
    for i, it in enumerate(items[:5], 1):
        flag = "[유료]" if it["is_paid"] else "[무료]"
        print(f"  {i}. {flag} {it['title'][:60]}")

    out = {
        "generated_at": now_kst.isoformat(),
        "source": "TheBell Deal > M&A (Code=0103)",
        "list_url": LIST_URL,
        "count": len(items),
        "items": items,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = max(1, os.path.getsize(OUT_PATH) // 1024)
    print(f"\n저장 완료: {OUT_PATH} ({size_kb} KB)")


if __name__ == "__main__":
    main()
