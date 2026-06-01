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

# Deal(01) > M&A(03) 리스트 페이지. 무료/유료 진입 페이지 모두 NewsList.asp 공용.
LIST_URL = "https://www.thebell.co.kr/front/free/Contents/NewsList.asp?Code=0103"
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


def detect_paid(art_el, href):
    """카드/URL을 종합해 유료 여부 추정. 휴리스틱 — 잘못 잡히면 후속 패스 가능."""
    # 1) thebell은 무료 기사를 /free/ 경로로, 유료를 /Content/ 경로로 서빙
    h = (href or "").lower()
    if "/free/" in h:
        return False
    if "/content/" in h and "/free/" not in h:
        return True

    # 2) class 키워드 (자기 + 자식)
    own_cls = " ".join(art_el.get("class", []) or [])
    inner_cls = " ".join(
        " ".join(t.get("class", []) or []) for t in art_el.find_all(True)
    )
    blob = (own_cls + " " + inner_cls).lower()
    if any(k in blob for k in ("lock", "paid", "premium", "subscriber", "member-only")):
        return True

    # 3) 이미지 alt / src
    for img in art_el.find_all("img"):
        src = (img.get("src") or "").lower()
        alt = (img.get("alt") or "").lower()
        if any(k in src for k in ("lock", "paid", "premium")):
            return True
        if any(k in alt for k in ("유료", "잠금", "구독", "프리미엄", "lock", "paid")):
            return True

    return False


def parse_listing(html_str):
    soup = BeautifulSoup(html_str, "html.parser")

    # thebell의 일반적 컨테이너 후보 — 사이트 리뉴얼 대비 다중 시도.
    selectors = [
        ".newsList li", ".article_list li", ".list_news li",
        "ul.news li", ".bd_list li", "div.article-item",
        "table.bd_list tbody tr", "li.news",
    ]
    arts = []
    matched_sel = None
    for sel in selectors:
        arts = soup.select(sel)
        if arts:
            matched_sel = sel
            break

    # Fallback — Article 링크에서 거꾸로 부모 추적
    if not arts:
        for a in soup.find_all("a", href=re.compile(r"(/free/Content/ArticleView|/Content/ArticleView)", re.I)):
            parent = a.find_parent(["li", "tr", "div", "article"]) or a
            if parent not in arts:
                arts.append(parent)
        if arts:
            matched_sel = "fallback:anchor"

    print(f"  컨테이너 선택자: {matched_sel} → 후보 {len(arts)}개")

    items = []
    seen_urls = set()
    for art in arts:
        a = art.find("a", href=True)
        if not a:
            continue
        href = a["href"].strip()
        if href.startswith("/"):
            href = BASE_URL + href
        elif not href.lower().startswith("http"):
            continue
        # 기사 본문 anchor만 채택 (다른 anchor 제외)
        if "ArticleView" not in href and "newsView" not in href.lower():
            continue
        if href in seen_urls:
            continue

        # 제목 — class에 title/tit/subject가 있거나, anchor 자체 텍스트
        title_el = art.find(class_=re.compile(r"(?i)title|tit|subject|head"))
        title = _text(title_el) or _text(a)
        if not title or len(title) < 3:
            continue

        # 요약
        summary_el = art.find(class_=re.compile(r"(?i)summary|desc|cont(?!ainer)|excerpt|lead"))
        summary = _text(summary_el)[:300] if summary_el else ""

        # 기자 / 일시
        meta_el = art.find(class_=re.compile(r"(?i)meta|info|date|reporter|byline|writer"))
        meta = _text(meta_el)[:120] if meta_el else ""

        paid = detect_paid(art, href)

        items.append({
            "title": title,
            "url": href,
            "summary": summary,
            "meta": meta,
            "is_paid": paid,
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
