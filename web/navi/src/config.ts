/**
 * config.ts — 바깥에서 주입되는 값 한 자리.
 *
 * ★ **토큰을 저장소에 넣지 마라.** 빌드 시 주입한다.
 *
 *     저장소 루트 .env           MAPBOX_TOKEN=pk....        (.gitignore · 정본)
 *     web/navi/.env.local        VITE_MAPBOX_TOKEN=pk....   (옛 자리 · 호환)
 *     배포                       ${{ secrets.MAPBOX_TOKEN }}
 *   고르는 순서는 vite.config.ts `mapboxToken()` 이 든다.
 *
 *   2026-09-05 에 Map Matching 대조로 1,301 회를 썼다. 무료 한도가 월
 *   10만이라 여유는 있으나, 개발 중 리로드마다 매칭하면 하루 수천 건이
 *   나간다. **누구 토큰으로 나가는지가 곧 누가 요금을 내는지다** —
 *   그래서 소유자가 바뀌면 환경변수 하나만 갈아끼우게 둔다.
 *
 * ★ 토큰이 없어도 앱은 돈다. `MATCHING_ENABLED` 가 false 면 음성 안내를
 *   전부 자체 문구로 낸다. **남는 사람이 토큰 없이 개발할 수 있어야 한다.**
 */

export const MAPBOX_TOKEN: string =
  (import.meta as { env?: Record<string, string> }).env?.VITE_MAPBOX_TOKEN ?? "";

export const MATCHING_ENABLED = MAPBOX_TOKEN.startsWith("pk.");

/**
 * 중개자 주소. **이것이 있으면 관제와 내비가 다른 기계에서도 이어진다.**
 * (DECISIONS §343 · `infra/opsLink.ts`)
 *
 *     저장소 루트 .env       FIRE_LANE_OPS_URL=wss://xxxx.cloudfront.net
 *     web/navi/.env.local    VITE_OPS_URL=ws://127.0.0.1:8000
 *     배포                   ${{ vars.FIRE_LANE_OPS_URL }}
 *   고르는 순서는 vite.config.ts `opsUrl()` 이 든다.
 *
 * ★ **비어 있으면 앱이 그대로 돈다.** 전송이 `BroadcastChannel` 로 떨어지고,
 *   그것은 같은 브라우저의 탭끼리만 닿는다 — 지금까지의 동작 그대로다.
 *   서버가 없다고 내비가 멈추면 안 된다.
 *
 * ★ **토큰이 아니다.** 주소이고, 공개돼도 손해가 없다 — 그래서 secrets 가
 *   아니라 vars 다. 중개자에 인증이 붙는 날 그 값은 secrets 로 간다.
 */
export const OPS_URL: string =
  (import.meta as { env?: Record<string, string> }).env?.VITE_OPS_URL ?? "";

/**
 * 주행 속도 가정(m/s).
 *
 * ★ **미검증이다.** 소방차 골목 주행 속도를 잰 적이 없다. 도착 예정
 *   시각과 "빠른 경로보다 N초" 가 전부 이 값에 매달린다. 화면이
 *   "예상" 이라고 말하는 이유이며 D-30 인터뷰 항목이다.
 */
export const ASSUMED_SPEED_MPS = 8.3;   // 약 30km/h

/** 도로에서 이만큼 넘게 떨어지면 스코프 밖으로 본다(m). */
export const SCOPE_M = 60;

/** 스냅 주기(ms). 2.2ms 브루트포스라 매 프레임 돌릴 이유가 없다. */
export const SNAP_INTERVAL_MS = 200;
