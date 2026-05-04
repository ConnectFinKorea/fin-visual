// ============== Navigation Map ==============
const NAV = {
  market: {
    label: "Market",
    groups: [
      { name: "Equity",    items: [
        { id: "market-cap",     label: "시가총액" },
        { id: "market-change",  label: "변동률" },
      ]},
      { name: "Financial", items: [
        { id: "market-revenue", label: "매출액" },
        { id: "market-opincome",label: "영업이익" },
      ]},
    ],
  },
  valuation: {
    label: "Valuation",
    groups: [
      { name: "Equity",    items: [
        { id: "val-trading", label: "Trading" },
        { id: "val-income",  label: "Income" },
      ]},
      { name: "Mezzanine", items: [
        { id: "val-rcps", label: "RCPS" },
        { id: "val-bw",   label: "BW" },
        { id: "val-cb",   label: "CB" },
      ]},
    ],
  },
  macro: {
    label: "Macro Eco",
    groups: [
      { name: "Indicator", items: [
        { id: "macro-prime",     label: "Prime Rate" },
        { id: "macro-bond",      label: "Bond(10YR)" },
        { id: "macro-inflation", label: "Inflation" },
        { id: "macro-unemp",     label: "실업률" },
      ]},
    ],
  },
  news: {
    label: "News",
    groups: [
      { name: "Source", items: [
        { id: "news-thebell", label: "TheBell" },
        { id: "news-naver",   label: "네이버파이넨셜" },
      ]},
    ],
  },
};

// ============== Dummy Data ==============
const TOP_INDUSTRIES = [
  { name: "반도체", total: "1,890조", delta: -1.5, companies: [
    { name: "삼성전자", cap: "977조", pct: -1.2 },
    { name: "SK하이닉스", cap: "575조", pct: 1.5 },
    { name: "삼성전기", cap: "12조", pct: 0.8 },
    { name: "DB하이텍", cap: "5조", pct: -2.1 },
  ], rise: ["피에스케이 (▲5.2%)", "원익IPS (▲3.8%)"]},
  { name: "완성차 제조업", total: "120조", delta: -1.5, companies: [
    { name: "현대차", cap: "91조", pct: -1.2 },
    { name: "기아", cap: "42조", pct: 1.5 },
  ], rise: ["KG모빌리티 (▲4.1%)"]},
  { name: "자동차 부품산업", total: "45조", delta: -0.8, companies: [
    { name: "현대모비스", cap: "21조", pct: -0.6 },
    { name: "한온시스템", cap: "5조", pct: -1.5 },
  ], rise: ["에스엘 (▲3.2%)"]},
  { name: "의약품 제조업", total: "180조", delta: 2.1, companies: [
    { name: "삼성바이오로직스", cap: "69조", pct: 2.4 },
    { name: "셀트리온", cap: "43조", pct: 1.8 },
  ], rise: ["알테오젠 (▲6.7%)"]},
  { name: "은행업", total: "95조", delta: 0.4, companies: [
    { name: "KB금융", cap: "32조", pct: 0.6 },
    { name: "신한지주", cap: "29조", pct: 0.3 },
  ], rise: ["JB금융지주 (▲2.4%)"]},
  { name: "통신업", total: "38조", delta: -0.3, companies: [
    { name: "SK텔레콤", cap: "16조", pct: -0.2 },
    { name: "KT", cap: "12조", pct: -0.5 },
  ], rise: ["LG유플러스 (▲1.2%)"]},
  { name: "이차전지", total: "150조", delta: 3.2, companies: [
    { name: "LG에너지솔루션", cap: "92조", pct: 3.5 },
    { name: "삼성SDI", cap: "32조", pct: 2.1 },
  ], rise: ["에코프로비엠 (▲5.8%)"]},
  { name: "철강업", total: "30조", delta: -1.8, companies: [
    { name: "POSCO홀딩스", cap: "18조", pct: -2.0 },
    { name: "현대제철", cap: "5조", pct: -1.2 },
  ], rise: ["세아베스틸지주 (▲1.5%)"]},
  { name: "조선업", total: "55조", delta: 1.2, companies: [
    { name: "HD현대중공업", cap: "48조", pct: 1.5 },
    { name: "삼성중공업", cap: "12조", pct: 0.8 },
  ], rise: ["한화오션 (▲2.8%)"]},
  { name: "유통업", total: "25조", delta: -0.5, companies: [
    { name: "신세계", cap: "8조", pct: -0.7 },
    { name: "이마트", cap: "5조", pct: -0.3 },
  ], rise: ["BGF리테일 (▲1.8%)"]},
  { name: "기타 산업", total: "650조", delta: 0.2, companies: [
    { name: "기타 상장사 다수", cap: "650조", pct: 0.2 },
  ], rise: []},
];

// ============== Routing Map ==============
// URL 경로 → pageId 매핑 (트리 구조)
const ROUTES = {
  "/":                                       "home",
  "/market":                                 "market-cap",       // 그룹 진입 시 첫 항목
  "/market/equity":                          "market-cap",
  "/market/equity/market-cap":               "market-cap",
  "/market/equity/change":                   "market-change",
  "/market/financial":                       "market-revenue",
  "/market/financial/revenue":               "market-revenue",
  "/market/financial/operating-income":      "market-opincome",
  "/valuation":                              "val-trading",
  "/valuation/equity":                       "val-trading",
  "/valuation/equity/trading":               "val-trading",
  "/valuation/equity/income":                "val-income",
  "/valuation/mezzanine":                    "val-rcps",
  "/valuation/mezzanine/rcps":               "val-rcps",
  "/valuation/mezzanine/bw":                 "val-bw",
  "/valuation/mezzanine/cb":                 "val-cb",
  "/macro":                                  "macro-prime",
  "/macro/prime-rate":                       "macro-prime",
  "/macro/bond":                             "macro-bond",
  "/macro/inflation":                        "macro-inflation",
  "/macro/unemployment":                     "macro-unemp",
  "/news":                                   "news-thebell",
  "/news/thebell":                           "news-thebell",
  "/news/naver-financial":                   "news-naver",
};

