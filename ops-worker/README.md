# ops-worker — 관제 ↔ 내비 중개자 (Cloudflare Workers)

`src/firelane/ops/server.py`(FastAPI)와 **같은 표면**을 Cloudflare Workers + Durable Object 로 옮긴 것이다(DECISIONS §755 · PLAN #176). 규칙은 `src/relay.ts` 한 곳이고 파이썬 `roster.py` 와 같은 표를 쓴다(`tests/test_ops_roster.py` 가 상수를 맞춰 문다).

- WebSocket `/ops` · `/unit/{id}` · `/cv/{cam}` · HTTP `GET /health`(토큰 없이) · `GET /units`(토큰). 토큰은 질의 `t`, `accept` 전에 본다.
- **메시지의 뜻을 안 본다**(§342). 「마지막 한 통을 기억한다」 — 차량 · 영상 버킷의 마지막 글자를 **그대로** 들고 새로 붙은 쪽에 재생한다. 관제의 `hb` · `ack` 는 안 기억한다.
- 방 하나(`fire-lane`) · 저장소 없음 · 연결이 곧 명부다.

## 로컬에서 (계정 없이)

```bash
cd ops-worker
npm ci
printf 'FIRE_LANE_OPS_TOKEN=devtoken-local\n' > .dev.vars      # 커밋 안 됨
npx wrangler dev --local --port 8787                           # → http://localhost:8787
npm test                                                       # 순수 규칙(node --test)
```
화면을 붙이려면 다른 터미널에서 `cd web/navi && VITE_OPS_URL=ws://127.0.0.1:8787 VITE_OPS_TOKEN=devtoken-local npm run dev`. 관제(`?view=ops`)와 내비(`?demo=1&…`)를 **다른 브라우저 프로필**에서 열어도 이어진다.

## 배포 (사람이 친다 — Cloudflare 계정이 든다)

```bash
cd ops-worker
npm ci
bash scripts/deploy.sh            # 로그인 → 토큰을 Worker 비밀로 → wrangler deploy → 다음 명령을 찍는다
```
그다음 스크립트가 찍는 두 줄(`gh variable set FIRE_LANE_OPS_URL …` · `gh secret set FIRE_LANE_OPS_TOKEN`)을 치고 앱을 다시 배포한다. **토큰 값은 Worker 비밀 · GitHub Secrets 두 곳이 같아야 한다.** 틀리면 화면은 멀쩡하고 연결만 조용히 안 된다.

> ★ **PLAN #176 의 전건: 시연 표시를 사람이 눈으로 본 뒤에 띄운다.** 중개자가 서면 시연 차량이 관제의 「출동 중」 에 실제와 섞인다 — 메시지가 `demo` 를 싣고 관제가 호박색 `시연 중` 으로 가르게 했다(§745). 두 화면에서 `?demo=1` 로 한 번 보고 띄운다.

## 알려진 한계

- **마지막 한 통은 메모리에만 있다.** Hibernation 으로 DO 가 쫓겨나면 사라진다. 내비의 `state` 는 0.5초마다 다시 오니 차량 버킷은 0.5초 안에 복구되지만, 영상(`cv`)은 주기 신호가 아니라 복구가 안 된다.
- **무료 한도**(§738 · 2026-11-13 공식 문서 기준): 하루 요청 10만(WebSocket 들어오는 메시지는 20:1) · 지속시간 13,000 GB-s. 0.5초마다 메시지가 오면 DO 가 hibernation 에 못 들어가 **하루 종일 켜 두면 지속시간이 먼저 닿는다**(128MB 가정 약 10,800 GB-s).
- 토큰은 신분이 아니다 — 누가 보냈는지 모른다. `ALLOWED_ORIGINS`(쉼표, `wrangler.toml` 의 `[vars]`)를 주면 그 출처의 WebSocket 만 받는다.
