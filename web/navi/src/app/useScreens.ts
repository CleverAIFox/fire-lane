/**
 * app/useScreens.ts — 어느 화면이 떠 있나. 화면 전환만 진다.
 *
 * ── 흐름 (2026-10-05 · DECISIONS §400) ───────────────────────────
 *
 *   wait(대기) ──지령이 온다──▶ brief(경로 설명) ──안내 시작──▶ drive
 *      ▲                                                        │
 *      └──────────────────── 처음부터 ◀───────────────────────────┘
 *
 * ★ **고르는 화면이 없다.** 종전 흐름은 넷이었고 셋이 선택 화면이었다 —
 *   `dispatch`(출동 정보 입력) · `search`(목적지 검색) · `vehicle`(차량 선택).
 *   사람이 그 전제를 잘랐다:
 *
 *       「내비가 스스로 고를 수 있는건 없다니깐 완전 수동적이라고 우리 내비는
 *        카카오택시처럼 넌 카카오택시 기사가 손님 선택할 수 있냐 목적지
 *        선택할 수 있냐 경로 선택할 수 있냐」
 *
 *   셋을 지웠다. 목적지 · 차량 · 경로는 전부 **관제가 정해서 지령에 실어
 *   보낸다**(`domain/dispatch`). 지령이 없으면 운전석은 **대기**다 —
 *   검색창이 아니다.
 *
 * ★ `brief` 는 종전 `compare` 자리인데 **고르는 화면이 아니다.** 왜 이 길로
 *   가는지를 보여주고 「안내 시작」 하나만 받는다. 둘을 나란히 그리는 것은
 *   비교가 아니라 **설명**이다 — 기사가 고르라고 두면 그 순간 수동이 아니다.
 *
 * ★ 한 번에 하나만 뜬다. 겹치면 지도가 안 보인다 — 골목에서 지도를
 *   가리는 것이 이 앱에서 제일 나쁘다.
 */
import { useCallback, useState } from "react";

export type Screen = "wait" | "brief" | "drive";

export function useScreens(initial: Screen = "wait") {
  const [screen, setScreen] = useState<Screen>(initial);
  const open = useCallback((s: Screen) => setScreen(s), []);
  return { screen, open, planning: screen !== "drive" };
}