// pageId → URL 정규형 (가장 구체적인 경로)
const PAGE_TO_URL = {
  "home":            "/",
  "market-cap":      "/market/equity/market-cap",
  "market-change":   "/market/equity/change",
  "market-revenue":  "/market/financial/revenue",
  "market-opincome": "/market/financial/operating-income",
  "val-trading":     "/valuation/equity/trading",
  "val-income":      "/valuation/equity/income",
  "val-rcps":        "/valuation/mezzanine/rcps",
  "val-bw":          "/valuation/mezzanine/bw",
  "val-cb":          "/valuation/mezzanine/cb",
  "macro-prime":     "/macro/prime-rate",
  "macro-bond":      "/macro/bond",
  "macro-inflation": "/macro/inflation",
  "macro-unemp":     "/macro/unemployment",
  "news-thebell":    "/news/thebell",
  "news-naver":      "/news/naver-financial",
};

// pageId → 브라우저 탭 타이틀
const PAGE_TITLES = {
  "home":            "FinVisual",
  "market-cap":      "시가총액 · FinVisual",
  "market-change":   "변동률 · FinVisual",
  "market-revenue":  "매출액 · FinVisual",
  "market-opincome": "영업이익 · FinVisual",
  "val-trading":     "Trading Multiple · FinVisual",
  "val-income":      "Income Approach · FinVisual",
  "val-rcps":        "RCPS · FinVisual",
  "val-bw":          "BW · FinVisual",
  "val-cb":          "CB · FinVisual",
  "macro-prime":     "Prime Rate · FinVisual",
  "macro-bond":      "10Y Bond · FinVisual",
  "macro-inflation": "Inflation · FinVisual",
  "macro-unemp":     "Unemployment · FinVisual",
  "news-thebell":    "TheBell · FinVisual",
  "news-naver":      "네이버파이넨셜 · FinVisual",
};

function urlForPage(pageId) { return PAGE_TO_URL[pageId] || "/"; }
function pageForUrl(path) {
  // 끝의 / 제거 (단, 루트 / 는 유지)
  const clean = path.length > 1 ? path.replace(/\/$/, "") : path;
  return ROUTES[clean] || "home";
}

// ============== State ==============
let currentPage = "home";

// ============== Renderer ==============
const $main    = document.getElementById("main");
const $sidebar = document.getElementById("sidebar");
const $dropdown= document.getElementById("dropdown");
const $navBtns = document.querySelectorAll(".nav-btn");

function pageOf(id) {
  for (const tab of Object.keys(NAV)) {
    for (const g of NAV[tab].groups) {
      const item = g.items.find(i => i.id === id);
      if (item) return { tab, group: g.name, item };
    }
  }
  return null;
}

function renderSidebar(tab) {
  if (!tab) {
    $sidebar.innerHTML = `<div class="sb-title">FinVisual</div>
      <div class="sb-group-name">Welcome</div>
      <div class="sb-link active">홈</div>`;
    return;
  }
  const data = NAV[tab];
  let html = `<div class="sb-title">${data.label}</div>`;
  for (const g of data.groups) {
    html += `<div class="sb-group">
      <div class="sb-group-name">${g.name}</div>`;
    for (const it of g.items) {
      const cls = it.id === currentPage ? "sb-link active" : "sb-link";
      html += `<a class="${cls}" data-page="${it.id}">${it.label}</a>`;
    }
    html += `</div>`;
  }
  $sidebar.innerHTML = html;
  $sidebar.querySelectorAll(".sb-link[data-page]").forEach(el => {
    el.addEventListener("click", () => navigate(el.dataset.page));
  });
}

function renderHome() {
  $main.innerHTML = `
    <div class="home">
      <h1>Welcome to <span class="accent">Financial Playground</span></h1>
      <p>Thanks for coming to <span style="color: var(--primary); font-weight: 700;">Financial Playground.</span></p>
      <p>The purpose of this website is to visualize equity market's movement, and to spot changes across the industries.</p>
      <p>I'm very appreciate your comment on this website</p>
      <p class="footnote">(First written in 26.04.29)</p>
    </div>`;
}

function fmtPct(v) {
  const tri = v >= 0 ? "▲" : "▼";
  const cls = v >= 0 ? "delta-up" : "delta-down";
  return `<span class="${cls}">${tri}${Math.abs(v).toFixed(1)}%</span>`;
}

// ============== Market Cap Treemap (finviz 스타일) ==============
// 데이터 소스: GitHub Actions가 data-snapshot 브랜치에 갱신
//   - industry_mapping.json: 월 1회 (DART → KSIC 11차)
//   - listed_stocks.json:    매일 23:59 KST (DART CORPCODE)
//   - snapshot.json:         평일 09-16 KST 정시 (네이버 금융)
const GH_USER = "ConnectFinKorea";
const GH_REPO = "fin-visual";
const DATA_BRANCH = "data-snapshot";
const RAW_BASE = `https://raw.githubusercontent.com/${GH_USER}/${GH_REPO}/${DATA_BRANCH}`;
// 1분 단위 캐시버스팅 (raw.githubusercontent CDN max-age=300 회피)
const CACHE_BUST = () => `?t=${Math.floor(Date.now() / 60000)}`;
const SNAPSHOT_URL = () => `${RAW_BASE}/snapshot.json${CACHE_BUST()}`;
const MAPPING_URL = () => `${RAW_BASE}/industry_mapping.json${CACHE_BUST()}`;
const MAPPING_URL_FALLBACK = "/data/industry_mapping.json";

