/**
 * app/useScreens.ts — 어느 화면이 떠 있나. 화면 전환만 진다.
 *
 * ★ 한 번에 하나만 뜬다. 겹치면 지도가 안 보인다 — 골목에서 지도를
 *   가리는 것이 이 앱에서 제일 나쁘다.
 *
 * ── 흐름 ────────────────────────────────────────────────────────
 *   map ──검색/클릭──▶ preview ──안내 시작──▶ map(주행)
 *                        │  경로 비교 ▶ compare ─선택─▶ preview
 *                        └  차량 변경 ▶ vehicle ─확인─▶ preview
 *
 * ★ 목적지를 고르면 **바로 안내를 시작하지 않는다.** 상용 내비는
 *   경로와 예상 시간을 보여주고 사용자가 시작을 누른다(2026-09-06).
 */
import { useCallback, useState } from "react";

export type Screen = "map" | "search" | "preview" | "vehicle" | "compare";

export function useScreens(initial: Screen = "map") {
  const [screen, setScreen] = useState<Screen>(initial);
  /** 병목 상세는 지도 위에 겹쳐 뜬다. 화면 전환이 아니다 */
  const [bottleneckUid, setBottleneckUid] = useState<string | null>(null);

  const open = useCallback((s: Screen) => {
    setScreen(s);
    setBottleneckUid(null);
  }, []);
  const close = useCallback(() => setScreen("map"), []);

  return {
    screen, open, close,
    isMap: screen === "map",
    bottleneckUid, setBottleneckUid,
  };
}
