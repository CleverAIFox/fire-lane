/**
 * app/useScreens.ts — 어느 화면이 떠 있나. 화면 전환만 진다.
 *
 * ── 흐름 (와이어프레임 2026-09-21) ────────────────────────────────
 *
 *   dispatch(00) ──출동 차량 선택──▶ vehicle(01) ──경로 계산──▶ compare(02)
 *        ▲  └ search (사건 위치 검색)                              │
 *        └──────────────── 처음부터 ◀── drive(03~23) ◀──안내 시작──┘
 *
 * ★ 한 번에 하나만 뜬다. 겹치면 지도가 안 보인다 — 골목에서 지도를
 *   가리는 것이 이 앱에서 제일 나쁘다.
 *
 * ★ 목적지를 고르면 **바로 안내를 시작하지 않는다.** 차량을 고르고 두 경로를
 *   비교한 뒤 사람이 시작을 누른다(09-05 판의 원칙이 09-21 에도 그대로다).
 */
import { useCallback, useState } from "react";

export type Screen = "dispatch" | "search" | "vehicle" | "compare" | "drive";

export function useScreens(initial: Screen = "dispatch") {
  const [screen, setScreen] = useState<Screen>(initial);
  const open = useCallback((s: Screen) => setScreen(s), []);
  return { screen, open, planning: screen !== "drive" };
}