async function renderMarketCap() {
  $main.innerHTML = `
    <div class="page-title">시가총액 트리맵 <span class="crumb">/ Market · Equity</span></div>
    <div class="treemap-meta">
      <span id="tm-status">데이터 로딩 중...</span>
      <span class="treemap-legend">
        <span class="lg-up"></span>상승
        <span class="lg-down"></span>하락
      </span>
    </div>
    <div id="treemap-container" class="treemap-container"></div>
    <div class="treemap-footnote">
      박스 크기 = 시가총액 · 색상 = 일별 등락률 ·
      대분류는 한국표준산업분류 11차 기준 ·
      대분류별 시총 상위 5개 + 기타로 합산
    </div>
  `;

  const $status = document.getElementById("tm-status");
  try {
    const [mapping, snapshot] = await Promise.all([
      fetchMapping(),
      fetch(SNAPSHOT_URL()).then(r => {
        if (!r.ok) throw new Error("snapshot.json 로드 실패 (data-snapshot 브랜치 확인)");
        return r.json();
      }),
    ]);
    drawTreemap(mapping, snapshot);
    const ts = new Date(snapshot.timestamp || Date.now()).toLocaleString("ko-KR");
    $status.textContent = `${snapshot.count?.toLocaleString() || 0}개 종목 · 업데이트 ${ts}`;
  } catch (err) {
    $status.innerHTML = `<span style="color:var(--red)">로드 실패: ${err.message}</span>`;
    document.getElementById("treemap-container").innerHTML =
      `<div class="treemap-fallback">
        <p>실시간 데이터를 불러올 수 없습니다.</p>
        <p style="font-size:11px; color: var(--text-3);">
          확인할 항목:<br>
          · GitHub Actions data-snapshot 브랜치에 snapshot.json 존재 여부<br>
          · GitHub Actions 워크플로 실행 상태 (Actions 탭)
        </p>
      </div>`;
  }
}

async function fetchMapping() {
  // 1순위: data-snapshot 브랜치 (월 1회 갱신, 가장 최신)
  try {
    const r = await fetch(MAPPING_URL());
    if (r.ok) return r.json();
  } catch (_) { /* fallback */ }
  // 2순위: main 브랜치의 시드 파일 (CF Pages 정적 서빙)
  const r = await fetch(MAPPING_URL_FALLBACK);
  if (!r.ok) throw new Error("industry_mapping.json 로드 실패");
  return r.json();
}

