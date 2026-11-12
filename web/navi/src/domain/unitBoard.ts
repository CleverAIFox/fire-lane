/**
 * domain/unitBoard.ts — **관제 차량 상태판의 순서.**  (DECISIONS §726 · B3)
 *
 * ★ 왜 생겼나 (2026-11-12). 상황판이 **연결된 순서**(`Object.values` — 먼저 말을 건 차가 위)로 그려져 「끊김」이 맨 위 · 「출동 중」이 둘째 · 「대기」가 셋째로 보였다.
 *   관제가 먼저 봐야 할 것은 **출동 중**이다. 「끊김」이 눈에 띄는 것은 **색이 할 일**(`D.danger`)이지 순서가 할 일이 아니다.
 *
 * ★ 순위 — 낮을수록 위:
 *     0 출동 중          연결돼 있고 남은 거리가 있다
 *     1 끊김 · 출동 중이었다  마지막 상태에 남은 거리가 있다 — **길을 잃었을 수 있는 차**라 대기보다 먼저 본다(색은 그대로 「끊김」 빨강)
 *     2 대기
 *     3 끊김 · 대기였다     나가 있던 차가 아니다
 *   같은 순위 안은 **차량 이름순**이다 — 남은 거리 · 도착 시각으로 정렬하면 0.5초마다 행이 서로 자리를 바꿔 누를 수가 없다.
 *
 * IN    차량 목록 · 지금 시각(`unitStale` 이 쓰는 시계)
 * OUT   새 배열(입력을 안 바꾼다) · 상태 한 낱말
 * 밖    **그리는 일 · 색 · 문구는 안 한다**(`OpsApp`). 목록의 다른 쓰임(지도 마커 · 포커스)의 순서도 안 바꾼다 — 상황판만이다.
 */
import { unitStale, type Unit } from "./opsProtocol";

export type UnitStatus = "dispatching" | "lost" | "idle";

/** 차 하나의 상태 — 끊김이 먼저다(들리지 않는 차의 마지막 말은 지금이 아니다) */
export function unitStatus(u: Unit, now: number): UnitStatus {
  return unitStale(u, now) ? "lost" : u.last.remainM != null ? "dispatching" : "idle";
}

/** 순위(낮을수록 위). 끊김은 **나가 있었는가**로 둘로 갈린다 */
export function unitRank(u: Unit, now: number): number {
  const s = unitStatus(u, now), was = u.last.remainM != null;
  return s === "dispatching" ? 0 : s === "lost" ? (was ? 1 : 3) : 2;
}

/** 상황판 순서 — 출동 중 먼저. 입력을 바꾸지 않고 새 배열을 낸다 */
export function sortUnits(units: readonly Unit[], now: number): Unit[] {
  return [...units].sort((a, b) => unitRank(a, now) - unitRank(b, now) || (a.unit < b.unit ? -1 : a.unit > b.unit ? 1 : 0));
}
