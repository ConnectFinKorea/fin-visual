"""
DART 상장사 업종 분류 신규 수집 → industry_mapping.json 생성

사용법:
  set DART_API_KEY=your_key   (Windows CMD)
  $env:DART_API_KEY="your_key" (PowerShell)
  python fetch_dart_industry.py

특징:
  - 워커 2개, 호출 간 0.2초 sleep (속도제한 회피)
  - 5회 재시도 (지수 백오프)
  - 200개마다 진행 상황 + 임시 저장 (중단되어도 재개 가능)
  - 한국표준산업분류 11차 기준 KSIC 매핑
"""

import sys
import os
import json
import time
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

API_KEY = os.environ.get("DART_API_KEY") or os.environ.get("OPENDART_API_KEY", "")
if not API_KEY:
    print("ERROR: DART_API_KEY 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + r"\data"
OUT_PATH    = os.path.join(OUT_DIR, "industry_mapping.json")
TEMP_PATH   = os.path.join(OUT_DIR, "_dart_progress.json")
CORP_XML    = os.path.join(OUT_DIR, "CORPCODE.xml")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
WORKERS = 2           # 동시 워커 수
SLEEP_SEC = 0.2       # 호출 간격 (워커별)
MAX_RETRY = 5         # 재시도 횟수


# ============ KSIC 11차 매핑 (대분류 2자리, 소분류 3자리) ============
# 2024-07-01 시행 한국표준산업분류 11차 기준. 10차와 거의 호환되며 일부 명칭 변경.
KSIC_MAJOR = {
    "01":"농업","02":"임업","03":"어업",
    "05":"석탄, 원유 및 천연가스 광업","06":"금속 광업","07":"비금속광물 광업","08":"광업 지원 서비스업",
    "10":"식료품 제조업","11":"음료 제조업","12":"담배 제조업","13":"섬유제품 제조업; 의복제외",
    "14":"의복, 의복액세서리 및 모피제품 제조업","15":"가죽, 가방 및 신발 제조업",
    "16":"목재 및 나무제품 제조업; 가구제외","17":"펄프, 종이 및 종이제품 제조업",
    "18":"인쇄 및 기록매체 복제업","19":"코크스, 연탄 및 석유정제품 제조업",
    "20":"화학 물질 및 화학제품 제조업; 의약품 제외","21":"의료용 물질 및 의약품 제조업",
    "22":"고무 및 플라스틱제품 제조업","23":"비금속 광물제품 제조업",
    "24":"1차 금속 제조업","25":"금속가공제품 제조업; 기계 및 가구 제외",
    "26":"전자부품, 컴퓨터, 영상, 음향 및 통신장비 제조업",
    "27":"의료, 정밀, 광학기기 및 시계 제조업","28":"전기장비 제조업",
    "29":"기타 기계 및 장비 제조업","30":"자동차 및 트레일러 제조업",
    "31":"기타 운송장비 제조업","32":"가구 제조업","33":"기타 제품 제조업",
    "34":"산업용 기계 및 장비 수리업","35":"전기, 가스, 증기 및 공기 조절 공급업",
    "36":"수도업","37":"하수, 폐수 및 분뇨 처리업",
    "38":"폐기물 수집, 운반, 처리 및 원료재생업","39":"환경 정화 및 복원업",
    "41":"종합 건설업","42":"전문직별 공사업",
    "45":"자동차 및 부품 판매업","46":"도매 및 상품 중개업","47":"소매업; 자동차 제외",
    "49":"육상운송 및 파이프라인 운송업","50":"수상 운송업","51":"항공 운송업",
    "52":"창고 및 운송관련 서비스업","55":"숙박업","56":"음식점 및 주점업",
    "58":"출판업","59":"영상·오디오 기록물 제작 및 배급업",
    "60":"방송 및 영상·오디오물 제공 서비스업","61":"우편 및 통신업",
    "62":"컴퓨터 프로그래밍, 시스템 통합 및 관리업","63":"정보서비스업",
    "64":"금융업","65":"보험 및 연금업","66":"금융 및 보험 관련 서비스업",
    "68":"부동산업","70":"연구개발업","71":"전문서비스업",
    "72":"건축기술, 엔지니어링 및 기타 과학기술 서비스업",
    "73":"기타 전문, 과학 및 기술 서비스업",
    "74":"사업시설 관리 및 조경 서비스업","75":"사업지원 서비스업","76":"임대업; 부동산 제외",
    "84":"공공행정","85":"교육 서비스업","86":"보건업","87":"사회복지 서비스업",
    "90":"창작, 예술 및 여가관련 서비스업","91":"스포츠 및 오락관련 서비스업",
    "94":"협회 및 단체","95":"개인 및 소비용품 수리업","96":"기타 개인 서비스업",
    "97":"가구 내 고용활동","98":"자가소비 생산활동","99":"국제 및 외국기관",
}

KSIC_SMALL = {
    "011":"작물 재배업","012":"축산업","013":"작물재배 및 축산 관련 서비스업","014":"수렵 및 수렵 관련 서비스업",
    "020":"임업","031":"어로 어업","032":"양식 어업 및 어업 관련 서비스업",
    "051":"석탄 광업","052":"원유 및 천연가스 채굴업","061":"철 광업","062":"비철금속 광업",
    "071":"토사석 광업","072":"기타 비금속광물 광업",
    "081":"원유 및 천연가스 채굴 관련 서비스업","082":"기타 광업 지원 서비스업",
    "101":"도축, 육류 가공 및 저장 처리업","102":"수산물 가공 및 저장 처리업",
    "103":"과실, 채소 가공 및 저장 처리업","104":"동물성 및 식물성 유지 제조업",
    "105":"낙농제품 및 식용 빙과류 제조업","106":"곡물가공품, 전분 및 전분제품 제조업",
    "107":"기타 식품 제조업","108":"동물용 사료 및 조제식품 제조업",
    "111":"알코올음료 제조업","112":"비알코올음료 및 얼음 제조업","120":"담배 제조업",
    "131":"방적 및 가공사 제조업","132":"직물직조 및 직물제품 제조업",
    "133":"편조원단 및 편조제품 제조업","139":"기타 섬유제품 제조업",
    "141":"봉제의복 제조업","142":"모피가공 및 모피제품 제조업",
    "143":"편조의복 제조업","144":"의복 액세서리 제조업",
    "151":"가죽, 가방 및 유사제품 제조업","152":"신발 및 신발부분품 제조업",
    "161":"제재 및 목재 가공업","162":"나무제품 제조업","163":"코르크 및 조물 제품 제조업",
    "171":"펄프, 종이 및 판지 제조업","172":"골판지, 종이 상자 및 종이용기 제조업",
    "179":"기타 종이 및 판지 제품 제조업",
    "181":"인쇄 및 인쇄관련 산업","182":"기록매체 복제업",
    "191":"코크스 및 연탄 제조업","192":"석유 정제품 제조업",
    "201":"기초 화학물질 제조업","202":"기타 화학제품 제조업","203":"합성고무 및 플라스틱 물질 제조업",
    "211":"기초 의약물질 및 생물학적 제제 제조업","212":"의약품 제조업",
    "213":"의료용품 및 기타 의약 관련제품 제조업",
    "221":"고무제품 제조업","222":"플라스틱제품 제조업",
    "231":"유리 및 유리제품 제조업","232":"도자기 및 기타 요업제품 제조업",
    "233":"시멘트, 석회, 플라스터 및 그 제품 제조업","239":"기타 비금속 광물제품 제조업",
    "241":"1차 철강 제조업","242":"1차 비철금속 제조업","243":"금속 주조업",
    "251":"구조용 금속제품, 탱크 및 증기발생기 제조업","252":"무기 및 총포탄 제조업",
    "259":"기타 금속가공제품 제조업",
    "261":"반도체 제조업","262":"전자부품 제조업","263":"컴퓨터 및 주변장치 제조업",
    "264":"통신 및 방송장비 제조업","265":"영상 및 음향기기 제조업","266":"마그네틱 및 광학 매체 제조업",
    "271":"의료용 기기 제조업","272":"측정, 시험, 항해, 제어 및 기타 정밀기기 제조업",
    "273":"사진장비 및 광학기기 제조업","274":"시계 및 시계부품 제조업",
    "281":"전동기, 발전기 및 전기 변환·공급·제어 장치 제조업","282":"일차전지 및 축전지 제조업",
    "283":"절연선 및 케이블 제조업","284":"전구 및 조명장치 제조업",
    "285":"가정용 기기 제조업","289":"기타 전기장비 제조업",
    "291":"일반 목적용 기계 제조업","292":"특수 목적용 기계 제조업",
    "301":"자동차용 엔진 및 자동차 제조업","302":"자동차 차체 및 트레일러 제조업",
    "303":"자동차 신품 부품 및 부속품 제조업","304":"자동차 재제조 부품 제조업",
    "311":"선박 및 보트 건조업","312":"철도장비 제조업",
    "313":"항공기, 우주선 및 부품 제조업","319":"그 외 기타 운송장비 제조업",
    "320":"가구 제조업",
    "331":"귀금속 및 장신용품 제조업","332":"악기 제조업",
    "333":"운동 및 경기용구 제조업","334":"인형, 장난감 및 오락용품 제조업",
    "339":"그 외 기타 제품 제조업","340":"산업용 기계 및 장비 수리업",
    "351":"전기업","352":"가스 제조 및 배관공급업","353":"증기, 냉·온수 및 공기 조절 공급업",
    "360":"수도업","370":"하수, 폐수 및 분뇨 처리업",
    "381":"폐기물 수집, 운반업","382":"폐기물 처리업","383":"금속 및 비금속 원료 재생업",
    "390":"환경 정화 및 복원업",
    "411":"건물 건설업","412":"토목 건설업",
    "421":"기반조성 및 시설물 축조관련 전문공사업","422":"건물설비 설치 공사업",
    "423":"전기 및 통신 공사업","424":"실내건축 및 건축마무리 공사업","425":"건설장비 운영업",
    "451":"자동차 판매업","452":"자동차 부품 및 내장품 판매업","453":"모터사이클 및 부품 판매업",
    "461":"상품 중개업","462":"산업용 농축산물 및 산동물 도매업",
    "463":"음·식료품 및 담배 도매업","464":"생활용품 도매업",
    "465":"기계장비 및 관련 물품 도매업","466":"건축자재, 철물 및 난방장치 도매업",
    "467":"기타 전문 도매업","468":"상품 종합 도매업",
    "471":"종합 소매업","472":"음·식료품 및 담배 소매업",
    "473":"정보통신장비 소매업","474":"섬유, 의복, 신발 및 가죽제품 소매업",
    "475":"기타 가정용품 소매업","476":"문화, 오락 및 여가 용품 소매업",
    "477":"연료 소매업","478":"기타 상품 전문 소매업","479":"무점포 소매업",
    "491":"철도운송업","492":"육상여객 운송업","493":"도로화물 운송업",
    "494":"소화물 전문 운송업","495":"파이프라인 운송업",
    "501":"해상 운송업","502":"내륙 수상 및 항만 내 운송업",
    "511":"정기 항공 운송업","512":"부정기 항공 운송업",
    "521":"보관 및 창고업","529":"기타 운송관련 서비스업",
    "551":"일반 및 생활 숙박시설 운영업","559":"기타 숙박업",
    "561":"음식점업","562":"주점 및 비알코올음료점업",
    "581":"서적, 잡지 및 기타 인쇄물 출판업","582":"소프트웨어 개발 및 공급업",
    "591":"영화, 비디오물, 방송프로그램 제작 및 배급업","592":"오디오물 출판 및 원판 녹음업",
    "601":"라디오 방송업","602":"텔레비전 방송업",
    "612":"전기 통신업","620":"컴퓨터 프로그래밍, 시스템 통합 및 관리업",
    "631":"자료처리, 호스팅, 포털 및 기타 인터넷 정보매개 서비스업",
    "639":"기타 정보 서비스업",
    "641":"은행 및 저축기관","642":"투자기관","649":"기타 금융업",
    "651":"보험업","652":"재보험업","653":"연금 및 공제업",
    "661":"금융 지원 서비스업","662":"보험 및 연금관련 서비스업",
    "681":"부동산 임대 및 공급업","682":"부동산 관련 서비스업",
    "701":"자연과학 및 공학 연구개발업","702":"인문 및 사회과학 연구개발업",
    "711":"법무 관련 서비스업","712":"회계 및 세무 관련 서비스업",
    "713":"광고업","714":"시장조사 및 여론조사업",
    "715":"회사본부 및 경영컨설팅 서비스업","716":"기타 전문서비스업",
    "721":"건축기술, 엔지니어링 및 관련기술 서비스업","722":"기타 과학기술 서비스업",
    "731":"수의업","732":"전문 디자인업","733":"사진 촬영 및 처리업",
    "739":"그 외 기타 전문, 과학 및 기술 서비스업",
    "741":"사업시설 유지관리 서비스업","742":"건물·산업설비 청소 및 방제 서비스업",
    "743":"조경 관리 및 유지 서비스업",
    "751":"고용 알선 및 인력 공급업","752":"여행사 및 기타 여행보조 서비스업",
    "753":"보안, 경비 및 탐정업","759":"기타 사업지원 서비스업",
    "761":"산업용 기계 및 장비 임대업","762":"개인 및 가정용품 임대업","763":"무형재산권 임대업",
    "851":"초등 교육기관","852":"중등 교육기관","853":"고등 교육기관",
    "854":"특수학교, 외국인학교 및 대안학교","855":"일반 교습 학원",
    "856":"기타 교육기관","857":"교육지원 서비스업",
    "861":"병원","862":"의원","863":"공중 보건 의료업","869":"기타 보건업",
    "871":"거주 복지시설 운영업","872":"비거주 복지시설 운영업",
    "901":"창작 및 예술관련 서비스업","902":"도서관, 사적지 및 유사 여가관련 서비스업",
    "911":"스포츠 서비스업","912":"유원지 및 기타 오락관련 서비스업",
    "941":"산업 및 전문가 단체","942":"노동조합","949":"기타 협회 및 단체",
    "951":"개인 및 소비용품 수리업",
    "961":"미용, 욕탕 및 유사 서비스업","969":"그 외 기타 개인 서비스업",
}


def lookup_major(code):
    code = str(code).strip()
    if not code:
        return None
    return KSIC_MAJOR.get(code[:2].zfill(2))


def lookup_small(code):
    code = str(code).strip()
    if len(code) < 3:
        return None
    return KSIC_SMALL.get(code[:3].zfill(3))


def download_corp_code():
    """DART corpCode.xml 다운로드 + 압축해제"""
    if os.path.exists(CORP_XML):
        print(f"  기존 CORPCODE.xml 사용 ({os.path.getsize(CORP_XML)//1024} KB)")
        return
    print("  corpCode.xml 다운로드 중...")
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(OUT_DIR)
    print(f"  완료 ({os.path.getsize(CORP_XML)//1024} KB)")


def get_listed_corps():
    tree = ET.parse(CORP_XML)
    root = tree.getroot()
    corps = []
    for item in root.findall("list"):
        s = (item.findtext("stock_code", "") or "").strip()
        c = (item.findtext("corp_code", "") or "").strip()
        n = (item.findtext("corp_name", "") or "").strip()
        if s:
            corps.append((c, n, s))
    return corps


def fetch_company(corp_code):
    """단일 회사 기업개황 조회 (지수 백오프)"""
    url = f"https://opendart.fss.or.kr/api/company.json?crtfc_key={API_KEY}&corp_code={corp_code}"
    delay = 0.5
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            if data.get("status") == "000":
                return data
            return None
        except Exception:
            if attempt < MAX_RETRY - 1:
                time.sleep(delay)
                delay *= 1.6
    return None


def load_progress():
    if os.path.exists(TEMP_PATH):
        with open(TEMP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(data):
    with open(TEMP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1/3] DART corpCode 준비")
    download_corp_code()

    print("\n[2/3] 상장사 목록 추출")
    corps = get_listed_corps()
    print(f"  종목코드 보유 법인: {len(corps):,}개")

    progress = load_progress()
    pending = [(c, n, s) for c, n, s in corps if c not in progress]
    print(f"  기 수집: {len(progress):,}개 / 신규 수집 대상: {len(pending):,}개")

    print(f"\n[3/3] 기업개황 조회 (워커 {WORKERS}개, 호출간 {SLEEP_SEC}초)")
    eta = len(pending) * (SLEEP_SEC + 0.3) / max(WORKERS, 1) / 60
    print(f"  예상 시간: {eta:.1f}분")

    cls_map = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX", "E": "기타"}
    lock = threading.Lock()
    counter = {"done": 0, "ok": 0}

    def task(args):
        cc, name, stock = args
        data = fetch_company(cc)
        result = None
        if data:
            result = {
                "stock_code": str(stock).zfill(6),
                "corp_code": cc,
                "name": data.get("corp_name", name),
                "induty_code": str(data.get("induty_code", "")).strip(),
                "market_raw": data.get("corp_cls", ""),
                "market": cls_map.get(data.get("corp_cls", "").strip(), "기타"),
            }
        time.sleep(SLEEP_SEC)
        return cc, result

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(task, item) for item in pending]
        for fut in as_completed(futures):
            cc, result = fut.result()
            with lock:
                counter["done"] += 1
                if result:
                    progress[cc] = result
                    counter["ok"] += 1
                if counter["done"] % 200 == 0:
                    save_progress(progress)
                    print(f"  진행 {counter['done']}/{len(pending)} (성공 {counter['ok']}, 전체 누적 {len(progress)})")

    save_progress(progress)
    print(f"\n  최종 수집: {len(progress):,}개")

    # ============ JSON 변환 ============
    companies = []
    major_set = {}
    small_set = {}

    for cc, info in progress.items():
        induty = info["induty_code"]
        if not induty:
            continue
        major_code = induty[:2].zfill(2)
        small_code = induty[:3].zfill(3) if len(induty) >= 3 else None
        major_name = lookup_major(induty) or "미분류"
        small_name = lookup_small(induty)

        companies.append({
            "stock_code": info["stock_code"],
            "corp_code": info["corp_code"],
            "name": info["name"],
            "induty_code": induty,
            "major_code": major_code,
            "major_name": major_name,
            "small_code": small_code,
            "small_name": small_name,
            "market": info["market"],
        })
        major_set[major_code] = major_name
        if small_code and small_name:
            small_set[small_code] = small_name

    output = {
        "version": "KSIC-11th-2026-05",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "DART OpenAPI (opendart.fss.or.kr) + 한국표준산업분류 11차",
        "categories_major": dict(sorted(major_set.items())),
        "categories_small": dict(sorted(small_set.items())),
        "companies": companies,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    market_count = {}
    for c in companies:
        market_count[c["market"]] = market_count.get(c["market"], 0) + 1

    print(f"\n저장 완료: {OUT_PATH}")
    print(f"  - 회사: {len(companies):,}개")
    print(f"  - 대분류: {len(major_set)}개")
    print(f"  - 소분류: {len(small_set)}개")
    print(f"  - 시장별: {market_count}")


if __name__ == "__main__":
    main()