function drawTreemap(mapping, snapshot) {
  const container = document.getElementById("treemap-container");
  if (typeof d3 === "undefined") {
    container.innerHTML = `<p style="color:var(--red)">D3.js 로드 실패</p>`;
    return;
  }

  // 1) stock_code → 분류 정보 매핑
  const codeToInfo = {};
  for (const c of mapping.companies) {
    codeToInfo[c.stock_code] = c;
  }

  // 2) 시세 + 분류 결합
  const enriched = [];
  for (const it of snapshot.items || []) {
    const info = codeToInfo[it.code];
    if (!info || !info.major_code || it.mcap <= 0) continue;
    enriched.push({
      code: it.code,
      name: it.name || info.name,
      mcap: it.mcap,
      change: isFinite(it.change) ? it.change : 0,
      major_code: info.major_code,
      major_name: info.major_name,
      market: it.market || info.market,
    });
  }

  // 3) 대분류로 그룹화
  const groups = {};
  for (const e of enriched) {
    if (!groups[e.major_code]) {
      groups[e.major_code] = {
        code: e.major_code,
        name: e.major_name,
        companies: [],
      };
    }
    groups[e.major_code].companies.push(e);
  }

  // 4) 각 분류 내 시총 정렬, 상위 5 + 기타로 압축, 시총 합계·가중평균 등락률 계산
  const groupArr = Object.values(groups);
  for (const g of groupArr) {
    g.companies.sort((a, b) => b.mcap - a.mcap);
    if (g.companies.length > 5) {
      const tail = g.companies.slice(5);
      const tailSum = tail.reduce((s, c) => s + c.mcap, 0);
      const tailChg = tailSum > 0
        ? tail.reduce((s, c) => s + c.change * c.mcap, 0) / tailSum
        : 0;
      g.companies = g.companies.slice(0, 5);
      g.companies.push({
        code: "_OTHER_" + g.code,
        name: "기타",
        mcap: tailSum,
        change: tailChg,
        isOther: true,
      });
    }
    g.totalMcap = g.companies.reduce((s, c) => s + c.mcap, 0);
    g.weightedChange = g.totalMcap > 0
      ? g.companies.reduce((s, c) => s + c.change * c.mcap, 0) / g.totalMcap
      : 0;
  }
  groupArr.sort((a, b) => b.totalMcap - a.totalMcap);

  // 5) 컨테이너 사이즈 + 모바일 판정
  const W = container.clientWidth || 800;
  const H = Math.max(420, Math.min(window.innerHeight - 220, W * 0.72));
  const isMobile = W < 600;

  // 색상 함수: 등락률 → R/G/B (red↑ blue↓)
  const colorFor = (chg) => {
    if (!isFinite(chg)) return "#888";
    const t = Math.min(1, Math.abs(chg) / 4);
    if (chg >= 0) {
      return `rgb(200, ${Math.round(140 - t*70)}, ${Math.round(140 - t*70)})`;
    } else {
      return `rgb(${Math.round(140 - t*70)}, ${Math.round(140 - t*70)}, 200)`;
    }
  };

  // 6) Pass 1 — 카테고리(대분류) 위치 계산
  // 카테고리 크기는 totalMcap (top5 + 기타 합산) 기준
  const catRoot = d3.hierarchy({
    children: groupArr.map(g => ({ ...g, value: g.totalMcap }))
  })
    .sum(d => d.value || 0)
    .sort((a, b) => b.value - a.value);

  d3.treemap()
    .tile(d3.treemapSquarify.ratio(1.5))
    .size([W, H])
    .paddingOuter(2)
    .paddingInner(2)
    .round(true)(catRoot);

  // 7) Pass 2 — 각 카테고리 내부에서 top5 회사들 + 기타 strip 배치
  const TITLE_H = isMobile ? 16 : 20;   // 카테고리 제목용 상단 패딩
  const OTHER_H = isMobile ? 16 : 18;   // 기타 strip 고정 높이
  const cells = [];                     // 회사 셀 (시각화 대상)
  const otherStrips = [];               // 기타 strip (시각화 대상)

  for (const cat of catRoot.children || []) {
    const catW = cat.x1 - cat.x0;
    const catH = cat.y1 - cat.y0;
    const g = cat.data;
    const top5 = g.companies.filter(c => !c.isOther);
    const otherCo = g.companies.find(c => c.isOther);

    // 너무 작으면 회사 셀 생략
    if (catW < 24 || catH < TITLE_H + 12) continue;

    // 기타 strip을 둘 공간이 있으면 예약, 아니면 회사가 전 공간 사용
    const hasOtherSpace = otherCo && (catH >= TITLE_H + OTHER_H + 8);
    const innerH = hasOtherSpace ? catH - TITLE_H - OTHER_H : catH - TITLE_H;
    const innerY0 = cat.y0 + TITLE_H;

    // top5에 대해 별도 treemap 실행
    if (top5.length > 0 && innerH > 6 && catW > 6) {
      const subRoot = d3.hierarchy({
        children: top5.map(c => ({ ...c, value: c.mcap }))
      })
        .sum(d => d.value || 0)
        .sort((a, b) => b.value - a.value);

      d3.treemap()
        .tile(d3.treemapSquarify.ratio(1.5))
        .size([catW - 2, innerH])
        .paddingInner(1)
        .round(true)(subRoot);

      for (const leaf of subRoot.leaves()) {
        cells.push({
          x0: cat.x0 + 1 + leaf.x0,
          y0: innerY0 + leaf.y0,
          x1: cat.x0 + 1 + leaf.x1,
          y1: innerY0 + leaf.y1,
          name: leaf.data.name,
          change: leaf.data.change,
          mcap: leaf.data.mcap,
        });
      }
    }

    // 기타 strip
    if (hasOtherSpace) {
      otherStrips.push({
        x0: cat.x0 + 1,
        y0: cat.y1 - OTHER_H - 1,
        x1: cat.x1 - 1,
        y1: cat.y1 - 1,
        mcap: otherCo.mcap,
        change: otherCo.change,
      });
    }
  }

  // 8) SVG 렌더링
  d3.select(container).selectAll("*").remove();
  const svg = d3.select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${W} ${H}`)
    .attr("width", "100%")
    .style("height", H + "px")
    .style("font-family", "inherit");

  // 8-a) 카테고리 외곽 + 제목
  const catG = svg.selectAll("g.cat")
    .data(catRoot.children || [])
    .join("g")
    .attr("class", "tm-cat")
    .attr("transform", d => `translate(${d.x0},${d.y0})`);

  catG.append("rect")
    .attr("width",  d => Math.max(0, d.x1 - d.x0))
    .attr("height", d => Math.max(0, d.y1 - d.y0))
    .attr("fill", "transparent")
    .attr("stroke", "var(--text-2)")
    .attr("stroke-width", 0.5);

  catG.append("text")
    .attr("x", 4)
    .attr("y", isMobile ? 11 : 13)
    .style("font-size", isMobile ? "9px" : "10.5px")
    .style("font-weight", 700)
    .style("fill", "var(--text)")
    .text(d => {
      const w = d.x1 - d.x0;
      if (w < 60) return "";
      const g = d.data;
      const sign = g.weightedChange >= 0 ? "+" : "";
      const pct = `${sign}${g.weightedChange.toFixed(1)}%`;
      const txt = g.name + ` (${pct})`;
      return w < 200 ? truncate(txt, Math.floor(w / (isMobile ? 6.2 : 7))) : txt;
    });

  // 8-b) 회사 셀 (top5)
  const leafG = svg.selectAll("g.leaf")
    .data(cells)
    .join("g")
    .attr("class", "tm-leaf")
    .attr("transform", d => `translate(${d.x0},${d.y0})`);

  leafG.append("rect")
    .attr("width",  d => Math.max(0, d.x1 - d.x0))
    .attr("height", d => Math.max(0, d.y1 - d.y0))
    .attr("fill", d => colorFor(d.change))
    .attr("stroke", "var(--card)")
    .attr("stroke-width", 0.5);

  leafG.append("text")
    .attr("x", 4).attr("y", 12)
    .style("font-size", "10.5px")
    .style("font-weight", 700)
    .style("fill", "#ffffff")
    .style("pointer-events", "none")
    .text(d => {
      const w = d.x1 - d.x0, h = d.y1 - d.y0;
      if (w < 38 || h < 18) return "";
      return truncate(d.name, Math.floor(w / 6.5));
    });

  leafG.append("text")
    .attr("x", 4).attr("y", 24)
    .style("font-size", "9.5px")
    .style("fill", "rgba(255,255,255,0.92)")
    .style("pointer-events", "none")
    .text(d => {
      const w = d.x1 - d.x0, h = d.y1 - d.y0;
      if (w < 50 || h < 30) return "";
      const sign = d.change >= 0 ? "+" : "";
      return `${sign}${d.change.toFixed(2)}%`;
    });

  leafG.append("text")
    .attr("x", 4).attr("y", 36)
    .style("font-size", "9px")
    .style("fill", "rgba(255,255,255,0.78)")
    .style("pointer-events", "none")
    .text(d => {
      const w = d.x1 - d.x0, h = d.y1 - d.y0;
      if (w < 70 || h < 44) return "";
      return formatMcap(d.mcap);
    });

  leafG.append("title")
    .text(d => {
      const sign = d.change >= 0 ? "+" : "";
      return `${d.name}\n시총: ${formatMcap(d.mcap)}원\n등락률: ${sign}${d.change.toFixed(2)}%`;
    });

  // 8-c) 기타 strip (카테고리 하단 고정 높이)
  const otherG = svg.selectAll("g.tm-other")
    .data(otherStrips)
    .join("g")
    .attr("class", "tm-other")
    .attr("transform", d => `translate(${d.x0},${d.y0})`);

  otherG.append("rect")
    .attr("width",  d => Math.max(0, d.x1 - d.x0))
    .attr("height", d => Math.max(0, d.y1 - d.y0))
    .attr("fill", d => colorFor(d.change))
    .attr("fill-opacity", 0.55)
    .attr("stroke", "var(--card)")
    .attr("stroke-width", 0.5);

  // 기타 strip 텍스트: 좌측 "기타", 우측 "시총 · 등락률"
  otherG.append("text")
    .attr("x", 5)
    .attr("y", d => (d.y1 - d.y0) / 2 + 3.5)
    .style("font-size", isMobile ? "9px" : "10px")
    .style("font-weight", 700)
    .style("fill", "#ffffff")
    .style("pointer-events", "none")
    .text(d => {
      const w = d.x1 - d.x0;
      if (w < 36) return "";
      return "기타";
    });

  otherG.append("text")
    .attr("x", d => (d.x1 - d.x0) - 5)
    .attr("y", d => (d.y1 - d.y0) / 2 + 3.5)
    .attr("text-anchor", "end")
    .style("font-size", isMobile ? "9px" : "10px")
    .style("fill", "#ffffff")
    .style("pointer-events", "none")
    .text(d => {
      const w = d.x1 - d.x0;
      if (w < 80) return "";
      const sign = d.change >= 0 ? "+" : "";
      return `${formatMcap(d.mcap)} · ${sign}${d.change.toFixed(2)}%`;
    });

  otherG.append("title")
    .text(d => {
      const sign = d.change >= 0 ? "+" : "";
      return `기타 종목 합산\n시총: ${formatMcap(d.mcap)}원\n가중평균 등락률: ${sign}${d.change.toFixed(2)}%`;
    });
}

function truncate(s, n) {
  if (!s) return "";
  return s.length > n ? s.slice(0, Math.max(1, n - 1)) + "…" : s;
}

function formatMcap(billionsKR) {
  // 입력 단위: 억원
  if (billionsKR >= 10000) return (billionsKR / 10000).toFixed(1) + "조";
  if (billionsKR >= 1000)  return (billionsKR / 1000).toFixed(0) * 1000 + "억";
  return Math.round(billionsKR) + "억";
}

// 윈도우 리사이즈 시 트리맵 재렌더 (현재 페이지가 트리맵인 경우)
let _resizeTimer;
window.addEventListener("resize", () => {
  if (currentPage !== "market-cap") return;
  clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(() => renderMarketCap(), 200);
});

function renderMarketChange() {
  let html = `<div class="page-title">변동률 <span class="crumb">/ Market · Equity</span></div>`;
  // 일별 변동률 ranking
  const ranked = [...TOP_INDUSTRIES].sort((a,b) => b.delta - a.delta);
  html += `<div class="compare-card"><h4>업종별 일별 변동률 (2026-04-30)</h4>
    <div class="row head"><span>산업</span><span class="num">변동률</span><span class="num">시총</span><span class="num">대표</span></div>`;
  for (const ind of ranked) {
    html += `<div class="row">
      <span>${ind.name}</span>
      <span class="num">${fmtPct(ind.delta)}</span>
      <span class="num">${ind.total}</span>
      <span class="num">${ind.companies[0].name}</span>
    </div>`;
  }
  html += `</div>`;
  $main.innerHTML = html;
}

function renderFinancial(kind) {
  const label = kind === "revenue" ? "매출액" : "영업이익";
  const yoy_data = TOP_INDUSTRIES.slice(0, 8).map((ind, i) => {
    const base = kind === "revenue" ? 50 + i * 7 : 8 + i * 1.4;
    return {
      name: ind.name,
      val: base.toFixed(0) + "조",
      yoy: ((Math.sin(i*1.3) * 12)).toFixed(1),
    };
  });
  let html = `<div class="page-title">${label} <span class="crumb">/ Market · Financial</span></div>
    <div class="compare-card"><h4>업종별 ${label} (2025년 연간 / YoY)</h4>
    <div class="row head"><span>산업</span><span class="num">${label}</span><span class="num">YoY</span><span class="num">기준</span></div>`;
  for (const r of yoy_data) {
    html += `<div class="row">
      <span>${r.name}</span>
      <span class="num">${r.val}</span>
      <span class="num">${fmtPct(parseFloat(r.yoy))}</span>
      <span class="num" style="color:var(--text-3); font-size:10px;">FY25</span>
    </div>`;
  }
  html += `</div>`;
  $main.innerHTML = html;
}

function renderValTrading() {
  const industries = TOP_INDUSTRIES.map(i => i.name);
  let html = `<div class="page-title">Trading Multiple <span class="crumb">/ Valuation · Equity</span></div>
    <select class="industry-select" id="ind-sel">
      ${industries.map(n => `<option>${n}</option>`).join("")}
    </select>
    <div class="metric-row">
      <div class="metric-card"><div class="label">PBR</div><div class="value">1.45x</div><div class="sub">2026-04 평균</div></div>
      <div class="metric-card"><div class="label">P/E</div><div class="value">12.8x</div><div class="sub">Forward 12M</div></div>
      <div class="metric-card"><div class="label">EV/EBITDA</div><div class="value">8.3x</div><div class="sub">2026E</div></div>
    </div>
    <div class="compare-card">
      <h4>전체 산업 평균 (KOSPI+KOSDAQ)</h4>
      <div class="row head"><span>지표</span><span class="num">평균</span><span class="num">중앙값</span><span class="num">상위25%</span></div>
      <div class="row"><span>PBR</span><span class="num">1.12x</span><span class="num">0.95x</span><span class="num">1.78x</span></div>
      <div class="row"><span>P/E</span><span class="num">14.2x</span><span class="num">11.5x</span><span class="num">22.4x</span></div>
      <div class="row"><span>EV/EBITDA</span><span class="num">9.6x</span><span class="num">7.8x</span><span class="num">14.1x</span></div>
    </div>`;
  $main.innerHTML = html;
}

function renderValIncome() {
  let html = `<div class="page-title">Income Approach <span class="crumb">/ Valuation · Equity</span></div>
    <div class="income-block">
      <h3>대상 기업: 삼성전자 (예시)</h3>
      <div class="assumption">
        <label>매출 성장률 (CAGR)</label>
        <input type="range" min="-10" max="20" value="5" id="a-growth">
        <span class="val" id="v-growth">5.0%</span>
      </div>
      <div class="assumption">
        <label>EBITDA 마진</label>
        <input type="range" min="5" max="40" value="25" id="a-margin">
        <span class="val" id="v-margin">25%</span>
      </div>
      <div class="assumption">
        <label>WACC (할인율)</label>
        <input type="range" min="5" max="15" step="0.5" value="9" id="a-wacc">
        <span class="val" id="v-wacc">9.0%</span>
      </div>
      <div class="assumption">
        <label>영구성장률 (g)</label>
        <input type="range" min="0" max="5" step="0.5" value="2" id="a-tg">
        <span class="val" id="v-tg">2.0%</span>
      </div>
    </div>
    <div class="result-card">
      <div class="label">DCF 추정 기업가치 (Enterprise Value)</div>
      <div class="value" id="dcf-result">580조원</div>
      <div class="sub" id="dcf-per-share">주당 적정가치: 70,500원</div>
    </div>
    <div style="font-size:10px; color: var(--text-3); text-align:center; margin-top:10px;">
      ※ 예시 dummy 모델 — 실제 가치산정에는 추가 가정 필요
    </div>`;
  $main.innerHTML = html;
  bindIncomeAssumptions();
}

function bindIncomeAssumptions() {
  const ids = ["growth", "margin", "wacc", "tg"];
  function recompute() {
    const g = parseFloat(document.getElementById("a-growth").value) / 100;
    const m = parseFloat(document.getElementById("a-margin").value) / 100;
    const w = parseFloat(document.getElementById("a-wacc").value) / 100;
    const t = parseFloat(document.getElementById("a-tg").value) / 100;
    document.getElementById("v-growth").textContent = (g*100).toFixed(1) + "%";
    document.getElementById("v-margin").textContent = (m*100).toFixed(0) + "%";
    document.getElementById("v-wacc").textContent   = (w*100).toFixed(1) + "%";
    document.getElementById("v-tg").textContent     = (t*100).toFixed(1) + "%";
    // 단순 더미 모델: EV = (매출×마진×(1+g)) / (WACC - g)
    const baseRev = 300;  // 조원
    const ebitda5 = baseRev * Math.pow(1+g, 5) * m;
    const tv = (ebitda5 * (1+t)) / Math.max(w - t, 0.01);
    const ev = tv * 0.7 + ebitda5 * 5 * 0.3;
    document.getElementById("dcf-result").textContent = ev.toFixed(0) + "조원";
    const perShare = (ev * 10000 / 5970).toFixed(0);
    document.getElementById("dcf-per-share").textContent =
      `주당 적정가치: ${Number(perShare).toLocaleString()}원`;
  }
  ids.forEach(k => document.getElementById("a-"+k).addEventListener("input", recompute));
  recompute();
}

function renderMezzanine(kind) {
  const labels = { rcps: "RCPS (전환상환우선주)", bw: "BW (신주인수권부사채)", cb: "CB (전환사채)" };
  const sample = [
    { corp: "에코프로비엠", amt: "1,500억", rate: "1.5%", strike: "180,000원", maturity: "2029-03", status: "정상", cls: "green" },
    { corp: "셀트리온헬스케어", amt: "800억", rate: "0%",  strike: "78,500원", maturity: "2028-06", status: "정상", cls: "green" },
    { corp: "카카오게임즈",     amt: "500억", rate: "2.0%", strike: "32,000원", maturity: "2027-12", status: "전환완료", cls: "gray" },
    { corp: "네이버Z",          amt: "300억", rate: "1.0%", strike: "55,000원", maturity: "2030-01", status: "주가하회", cls: "red" },
  ];
  let html = `<div class="page-title">${labels[kind]} <span class="crumb">/ Valuation · Mezzanine</span></div>
    <div style="font-size:11px; color:var(--text-3); margin-bottom:10px;">
      ※ 최근 1년 발행된 ${kind.toUpperCase()} 중 주요 종목 (예시)
    </div>`;
  for (const m of sample) {
    html += `<div class="mezz-card">
      <div class="top-row">
        <span class="corp">${m.corp}</span>
        <span class="badge ${m.cls}">${m.status}</span>
      </div>
      <div class="meta">
        <div>발행규모: <b>${m.amt}</b></div>
        <div>표면이자율: <b>${m.rate}</b></div>
        <div>전환가: <b>${m.strike}</b></div>
        <div>만기: <b>${m.maturity}</b></div>
      </div>
    </div>`;
  }
  $main.innerHTML = html;
}

function chartSVG(points, color) {
  const w = 100, h = 100;
  const min = Math.min(...points), max = Math.max(...points);
  const range = max - min || 1;
  const pts = points.map((v, i) => {
    const x = (i / (points.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 10) - 5;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5"/>
    <polyline points="0,${h} ${pts} ${w},${h}" fill="${color}" fill-opacity="0.1" stroke="none"/>
  </svg>`;
}

