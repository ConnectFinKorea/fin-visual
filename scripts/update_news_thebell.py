"""
TheBell 다중 카테고리 뉴스 스크래핑 → data/news_thebell.json (롤링 15일 아카이브)

수집 범위 (NewsList.asp?Code=XXXX):
  deal    : 채권(0101) · 주식(0102) · M&A(0103)
  finance : 증권(0202)
  invest  : IB(0301) · 자산운용(0302) · PEF/벤처캐피탈(0303) · 연기금(0304)

특징:
  - 카테고리별 페이지를 넘기며 최근 RETENTION_DAYS(15일) 기사 수집
  - 기사 key 로 중복 제거. 여러 카테고리에 동시 노출되면 출처 = "multiple"
  - 매 실행마다 직전 결과(data-snapshot)에 누적(롤링 보관) → 1회 노출이 짧아도 15일치가 채워짐
  - 무료 전환 추적: is_paid 가 True→False 로 바뀐(또는 처음 무료로 관측된) 날짜를 free_date 에 기록
    · 더벨은 실제 전환일을 공개하지 않으므로 free_date = "우리가 무료로 처음 관측한 날"
  - 신규 기사 Telegram 발송 (첫 실행/스키마 변경 시엔 baseline 으로 발송 생략, 대량은 분할 발송)

환경변수 (선택):
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID  봇 토큰·수신 chat (없으면 발송 skip)
  GH_REPO  ConnectFinKorea/fin-visual (직전 결과 fetch용; 없으면 baseline 처리)
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
from datetime import date, datetime, timedelta, timezone

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 미설치. `pip install beautifulsoup4` 필요.")
    sys.exit(1)

KST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "news_thebell.json")

BASE_URL = "https://www.thebell.co.kr"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 수집 카테고리 (code, 출처 라벨)
CATEGORIES = [
    ("0101", "채권"),
    ("0102", "주식"),
    ("0103", "M&A"),
    ("0202", "증권"),
    ("0301", "IB"),
    ("0302", "자산운용"),
    ("0303", "PEF/벤처캐피탈"),
    ("0304", "연기금"),
]

SCHEMA = 2                 # 출력 스키마 버전 (변경 시 baseline 재시작)
RETENTION_DAYS = 15        # 롤링 보관 기간
MAX_PAGES = 15             # 카테고리당 최대 페이지 (안전 상한)
PAGE_SLEEP = 0.3           # 페이지 요청 간격 (더벨 부담 완화)
TIMEOUT = 25
TELEGRAM_BATCH = 20        # Telegram 한 메시지당 최대 기사 수 (4096자 한도 회피)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GH_REPO = os.environ.get("GH_REPO", "").strip()

LIST_URL_MA = f"{BASE_URL}/front/NewsList.asp?Code=0103"


# ===================== fetch / parse =====================

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
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _text(el):
    return el.get_text(" ", strip=True) if el else ""


def parse_date(s):
    """'2026-06-05 13:52:16' → date(2026,6,5). 실패 시 None."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_list_page(html_str):
    """리스트 페이지에서 기사 추출. 사이드바(인기뉴스)는 <dt> 없어 제외.
    반환: [{key, url, title, summary, meta, is_paid, date}]"""
    soup = BeautifulSoup(html_str, "html.parser")
    anchors = soup.find_all("a", href=re.compile(r"newsview\.asp\?code=\d+", re.I))

    items = []
    seen = set()
    for a in anchors:
        dts = a.find_all("dt")
        if not dts:
            continue

        href = a.get("href", "").strip()
        if not href:
            continue
        if href.startswith("/"):
            href = BASE_URL + href
        elif not href.lower().startswith("http"):
            continue

        km = re.search(r"key=([0-9]+)", href)
        if not km:
            continue
        key = km.group(1)
        if key in seen:
            continue

        # 제목 = 텍스트 있는 첫 <dt> (대표기사는 <dt class='photo'> 가 먼저 옴)
        title = ""
        for d in dts:
            t = _text(d)
            if t and len(t) >= 3:
                title = t
                break
        if not title:
            continue

        dd = a.find("dd")
        summary = _text(dd)[:300] if dd else ""

        dl = a.find_parent("dl")
        meta = ""
        is_paid = True
        date_text = ""
        if dl:
            reporter = _text(dl.find("span", class_="user"))
            date_text = _text(dl.find("span", class_="date"))
            if reporter or date_text:
                meta = f"{reporter} · {date_text}".strip(" ·")
            if dl.find(class_="freeTimeText"):
                is_paid = False
            else:
                for img in dl.find_all("img"):
                    src = (img.get("src") or "").lower()
                    alt = (img.get("alt") or "")
                    if "time_icon" in src or "무료시간" in alt:
                        is_paid = False
                        break

        seen.add(key)
        items.append({
            "key": key, "url": href, "title": title, "summary": summary,
            "meta": meta, "is_paid": is_paid, "date": date_text,
        })
    return items


