#!/usr/bin/env bash
# ops-worker/scripts/deploy.sh — 중개자를 Cloudflare 에 올린다. **사람이 친다**(계정 로그인 · 비밀 입력이 든다). DECISIONS §755 · PLAN #176
#
#   cd ops-worker && npm ci && bash scripts/deploy.sh
#
# 하는 일: ① 로그인 확인(없으면 `wrangler login` 이 브라우저를 연다) ② 토큰(`FIRE_LANE_OPS_TOKEN`)을 Worker 비밀로 넣는다 ③ 배포 ④ 주소 · 다음에 칠 명령을 찍는다.
# 안 하는 일: GitHub Variables/Secrets 를 건드리지 않는다(마지막에 명령만 찍는다) — 밖으로 나가는 일은 사람이 친다.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d node_modules ] || { echo "✗ node_modules 가 없다 — 먼저 \`npm ci\`" >&2; exit 1; }

echo "① Cloudflare 로그인 확인"
npx wrangler whoami >/dev/null 2>&1 || npx wrangler login

echo "② 토큰 — 저장소 Secrets 의 FIRE_LANE_OPS_TOKEN 과 **같은 값**을 넣는다(빌드가 번들에 박는 그 값)"
if [ -n "${FIRE_LANE_OPS_TOKEN:-}" ]; then
  printf '%s' "$FIRE_LANE_OPS_TOKEN" | npx wrangler secret put FIRE_LANE_OPS_TOKEN
else
  echo "  (환경변수 FIRE_LANE_OPS_TOKEN 이 없다 — 지금 입력하면 된다. 새로 만들려면: openssl rand -hex 24)"
  npx wrangler secret put FIRE_LANE_OPS_TOKEN
fi

echo "③ 배포"
npx wrangler deploy

cat <<'MSG'

④ 다음에 칠 것 (밖으로 나가는 일이라 이 스크립트가 안 친다)
   · 위 「https://fire-lane-ops.….workers.dev」 를 wss 로 바꾼 주소를 저장소 Variables 에:
       gh variable set FIRE_LANE_OPS_URL --body "wss://fire-lane-ops.<서브도메인>.workers.dev"
   · 같은 토큰을 저장소 Secrets 에(이미 넣었다면 건너뛴다):
       gh secret set FIRE_LANE_OPS_TOKEN
   · 확인(주소는 위와 같다):
       curl https://fire-lane-ops.<서브도메인>.workers.dev/health          # {"ok":true}
       curl "https://fire-lane-ops.<서브도메인>.workers.dev/units?t=<토큰>"  # {"room":"fire-lane","ops":false,"units":[]}
   · ★ PLAN #176 의 전건: 시연 표시(`?demo=1` 내비 + 관제)를 **사람이 눈으로 본 뒤에** 앱을 다시 배포한다(PLAN #176).
MSG
