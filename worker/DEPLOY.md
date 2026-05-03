# FinVisual Market Worker 배포 가이드

Cloudflare Worker로 네이버 금융 시가총액·등락률을 5분마다 폴링하여 KV에 저장하고, 프론트엔드(`fin-visual.com`)에 `/api/snapshot`으로 제공합니다.

---

## 1. wrangler CLI 설치

PowerShell에서:

```bash
npm install -g wrangler
wrangler --version    # 3.x 이상 확인
wrangler login        # Cloudflare 계정 로그인 (브라우저 열림)
```

Node.js가 없다면 [nodejs.org](https://nodejs.org)에서 LTS 버전 먼저 설치.

---

## 2. KV namespace 생성

```bash
cd "C:\Users\gmyhs\OneDrive\Desktop\MYSITE\Github\worker"

# 운영용
wrangler kv:namespace create MARKET_KV

# 미리보기용 (개발 환경)
wrangler kv:namespace create MARKET_KV --preview
```

각 명령이 출력하는 `id` 값을 복사:

```
✨ Success! Add the following to your wrangler.toml:
[[kv_namespaces]]
binding = "MARKET_KV"
id = "abc123def456..."          ← 이 값
```

---

## 3. wrangler.toml에 KV ID 입력

`worker/wrangler.toml` 파일 열어서 `PUT_YOUR_KV_NAMESPACE_ID_HERE` 부분을 위에서 받은 ID로 교체:

```toml
[[kv_namespaces]]
binding = "MARKET_KV"
id = "abc123def456..."           # 운영 KV ID
preview_id = "xyz789..."         # 미리보기 KV ID
```

---

## 4. Worker 배포

```bash
wrangler deploy
```

성공하면 다음과 같은 URL이 출력됨:

```
https://finvisual-market.<account>.workers.dev
```

이 URL을 메모해두세요. 첫 번째 (수동) 갱신 트리거:

```bash
curl https://finvisual-market.<account>.workers.dev/api/refresh
```

5초 정도 기다린 후 데이터 확인:

```bash
curl https://finvisual-market.<account>.workers.dev/api/snapshot
```

---

## 5. 프론트엔드와 연결

`Github/app.js` 상단의 `WORKER_API` 상수를 본인 Worker URL로 변경:

```javascript
const WORKER_API = "https://finvisual-market.<account>.workers.dev/api/snapshot";
```

`<account>` 부분을 본인 Cloudflare 계정 슬러그로 교체.

(선택) 커스텀 도메인 사용하려면 Cloudflare 대시보드에서 Worker → Triggers → Custom Domain 으로 `api.fin-visual.com` 같은 서브도메인 연결 가능.

---

## 6. Cron Trigger 자동 실행 확인

`wrangler.toml`의 `crons = ["*/5 * * * *"]` 가 매 5분마다 자동 실행됩니다.

Cloudflare 대시보드에서 확인:
- Workers & Pages → finvisual-market → **Triggers** 탭 → Cron Triggers 섹션
- "Last status" 확인

또는 실시간 로그:

```bash
wrangler tail
```

---

## 7. 프론트엔드 배포

`Github` 폴더 git push 하면 Cloudflare Pages가 자동 배포:

```bash
cd "C:\Users\gmyhs\OneDrive\Desktop\MYSITE\Github"
git add .
git commit -m "treemap + worker 추가"
git push
```

---

## 트러블슈팅

### `/api/snapshot` 이 빈 데이터 반환
- Worker가 처음 배포된 직후엔 KV가 비어있음 → `/api/refresh` 한 번 호출하거나 5분 기다리기

### 네이버 API 응답 형식 다른 경우
- `worker.js` 의 `fetchMarket` 함수에서 `s.itemCode`, `s.marketValue` 등 필드명 매핑 확인
- `wrangler tail`로 로그 보면서 실제 응답 구조 확인 후 조정

### CORS 오류
- Worker 응답 헤더에 `Access-Control-Allow-Origin: *` 이미 설정됨
- 그래도 막히면 브라우저 콘솔에서 정확한 메시지 확인

### 프론트가 industry_mapping.json 못 찾음
- Cloudflare Pages는 `Github/data/industry_mapping.json` 을 `https://fin-visual.com/data/industry_mapping.json` 경로로 자동 서빙해야 정상
- Pages 빌드 로그에서 `data/` 폴더가 포함됐는지 확인