function renderMacro(kind) {
  const cfg = {
    prime:     { title: "Prime Rate (기준금리)",   unit: "%", colors: ["#2C7BE5", "#E53935", "#38A169", "#F59E0B"] },
    bond:      { title: "10Y Government Bond",     unit: "%", colors: ["#1E88E5", "#C53030", "#2E9E5C", "#D97706"] },
    inflation: { title: "Inflation (CPI YoY)",     unit: "%", colors: ["#3B82F6", "#EF4444", "#10B981", "#F59E0B"] },
    unemp:     { title: "Unemployment Rate",       unit: "%", colors: ["#2C7BE5", "#E53935", "#38A169", "#F59E0B"] },
  };
  const seedSet = {
    prime:     { Korea:[3.5,3.5,3.5,3.25,3.0,3.0], US:[5.5,5.5,5.25,5.0,4.75,4.5], Japan:[0.5,0.5,0.5,0.5,0.5,0.5], China:[3.45,3.45,3.45,3.45,3.35,3.35] },
    bond:      { Korea:[3.4,3.5,3.6,3.5,3.45,3.4], US:[4.3,4.4,4.5,4.6,4.5,4.4], Japan:[1.0,1.05,1.1,1.15,1.2,1.18], China:[2.4,2.42,2.45,2.4,2.38,2.35] },
    inflation: { Korea:[2.4,2.5,2.3,2.2,2.1,2.0], US:[3.1,3.0,2.9,2.8,2.7,2.6], Japan:[2.2,2.0,1.9,1.8,1.8,1.7], China:[0.5,0.4,0.3,0.5,0.6,0.7] },
    unemp:     { Korea:[3.0,3.1,3.2,3.0,2.9,2.8], US:[3.7,3.8,3.9,4.0,4.0,4.1], Japan:[2.5,2.5,2.6,2.5,2.5,2.4], China:[5.0,5.1,5.2,5.1,5.0,4.9] },
  };
  const C = cfg[kind];
  const series = seedSet[kind];
  const countries = [
    { code:"Korea",  flag:"🇰🇷", name:"South Korea" },
    { code:"US",     flag:"🇺🇸", name:"United States" },
    { code:"Japan",  flag:"🇯🇵", name:"Japan" },
    { code:"China",  flag:"🇨🇳", name:"China" },
  ];
  let html = `<div class="page-title">${C.title} <span class="crumb">/ Macro Eco</span></div>`;
  countries.forEach((c, i) => {
    const data = series[c.code];
    const last = data[data.length-1];
    const prev = data[data.length-2];
    const chg = (last - prev).toFixed(2);
    html += `<div class="country-card">
      <h3>${c.flag} ${c.name}</h3>
      <div class="sub">최근 6개월 추이</div>
      <div class="chart-box">${chartSVG(data, C.colors[i])}</div>
      <div class="macro-stat"><span class="lbl">현재</span><span class="val">${last}${C.unit}</span></div>
      <div class="macro-stat"><span class="lbl">전월 대비</span><span class="val">${chg >= 0 ? "+" : ""}${chg}${C.unit}</span></div>
      <div class="macro-stat"><span class="lbl">최근 6개월 평균</span><span class="val">${(data.reduce((a,b)=>a+b,0)/data.length).toFixed(2)}${C.unit}</span></div>
    </div>`;
  });
  $main.innerHTML = html;
}

