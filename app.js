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

function renderMarketCap() {
  let html = `<div class="page-title">시가총액 <span class="crumb">/ Market · Equity</span></div>`;
  for (const ind of TOP_INDUSTRIES) {
    html += `<div class="industry-card">
      <div class="ic-head">
        <span class="name">${ind.name}</span>
        <span class="total">${ind.total}원 ${fmtPct(ind.delta)}</span>
      </div>
      <div class="company-grid">`;
    for (const c of ind.companies) {
      const cls = c.pct >= 0 ? "up" : "down";
      html += `<div class="co-tile ${cls}">
        <div class="co-name">${c.name}</div>
        <div class="co-cap">${c.cap}원</div>
        <div class="co-pct">${fmtPct(c.pct)}</div>
      </div>`;
    }
    html += `</div>`;
    if (ind.rise.length) {
      html += `<div class="short-rise">
        <div class="short-rise-title">단기상승 주식</div>
        <div style="font-size:10px; color: var(--text-2);">${ind.rise.join(" · ")}</div>
      </div>`;
    }
    html += `</div>`;
  }
  $main.innerHTML = html;
}

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
