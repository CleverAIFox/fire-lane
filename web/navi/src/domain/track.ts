/**
 * track.ts — **주행 중에 무엇을 믿을 것인가.**
 *
 * ── 왜 이 파일이 생겼나 (DECISIONS §336) ─────────────────────
 * `app/useNavigation.ts` 가 482줄이었고 그 안에 **정책 넷**이 React 상태와
 * 섞여 있었다. 정책은 물을 수 있어야 하는데, 물으려면 렌더러가 필요했다 —
 * `vitest` 환경이 `node` 라 훅을 돌릴 수가 없다.
 *
 * §329 가 `useVoice` 에서 같은 일을 했고 같은 방법을 쓴다 — **의존성을 늘리는
 * 대신 정책을 내린다.** 여기 내려온 넷은 전부 순수 함수이고, 넷 다 옮기기
 * 전에는 시험이 하나도 없었다.
 *
 *   ① 위치원 선택   단계 · 배속 · 경로 · 모드 넷으로 하나를 고른다
 *   ② 진행방향      heading 이 있으면 그것, 없으면 **움직인 만큼**에서 낸다
 *   ③ 정확도 보고   임계를 **넘나들 때만** 올린다
 *   ④ 구간 내 비율  경로 위 거리에서 「지금 구간의 몇 %」를 낸다
 *
 * IN    인자뿐 — 전역도 시계도 안 읽는다
 * OUT   값뿐
 * 밖    **무엇을 말할지는 안 정한다** — 그것은 `domain/voice.ts` 다.
 *       **어디에 있는지도 안 낸다** — 경로 위 추정은 `domain/locate.ts` 가 든다.
 *       여기가 드는 것은 「그 값을 받아서 무엇을 믿을 것인가」다.
 */
import { bearing, distM, type LngLat } from "./geo";
import type { Phase, PosMode } from "./types";

/**
 * ① 붙일 위치원.
 *
 *   none        아무것도 안 붙인다
 *   replay      GPS 흉내(1Hz · 잡음 · 음영). `gpsSim`
 *   simulation  경로 따라가기. 잡음 없음
 *   gps         실제 단말 GPS
 */
export type SourceKind = "none" | "replay" | "simulation" | "gps";

/**
 * ★ 주행 전(`loading` · `idle` · `picked` · `preview`)에는 **위치를 안 받는다.**
 *   출발지가 안전센터라 현위치가 쓰이지 않고, 받으면 「위치 없음」 알림만 뜬다
 *   (2026-09-21). `arrived` 도 마찬가지다 — 끝난 뒤에 따라다닐 이유가 없다.
 *
 * ★ 배속이 0 이면 시연이 아니다. 그때는 경로가 있어도 **실제 GPS** 다.
 */
export function chooseSource(a: {
  phase: Phase; simSpeed: number; hasPlan: boolean; posMode: PosMode;
}): SourceKind {
  if (a.phase !== "guiding") return "none";
  if (a.simSpeed > 0 && a.hasPlan) return a.posMode === "gpsSim" ? "replay" : "simulation";
  return "gps";
}

/**
 * ② 진행방향과, 그것을 잰 자리.
 *
 * ★ `heading` 이 오면 그대로 쓴다 — 단말이 잰 값이 우리가 두 점으로 낸 값보다
 *   낫다. 안 오면 **`minM` 이상 움직였을 때만** 새로 낸다. 서 있는 차의 GPS 는
 *   제자리에서 떨리고, 그 떨림으로 방위를 내면 **화살표가 팽이처럼 돈다.**
 *
 * ★ 첫 측위는 방위를 못 낸다(비교할 앞자리가 없다). `prev` 를 그대로 두고
 *   자리만 기억한다 — 0 으로 떨어뜨리면 북쪽을 보고 있다고 거짓말한다.
 */
export function nextBearing(
  prev: number,
  fix: { lon: number; lat: number; heading?: number | null },
  lastPos: LngLat | null,
  minM: number,
): { brg: number; lastPos: LngLat } {
  const here: LngLat = [fix.lon, fix.lat];
  if (fix.heading != null) return { brg: fix.heading, lastPos: here };
  if (lastPos && distM(lastPos, here) >= minM) {
    return { brg: bearing(lastPos, here), lastPos: here };
  }
  return { brg: prev, lastPos: lastPos ?? here };
}

/**
 * ③ 정확도를 화면에 올릴 때인가 — **임계를 넘나들 때만.**
 *
 * ★ 값 자체는 화면에 안 쓴다. 「12m 였다가 13m 가 됐다」는 운전자에게 아무것도
 *   아니고, 1Hz 로 갱신하면 그 숫자가 화면을 덮는다. 바뀌는 것은 **약한가
 *   아닌가** 하나뿐이다.
 *
 * ★ `null`(못 잼)은 제 갈래다. 「약함」도 「멀쩡함」도 아니다 — `null` 과
 *   `weakM` 아래를 같이 묶으면 **정확도를 못 재는 단말이 멀쩡한 것으로 뜬다.**
 */
export function weakCrossed(was: number | null, now: number | null, weakM: number): boolean {
  const side = (a: number | null) => (a == null ? null : a > weakM);
  return side(was) !== side(now);
}

/**
 * ④ 지금 구간을 얼마나 지났나(0..1).
 *
 * `lengths` 는 경로 각 구간의 길이, `edge` 는 지금 구간의 색인, `s` 는 경로
 * 처음부터 잰 거리다.
 *
 * ★ 0..1 로 **자른다.** 추정기가 구간 경계에서 조금 넘치는 값을 낼 수 있고,
 *   그대로 쓰면 진행률이 100% 를 넘거나 음수가 된다.
 * ★ 길이가 0 이거나 없는 구간은 1 로 본다 — 길이가 없는 구간 위에서 「몇 %」는
 *   뜻이 없고, 0 으로 나누면 `Infinity` 가 화면까지 간다.
 */
export function edgeShare(lengths: readonly (number | null | undefined)[],
                          edge: number, s: number): number {
  let acc = 0;
  for (let i = 0; i < edge; i++) acc += lengths[i] ?? 0;
  const L = lengths[edge] ?? 0;
  if (!(L > 0)) return 1;
  return Math.max(0, Math.min(1, (s - acc) / L));
}