function renderNews(source) {
  const sources = {
    thebell: {
      title: "TheBell",
      url: "https://www.thebell.co.kr",
      items: [
        "측근 요직 배치…수평적 조직구조에 컨트롤 타워 부족",
        "한화에어로, 美 방산수출 확대 본격화",
        "삼성SDI, 차세대 4680 배터리 양산 일정 공개",
        "현대차 미국 공장, 트럼프 관세에 대비 가속",
        "SK하이닉스, HBM4 공급 계약 5건 추가 체결",
        "셀트리온, 美 FDA 신청 4종 동시 진행",
        "두산로보틱스, 유럽 자회사 추가 인수 검토",
      ],
    },
    naver: {
      title: "네이버파이넨셜",
      url: "https://finance.naver.com",
      items: [
        "코스피 2,750p 회복…외국인 8거래일 연속 순매수",
        "원/달러 환율 1,350원대 안착…수출주 주목",
        "건설주 약세 지속…부동산 PF 우려 재부각",
        "이차전지 대장주 일제히 반등…리튬 가격 상승",
        "반도체 장비주 강세…AI 인프라 투자 확대",
        "방산주 사상 최고가 행진…수주 모멘텀 지속",
        "조선주 호실적 발표…2분기 흑자 전환 가시화",
      ],
    },
  };
  const s = sources[source];
  let html = `<div class="page-title">${s.title} <span class="crumb">/ News</span></div>
    <div class="news-source">
      <h2>${s.title}</h2>`;
  s.items.forEach((it, i) => {
    html += `<a class="news-item" href="${s.url}" target="_blank">
      <span class="num">${(i+1).toString().padStart(2,"0")}.</span>${it}
    </a>`;
  });
  html += `</div>
    <div style="font-size:10px; color: var(--text-3); text-align:center;">
      각 기사를 클릭하면 ${s.title} 사이트로 이동합니다.
    </div>`;
  $main.innerHTML = html;
}

