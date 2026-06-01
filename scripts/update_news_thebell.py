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
    TheBell M&A 리스트 파싱.
    실제 구조 (2026-06 기준):
      <li>
        <a href="/front/newsview.asp?code=0103&key=...">
          <p>제목</p>
          <p>요약</p>
        </a>
        <a href="/search/search.asp?keyword=...">기자명</a>
        2026-06-01 15:39:57
      </li>
    무료 표시: <li> 안에 <img src=".../time_icon.png"> 존재.
    유료 = 기본값 (time_icon 없음).
    """
    soup = BeautifulSoup(html_str, "html.parser")

    # 기사 본문 anchor — href에 'newsview.asp?code=0103' 포함.
    # 거기서 부모 <li>를 거꾸로 잡는 게 가장 안전 (class 의존 없음).
    anchors = soup.find_all("a", href=re.compile(r"newsview\.asp\?code=0103", re.I))
    print(f"  newsview anchor 매치: {len(anchors)}개")

    items = []
    seen_urls = set()
    for a in anchors:
        href = a.get("href", "").strip()
        if not href:
            continue
        if href.startswith("/"):
            href = BASE_URL + href
        elif not href.lower().startswith("http"):
            continue
        if href in seen_urls:
            continue

        # 제목 — anchor 안의 첫 번째 <p>
        ps = a.find_all("p")
        if not ps:
            continue
        title = _text(ps[0])
        if not title or len(title) < 3:
            continue

        # 요약 — anchor 안의 두 번째 <p>
        summary = _text(ps[1])[:300] if len(ps) >= 2 else ""

        # 메타 (기자 + 일시) — 부모 <li>에서 reporter anchor + 다음 text node
        li = a.find_parent("li")
        meta = ""
        is_paid = True  # 기본값 = 유료
        if li:
            reporter_a = li.find("a", href=re.compile(r"search\.asp", re.I))
            reporter = _text(reporter_a) if reporter_a else ""
            datetime_text = ""
            if reporter_a:
                # reporter anchor 다음 sibling이 일시 text node
                sib = reporter_a.next_sibling
                if sib:
                    datetime_text = str(sib).strip()[:30]
            meta = f"{reporter} · {datetime_text}".strip(" ·") if (reporter or datetime_text) else ""

            # 무료 표시 = time_icon.png 이미지 존재
            for img in li.find_all("img"):
                src = (img.get("src") or "").lower()
                if "time_icon" in src:
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
