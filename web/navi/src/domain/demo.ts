/**
 * domain/demo.ts — **시연은 GPS 와 무관한 축이다.**  (DECISIONS §713 · ⓲C)
 *
 * ── 왜 생겼나 (2026-11-12) ──────────────────────────────────────
 * 구조가 거꾸로였다 — 「GPS 가 주 · 시연은 GPS 실패 시 폴백」. 실제로는 **시연이 매일 돌고 실차는 가끔 돈다**
 * (개발 · 발표 · 심사가 전부 구역 밖이다). 위치가 잡히든 말든 · 구역 안이든 밖이든 시연은 켜져야 한다.
 *
 * 측위는 세 상태다(`GpsState` — 시연이 꺼져 있을 때만 의미가 있다):
 *   ① `none`     GPS 없음(데스크톱 · 권한 거부)
 *   ② `outside`  GPS 있고 구역 밖(서울에서 연다)
 *   ③ `live`     GPS 있고 구역 안 = **실주행**
 *   (`idle` 은 아직 아무 측위도 안 온 때다.)
 *
 * ★ 켜는 길은 **명시적**이다 — `?demo=1` 주소, 또는 아래 `demoUi` 가 내는 단추. 자동으로 안 켠다(종전에는 구역 밖이면 말없이 시연으로 갈아탔다).
 * ★ **실주행 중에는 못 켠다** — 주행 중이고 구역 안에서 측위가 실제로 오는 중(`live`)이면 단추가 없다. 운전석에서 손이 스쳐 모의 주행이
 *   실제 GPS 를 대체하면 화면의 차가 운전자가 아니게 된다(`App.tsx` W13-1).
 * ★ 켜져 있으면 **늘 표가 난다**(`badge`) — 실주행과 헷갈리면 최악이다.
 * ★ 안내 문구가 가리키는 단추는 **같은 규칙에서 나온다**(`DEMO_START` 한 이름) — 문구가 뜨는 곳에는 단추가 있다(`demoUi` 가 `start` 를 낸다).
 *
 * IN    단계 · 측위 상태 · 시연 켜짐
 * OUT   켤 수 있는가 · 안내 문구(화면이 낼 표 · 단추는 `ui/DemoStrip` 의 `demoUi` — 첫 화면에 안 필요해 지연 청크에 둔다)
 * 밖    시연을 **어떻게** 돌리는지(위치원)는 `app/usePositionSource` 가 안다.
 */
import type { Phase } from "./types";

export type GpsState = "idle" | "none" | "outside" | "live";
/** 안내 문구와 단추가 **같이 쓰는** 이름 — 한 곳에서 바꾼다 */
export const DEMO_START = "시연으로 주행";

/** 켤 수 있는가. 꺼져 있고 **실주행 중**이면 못 켠다 */
export function canStartDemo(phase: Phase, gps: GpsState, demo: boolean): boolean {
  return demo || !(phase === "guiding" && gps === "live");
}

/** ① GPS 없음. 문구가 가리키는 단추(`DEMO_START`)는 `demoUi` 가 같은 조건에서 낸다 */
export const noGpsNotice = (): string => `GPS 신호가 없다 — 「${DEMO_START}」을 누른다`;
