/**
 * FinVisual Market Worker
 *
 * 역할:
 *   1) 5분마다 (Cron) 네이버 금융 모바일 API에서 KOSPI/KOSDAQ 전 종목 시가총액·등락률 수집
 *   2) Cloudflare KV에 JSON으로 저장 (binding: MARKET_KV)
 *   3) /api/snapshot 엔드포인트로 프론트엔드에 전달
 *
 * 엔드포인트:
 *   GET /api/snapshot   - 최신 스냅샷 반환
 *   GET /api/refresh    - 수동 갱신 트리거 (관리자용)
 *   GET /api/health     - 상태 확인
 */

export default {
  // ====== Cron Trigger ======
  async scheduled(event, env, ctx) {
    ctx.waitUntil(refreshSnapshot(env));
  },

  // ====== HTTP Endpoint ======
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }

    if (url.pathname === "/api/snapshot") {
      const data = await env.MARKET_KV.get("latest", "json");
      if (!data) {
        // 첫 호출: KV 비어있으면 즉시 갱신
        await refreshSnapshot(env);
        const fresh = await env.MARKET_KV.get("latest", "json");
        return jsonResponse(fresh || { error: "no data" }, cors);
      }
      return jsonResponse(data, cors);
    }

    if (url.pathname === "/api/refresh") {
      ctx.waitUntil(refreshSnapshot(env));
      return jsonResponse({ status: "refresh triggered" }, cors);
    }

    // ====== Memo board (개발 아이디어 보드, 인증 없음) ======
    // 저장: KV 키 "memos" 에 JSON 배열. 모든 기기가 같은 데이터를 읽고 씀.
    if (url.pathname === "/api/memos" || url.pathname.startsWith("/api/memos/")) {
      return handleMemos(request, url, env, cors);
    }

    if (url.pathname === "/api/health") {
      const meta = await env.MARKET_KV.get("latest", "json");
      return jsonResponse({
        ok: true,
        last_update: meta?.timestamp ?? null,
        item_count: meta?.count ?? 0,
      }, cors);
    }

    return new Response(
      "FinVisual Market Worker\n" +
      "Endpoints: /api/snapshot, /api/refresh, /api/health",
      { status: 200, headers: { "content-type": "text/plain" } }
    );
  },
};

function jsonResponse(obj, headers = {}) {
  return new Response(JSON.stringify(obj), {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8", ...headers },
  });
}

// ====== Memo board CRUD (KV 키 "memos") ======
async function handleMemos(request, url, env, cors) {
  const MEMO_KEY = "memos";
  const j = (obj, status = 200) => new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...cors },
  });

  const list = (await env.MARKET_KV.get(MEMO_KEY, "json")) || [];

  // 컬렉션: /api/memos
  if (url.pathname === "/api/memos") {
    if (request.method === "GET") return j({ items: list });
    if (request.method === "POST") {
      let body = {};
      try { body = await request.json(); } catch (e) {}
      const item = {
        id: crypto.randomUUID(),
        date: new Date().toISOString(),
        title: String(body.title || "").slice(0, 200),
        body: String(body.body || "").slice(0, 20000),
        status: "open",
      };
      list.push(item);
      await env.MARKET_KV.put(MEMO_KEY, JSON.stringify(list));
      return j(item, 201);
    }
    return j({ error: "method not allowed" }, 405);
  }

  // 개별 항목: /api/memos/{id}
  const id = decodeURIComponent(url.pathname.slice("/api/memos/".length));
  const idx = list.findIndex(m => m.id === id);
  if (idx === -1) return j({ error: "not found" }, 404);

  if (request.method === "PUT") {
    let body = {};
    try { body = await request.json(); } catch (e) {}
    const m = list[idx];
    if (typeof body.title === "string") m.title = body.title.slice(0, 200);
    if (typeof body.body === "string")  m.body  = body.body.slice(0, 20000);
    if (body.status === "open" || body.status === "done") m.status = body.status;
    await env.MARKET_KV.put(MEMO_KEY, JSON.stringify(list));
    return j(m);
  }
  if (request.method === "DELETE") {
    list.splice(idx, 1);
    await env.MARKET_KV.put(MEMO_KEY, JSON.stringify(list));
    return j({ ok: true });
  }
  return j({ error: "method not allowed" }, 405);
}

// ====== Naver 금융 모바일 API 호출 ======
async function refreshSnapshot(env) {
  const items = [];
  for (const market of ["KOSPI", "KOSDAQ"]) {
    const market_items = await fetchMarket(market);
    items.push(...market_items);
  }

  const snapshot = {
    timestamp: Date.now(),
    iso: new Date().toISOString(),
    count: items.length,
    items: items,
  };

  await env.MARKET_KV.put("latest", JSON.stringify(snapshot));

  // 디버그용 로그 (Workers Tail에서 확인)
  console.log(`[refresh] ${market_count(items)} items @ ${snapshot.iso}`);
  return snapshot;
}

function market_count(items) {
  const c = {};
  for (const it of items) c[it.market] = (c[it.market] || 0) + 1;
  return JSON.stringify(c);
}

async function fetchMarket(market) {
  // m.stock.naver.com 모바일 API: 페이지당 100종목, 35페이지면 3500종목 커버
  const headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://m.stock.naver.com/",
  };

  const out = [];
  for (let page = 1; page <= 40; page++) {
    const url = `https://m.stock.naver.com/api/stocks/marketValue/${market}?page=${page}&pageSize=100`;
    let json;
    try {
      const res = await fetch(url, { headers });
      if (!res.ok) break;
      json = await res.json();
    } catch (e) {
      console.log(`[fetch error] ${market} page ${page}: ${e.message}`);
      break;
    }

    // 응답 형태가 케이스별로 약간 다름: stocks / marketCap / list 등 시도
    const stocks = json?.stocks || json?.marketCap || json?.list || [];
    if (!Array.isArray(stocks) || stocks.length === 0) break;

    for (const s of stocks) {
      const code = String(s.itemCode || s.code || "").trim();
      if (!code || code.length < 6) continue;

      // 가격 파싱 (네이버는 "1,234,567" 같은 콤마 포함 문자열 가능)
      const priceRaw = s.closePrice ?? s.tradePrice ?? s.now ?? "0";
      const mcapRaw  = s.marketValue ?? s.marketCap ?? "0";
      const chgRaw   = s.fluctuationsRatio ?? s.changeRate ?? s.rate ?? "0";

      const price = parseFloat(String(priceRaw).replace(/,/g, "")) || 0;
      const mcap  = parseFloat(String(mcapRaw).replace(/,/g, ""))  || 0;
      const chg   = parseFloat(String(chgRaw).replace(/[+%]/g, "")) || 0;

      out.push({
        code: code.padStart(6, "0"),
        name: s.stockName || s.name || "",
        market: market,
        price: price,
        mcap: mcap,                 // 단위: 억원 (네이버 marketValue)
        change: chg,                // 등락률 %
      });
    }

    // 페이지 끝 감지: 100개 미만이면 마지막
    if (stocks.length < 100) break;
  }
  return out;
}