def scrape_category(code, label, cutoff):
    """한 카테고리를 페이지 넘기며 cutoff(날짜) 이후 기사 수집. key→article dict."""
    arts = {}
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE_URL}/front/NewsList.asp?Code={code}&page={page}"
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"    [{label}] page {page} fetch 실패: {e}")
            break
        page_arts = parse_list_page(html)
        if not page_arts:
            break
        oldest = None
        for a in page_arts:
            arts[a["key"]] = a
            d = parse_date(a["date"])
            if d and (oldest is None or d < oldest):
                oldest = d
        time.sleep(PAGE_SLEEP)
        # 이 페이지에서 가장 오래된 기사가 cutoff 이전이면 더 볼 필요 없음
        if oldest and oldest < cutoff:
            break
    return arts


def scrape_all(cutoff):
    """전 카테고리 수집 + 중복 병합. key→{..., sources:set}."""
    merged = {}
    for code, label in CATEGORIES:
        cat = scrape_category(code, label, cutoff)
        for key, a in cat.items():
            if key in merged:
                merged[key]["sources"].add(label)
            else:
                a = dict(a)
                a["sources"] = {label}
                merged[key] = a
        print(f"  [{label}] {len(cat)}건 수집")
    return merged


# ===================== 직전 store (롤링 누적) =====================

