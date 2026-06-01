"""
TheBell Deal > M&A 섹션 상위 10개 기사 스크래핑 → data/news_thebell.json
- URL: https://www.thebell.co.kr/front/NewsList.asp?Code=0103
- 메인 entry 구조: <dl><a><dt>제목</dt><dd>요약</dd></a></dl>
- 무료 표시: <div class="freeTimeText"> 또는 alt="무료시간표시" img (없으면 기본=유료)
- 직전 push본과 URL 비교 → 신규 기사만 Telegram으로 전송 (선택)
- Railway cron 서비스로 운영

환경변수 (선택):
  TELEGRAM_BOT_TOKEN  봇 토큰 (없으면 Telegram 전송 skip)
  TELEGRAM_CHAT_ID    수신 chat id
  GH_REPO             ConnectFinKorea/fin-visual (직전 결과 fetch용)
"""

import html as htmllib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
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

# Telegram (선택). 두 변수 모두 set되어야 활성.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GH_REPO = os.environ.get("GH_REPO", "").strip()


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


def fetch_previous_urls():
    """직전 push된 news_thebell.json에서 URL set 가져오기.
    None 반환: 비교 불가 (GH_REPO 미설정) → Telegram 전송 skip.
    set() 반환: 첫 실행/이전 파일 없음 → 모든 기사를 신규로 처리.
    {...} 반환: 기존 URL 집합.
    """
    if not GH_REPO:
        print("  GH_REPO 미설정 — 신규 판별 불가 (Telegram 전송 skip)")
        return None
    url = (f"https://raw.githubusercontent.com/{GH_REPO}/data-snapshot/news_thebell.json"
           f"?t={int(time.time() // 60)}")  # 분 단위 캐시버스팅
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        urls = {it["url"] for it in data.get("items", []) if it.get("url")}
        print(f"  직전 push: {len(urls)}개 URL")
        return urls
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("  직전 push 없음 (첫 실행) — 모든 기사를 신규로 처리")
            return set()
        print(f"  주의: 직전 결과 fetch 실패 (HTTP {e.code}) — 모든 기사를 신규로 처리")
        return set()
    except Exception as e:
        print(f"  주의: 직전 결과 fetch 실패 ({e}) — 모든 기사를 신규로 처리")
        return set()


def _extract_date_md(meta_text):
    """meta('남지연 기자 · 2026-06-01 15:39:57')에서 'MM/DD' 추출. 실패 시 '??/??'."""
    m = re.search(r"\d{4}-(\d{2})-(\d{2})", meta_text or "")
    return f"{m.group(1)}/{m.group(2)}" if m else "??/??"


def send_telegram(items):
    """신규 기사 전체를 한 메시지로 표 형식 전송.
    제목은 <a href> 링크 → 탭하면 thebell로 이동. 봇 미설정 시 silent skip.
    포맷:
      📰 TheBell M&A 신규 N건 (2026-06-01 16:42 KST)

      01. 06/01 [유료] 제목1
      02. 06/01 [무료] 제목2
      ...
    """
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("  Telegram 미설정 (TELEGRAM_BOT_TOKEN/CHAT_ID) — 알림 skip")
        return
    if not items:
        print("  Telegram 전송할 신규 기사 없음")
        return

    now_kst = datetime.now(timezone.utc).astimezone(KST)
    header = (f"📰 <b>TheBell M&amp;A 신규 {len(items)}건</b> "
              f"({now_kst.strftime('%Y-%m-%d %H:%M')} KST)")
    lines = [header, ""]
    for i, it in enumerate(items, 1):
        badge = "[유료]" if it.get("is_paid") else "[무료]"
        title = htmllib.escape(it.get("title", ""))      # 본문 텍스트 이스케이프
        url   = htmllib.escape(it.get("url", ""), quote=True)  # href 속성 이스케이프 (& → &amp;)
        date_md = _extract_date_md(it.get("meta", ""))
        lines.append(f'{i:02d}. {date_md} {badge} <a href="{url}">{title}</a>')
    text = "\n".join(lines)

    # Telegram 메시지 길이 한도 4096자 — 10건 × ~170자 ≈ 1800자라 여유.
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",  # 링크 10개 → preview 끄는 게 깔끔
    }).encode("utf-8")
    try:
        with urllib.request.urlopen(api, data=payload, timeout=10) as resp:
            if resp.status == 200:
                print(f"  Telegram 전송 완료 ({len(items)}건 1개 메시지)")
            else:
                print(f"  Telegram 전송 실패 (HTTP {resp.status})")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        print(f"  Telegram 전송 HTTP 오류 {e.code}: {body}")
    except Exception as e:
        print(f"  Telegram 전송 예외: {e}")


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

    # ============ Telegram 신규 기사 알림 ============
    print(f"\n[Telegram 알림]")
    previous_urls = fetch_previous_urls()
    if previous_urls is None:
        new_items = []
    else:
        new_items = [it for it in items if it["url"] not in previous_urls]
    print(f"  신규 기사: {len(new_items)}건")
    send_telegram(new_items)


if __name__ == "__main__":
    main()
