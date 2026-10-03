/**
 * config.ts — 바깥에서 주입되는 값 한 자리.
 *
 * ★ **토큰을 저장소에 넣지 마라.** 빌드 시 주입한다.
 *
 * ── ★ 2026-10-03 — Mapbox 토큰을 걷었다 (DECISIONS §366-2) ──────
 * 종전에 이 자리가 `MAPBOX_TOKEN` · `MATCHING_ENABLED` 둘을 들었고, 그
 * 사유를 길게 적었다 — 「토큰이 없어도 앱은 돈다. `MATCHING_ENABLED` 가
 * false 면 음성 안내를 전부 자체 문구로 낸다」.
 *
 * **그 둘을 읽는 파일이 하나였고 그 파일을 아무도 import 하지 않았다**
 * (`infra/matching.ts` 90줄). 즉 Map Matching 은 **번들에 실린 적이 없다** —
 * 상용 정합을 안 쓰기로 한 판단(`domain/snap.ts` 머리말 · 브루트포스 2.2ms)
 * 뒤로 코드만 남은 것이다. 그래서 「없어도 돈다」가 아니라 **늘 없었다.**
 *
 * 끌고 있던 것 둘을 같이 걷었다 — `naviweight.ALLOWED` 의 바깥 의존
 * `api.mapbox.com`(래칫 1 → 0)과 `build-navi` 액션의 **배포 전건**(토큰
 * 시크릿이 없으면 배포가 죽었다). 대조 능력은 안 잃는다 —
 * `tools/matchcheck.py` 가 루트 `.env` 의 토큰으로 그대로 든다.
 */

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