def load_previous_store():
    """직전 news_thebell.json(data-snapshot) 로드.
    반환: (items_list, schema). 구버전/없음/실패 → ([], None) → baseline."""
    if not GH_REPO:
        print("  GH_REPO 미설정 — 직전 결과 비교 불가 (baseline 처리)")
        return [], None
    url = (f"https://raw.githubusercontent.com/{GH_REPO}/data-snapshot/news_thebell.json"
           f"?t={int(time.time() // 60)}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("  직전 결과 없음 (첫 실행) → baseline")
        else:
            print(f"  직전 결과 fetch 실패 (HTTP {e.code}) → baseline")
        return [], None
    except Exception as e:
        print(f"  직전 결과 fetch 실패 ({e}) → baseline")
        return [], None
    if data.get("schema") == SCHEMA and isinstance(data.get("items"), list):
        return data["items"], SCHEMA
    print("  직전 결과가 구버전 스키마 → baseline 재시작")
    return [], None


# ===================== Telegram =====================

def _src_label(sources_list):
    return sources_list[0] if len(sources_list) == 1 else "multiple"


def _date_md(s):
    m = re.search(r"\d{4}-(\d{2})-(\d{2})", s or "")
    return f"{m.group(1)}/{m.group(2)}" if m else "--/--"


def send_telegram(new_arts, now_kst):
    """신규 기사 분할 발송. 봇/대상 미설정 시 skip."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("  Telegram 미설정 — 발송 skip")
        return
    if not new_arts:
        print("  신규 기사 없음 — 발송 skip")
        return

    total_parts = (len(new_arts) + TELEGRAM_BATCH - 1) // TELEGRAM_BATCH
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    stamp = now_kst.strftime("%Y-%m-%d %H:%M")

    for pi in range(total_parts):
        chunk = new_arts[pi * TELEGRAM_BATCH:(pi + 1) * TELEGRAM_BATCH]
        part = f" ({pi + 1}/{total_parts})" if total_parts > 1 else ""
        lines = [f"📰 <b>TheBell 신규 {len(new_arts)}건</b>{part} ({stamp} KST)", ""]
        for i, it in enumerate(chunk, pi * TELEGRAM_BATCH + 1):
            badge = "[유료]" if it.get("is_paid") else "[무료]"
            src = htmllib.escape(it.get("source", ""))
            title = htmllib.escape(it.get("title", ""))
            url = htmllib.escape(it.get("url", ""), quote=True)
            lines.append(f'{i:02d}. [{src}]{badge} {_date_md(it.get("date"))} '
                         f'<a href="{url}">{title}</a>')
        text = "\n".join(lines)
        payload = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        try:
            with urllib.request.urlopen(api, data=payload, timeout=10) as resp:
                ok = resp.status == 200
            print(f"  Telegram 발송 {pi + 1}/{total_parts} ({len(chunk)}건) {'OK' if ok else '실패'}")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            print(f"  Telegram HTTP 오류 {e.code}: {body}")
        except Exception as e:
            print(f"  Telegram 예외: {e}")
        time.sleep(0.5)


# ===================== main =====================

def main():
    now_kst = datetime.now(timezone.utc).astimezone(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    cutoff = (now_kst - timedelta(days=RETENTION_DAYS)).date()
    print(f"[현재 시각] {now_kst.isoformat()}  / 보관 cutoff {cutoff}")

    # 1) 스크랩
    scraped = scrape_all(cutoff)
    print(f"  스크랩 총 {len(scraped)}건 (중복 제거 후)")
    if not scraped:
        print("ERROR: 수집 0건 — 구조 변경/차단 의심. 갱신 중단.")
        sys.exit(1)

    # 2) 직전 store 로드 (롤링 누적)
    prev_items, prev_schema = load_previous_store()
    baseline = (prev_schema != SCHEMA)
    store = {it["key"]: it for it in prev_items if it.get("key")}

    # 3) 병합 + 무료 전환 추적 + 신규 집계
    new_keys = []
    for key, a in scraped.items():
        src_list = sorted(a["sources"])
        if key in store:
            it = store[key]
            if not a["is_paid"] and not it.get("free_date"):
                it["free_date"] = today_str          # 무료 전환 관측
            it["is_paid"] = a["is_paid"]
            it["title"] = a["title"]
            it["meta"] = a["meta"]
            it["url"] = a["url"]
            it["summary"] = a["summary"]
            if not it.get("date"):
                it["date"] = a["date"]
            merged_src = sorted(set(it.get("sources_list", [])) | set(src_list))
            it["sources_list"] = merged_src
            it["source"] = _src_label(merged_src)
        else:
            store[key] = {
                "key": key, "url": a["url"], "title": a["title"], "summary": a["summary"],
                "meta": a["meta"], "date": a["date"], "is_paid": a["is_paid"],
                "sources_list": src_list, "source": _src_label(src_list),
                "first_seen": today_str,
                "free_date": today_str if not a["is_paid"] else None,
            }
            new_keys.append(key)

    # 4) 보관 기간 지난 기사 제거 + 정렬(최신순)
    items = []
    for it in store.values():
        d = parse_date(it.get("date"))
        if d and d < cutoff:
            continue
        items.append(it)
    items.sort(key=lambda it: it.get("date") or "", reverse=True)

    free_cnt = sum(1 for it in items if not it.get("is_paid"))
    print(f"  보관 {len(items)}건 (무료 {free_cnt}) / 이번 신규 {len(new_keys)}건")

    # 5) 저장
    out = {
        "schema": SCHEMA,
        "generated_at": now_kst.isoformat(),
        "source": "TheBell (deal·finance·invest 다중 카테고리)",
        "list_url": LIST_URL_MA,
        "retention_days": RETENTION_DAYS,
        "count": len(items),
        "items": items,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  저장 완료: {OUT_PATH} ({max(1, os.path.getsize(OUT_PATH)//1024)} KB)")

    # 6) Telegram
    print("[Telegram]")
    if baseline:
        print(f"  baseline(첫 실행/스키마 변경) — 기준선 {len(items)}건 저장, 발송 생략")
    else:
        new_arts = [it for it in items if it["key"] in set(new_keys)]
        # 최신순 정렬된 items 순서 유지
        send_telegram(new_arts, now_kst)


if __name__ == "__main__":
    main()