// ============== Router ==============
const $gnb = document.getElementById("gnb");

function closeDropdown() {
  // CSS hover와 충돌하지 않게 강제 닫기 클래스 사용
  // 마우스가 gnb 영역을 벗어나면 자동 해제
  if ($gnb) $gnb.classList.add("force-close");
}

if ($gnb) {
  $gnb.addEventListener("mouseleave", () => {
    $gnb.classList.remove("force-close");
  });
}

function navigate(pageId, opts = {}) {
  // opts.replace = true → pushState 대신 replaceState (히스토리 누적 안 함)
  // opts.fromPopState = true → popstate 이벤트로 호출됨 (URL 갱신 스킵)
  currentPage = pageId;
  closeDropdown();

  // top-nav active
  $navBtns.forEach(b => b.classList.remove("active"));
  const meta = pageOf(pageId);
  if (meta) {
    document.querySelector(`.nav-btn[data-tab="${meta.tab}"]`).classList.add("active");
    renderSidebar(meta.tab);
  } else {
    renderSidebar(null);
  }

  // render main
  const renderers = {
    "home": renderHome,
    "market-cap": renderMarketCap,
    "market-change": renderMarketChange,
    "market-revenue":  () => renderFinancial("revenue"),
    "market-opincome": () => renderFinancial("opincome"),
    "val-trading": renderValTrading,
    "val-income":  renderValIncome,
    "val-rcps": () => renderMezzanine("rcps"),
    "val-bw":   () => renderMezzanine("bw"),
    "val-cb":   () => renderMezzanine("cb"),
    "macro-prime":     () => renderMacro("prime"),
    "macro-bond":      () => renderMacro("bond"),
    "macro-inflation": () => renderMacro("inflation"),
    "macro-unemp":     () => renderMacro("unemp"),
    "news-thebell": () => renderNews("thebell"),
    "news-naver":   () => renderNews("naver"),
  };
  (renderers[pageId] || renderHome)();
  $main.scrollTop = 0;

  // URL 갱신 (popstate에서 호출된 경우 제외)
  if (!opts.fromPopState) {
    const url = urlForPage(pageId);
    if (location.pathname !== url) {
      if (opts.replace) history.replaceState({ pageId }, "", url);
      else              history.pushState({ pageId }, "", url);
    }
  }

  // 브라우저 탭 타이틀
  document.title = PAGE_TITLES[pageId] || "FinVisual";
}

