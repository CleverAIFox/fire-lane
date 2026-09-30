/**
 * phase.ts — **한 건의 출동이 어느 단계에 있는가.**
 *
 * ── 왜 이 파일이 생겼나 (DECISIONS §336) ─────────────────────
 * 단계 이동이 `app/useNavigation.ts` 안에 **여덟 자리로 흩어져** 있었다.
 * `setPhase("arrived")` 가 두 곳, `setPhase("picked")` 가 두 곳, 그중 하나만
 * 「로딩 중이면 안 옮긴다」는 가드를 갖고 있었다. 그 가드가 왜 한쪽에만
 * 있는지는 코드를 전부 읽어야 알 수 있었고, **읽어도 그것이 규칙인지 사고인지
 * 가릴 수가 없었다.**
 *
 * 표로 옮기면 그 물음이 눈으로 보인다. 그리고 물을 수 있다.
 *
 * IN    현재 단계 · 일어난 일
 * OUT   다음 단계
 * 밖    **언제 그 일이 일어나는지는 안 정한다** — 도착 판정(남은 거리)도,
 *       데이터가 다 왔는지도 훅이 안다. 여기가 드는 것은 **일이 일어났을 때
 *       어디로 가는가** 하나다.
 */
import type { Phase } from "./types";

/**
 * 단계를 움직이는 일.
 *
 *   loaded     번들이 다 왔다
 *   pick       목적지(또는 출발지)를 찍었다
 *   routed     경로가 나왔다
 *   start      안내를 시작했다
 *   arrive     도착했다 — 남은 거리든 시뮬레이션 끝이든
 *   reset      처음으로
 */
export type Event = "loaded" | "pick" | "routed" | "start" | "arrive" | "reset";

/**
 * ★ **`loading` 은 사람의 조작을 안 받는다.** 데이터가 없는데 목적지를 찍으면
 *   찍을 대상이 없다 — 그 상태에서 `picked` 로 가면 화면은 「골랐다」고 말하고
 *   실제로는 아무것도 안 골라져 있다. 종전에 이 가드가 `setOriginAt` 한 곳에만
 *   있었고 `pick` 쪽에는 없었다. 여기서는 **한 자리**다.
 *
 * ★ `routed` 는 `guiding` 을 **안 깬다.** 주행 중 재탐색이 경로를 갈아끼우는데,
 *   그때 `preview` 로 떨어지면 화면이 주행에서 미리보기로 튄다. 종전에는
 *   호출부가 `keepGuiding` 인자로 그것을 들고 있었다 — 규칙이 인자에 살면
 *   부르는 자리마다 그 규칙을 다시 판단한다.
 *
 * ★ `arrived` 에서 `arrive` 가 또 오면 그대로 둔다. 시뮬레이션 끝 신호와 남은
 *   거리 판정이 **둘 다** 올 수 있고, 둘은 같은 사실을 말한다.
 */
export function nextPhase(cur: Phase, ev: Event): Phase {
  if (ev === "reset") return "idle";
  if (cur === "loading") return ev === "loaded" ? "idle" : "loading";
  switch (ev) {
    case "loaded": return cur;              // 두 번 오면 무시 — 이미 지났다
    case "pick":   return "picked";
    case "routed": return cur === "guiding" ? "guiding" : "preview";
    case "start":  return "guiding";
    case "arrive": return "arrived";
  }
}