// 브라우저 뒤로/앞으로 버튼
window.addEventListener("popstate", e => {
  const pageId = (e.state && e.state.pageId) || pageForUrl(location.pathname);
  navigate(pageId, { fromPopState: true });
});

// ============== Mega Dropdown (CSS-driven) ==============
// 열림/닫힘은 CSS .gnb:hover가 처리. JS는 컨텐츠 빌드 + 클릭 네비게이션만 담당.

function buildMegaDropdown() {
  let html = `<div class="mega-spacer"></div>`;
  for (const tabKey of Object.keys(NAV)) {
    const tab = NAV[tabKey];
    html += `<div class="mega-col">`;
    for (const g of tab.groups) {
      html += `<h4>${g.name}</h4>`;
      for (const it of g.items) {
        html += `<a data-page="${it.id}">${it.label}</a>`;
      }
    }
    html += `</div>`;
  }
  $dropdown.innerHTML = html;
  $dropdown.querySelectorAll("a[data-page]").forEach(el => {
    el.addEventListener("click", () => {
      navigate(el.dataset.page);
      // 클릭 후 hover 해제 효과 — 강제 blur로 자연스럽게 닫힘
      document.activeElement && document.activeElement.blur();
    });
  });
}

// 상단 버튼 클릭 → 해당 분류의 첫 페이지로 이동
$navBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    const firstItem = NAV[tab].groups[0].items[0];
    navigate(firstItem.id);
  });
});

// 초기 빌드
buildMegaDropdown();

// 로고 클릭 → 홈
document.querySelector(".logo").addEventListener("click", () => navigate("home"));
document.querySelector(".logo").style.cursor = "pointer";

// ============== Init: URL 기반 진입 ==============
const initialPage = pageForUrl(location.pathname);
navigate(initialPage, { replace: true });   // 초기 진입은 히스토리 누적 안 함
