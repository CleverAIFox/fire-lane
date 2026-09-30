/**
 * phase.test.ts — 단계 이동 표. (DECISIONS §336 · `domain/phase.ts`)
 *
 * ★ 종전에 이 이동은 `app/useNavigation.ts` 안에 **여덟 자리로 흩어져** 있었고,
 *   「로딩 중이면 안 옮긴다」 가드가 그중 **한 자리에만** 있었다. 표로 옮기니
 *   그 물음이 시험 한 줄이 된다.
 */
import { describe, expect, it } from "vitest";
import { nextPhase, type Event } from "../src/domain/phase";
import type { Phase } from "../src/domain/types";

const ALL: Phase[] = ["loading", "idle", "picked", "preview", "guiding", "arrived"];
const EVENTS: Event[] = ["loaded", "pick", "routed", "start", "arrive", "reset"];

describe("loading — 데이터가 없는 동안", () => {
  it("★ 사람의 조작을 안 받는다 — 골랐다고 말하면서 아무것도 안 골라져 있다", () => {
    for (const ev of ["pick", "routed", "start", "arrive"] as Event[]) {
      expect(nextPhase("loading", ev)).toBe("loading");
    }
  });

  it("번들이 오면 idle 로", () => {
    expect(nextPhase("loading", "loaded")).toBe("idle");
  });

  it("reset 은 loading 도 푼다 — 사람이 처음으로 돌리는 것은 언제나 된다", () => {
    expect(nextPhase("loading", "reset")).toBe("idle");
  });
});

describe("routed — 경로가 나왔다", () => {
  it("★ 주행 중에는 미리보기로 안 떨어진다 — 재탐색이 화면을 튕긴다", () => {
    expect(nextPhase("guiding", "routed")).toBe("guiding");
  });

  it("주행 전에는 미리보기로", () => {
    expect(nextPhase("idle", "routed")).toBe("preview");
    expect(nextPhase("picked", "routed")).toBe("preview");
    expect(nextPhase("preview", "routed")).toBe("preview");
  });
});

describe("arrive", () => {
  it("두 번 와도 그대로 — 시뮬레이션 끝과 남은 거리가 같은 사실을 말한다", () => {
    expect(nextPhase("guiding", "arrive")).toBe("arrived");
    expect(nextPhase("arrived", "arrive")).toBe("arrived");
  });
});

describe("loaded — 두 번 오면", () => {
  it("이미 지난 단계를 안 되돌린다", () => {
    expect(nextPhase("guiding", "loaded")).toBe("guiding");
    expect(nextPhase("picked", "loaded")).toBe("picked");
  });
});

describe("그물이 비지 않았는가", () => {
  it("모든 짝이 알려진 단계를 낸다 — 표에 구멍이 없다", () => {
    for (const p of ALL) {
      for (const ev of EVENTS) {
        expect(ALL).toContain(nextPhase(p, ev));
      }
    }
  });

  it("★ 표가 **움직이기는 하는가** — 전부 제자리면 위 시험은 언제나 초록이다", () => {
    const moved = ALL.flatMap((p) => EVENTS.map((ev) => nextPhase(p, ev) !== p))
      .filter(Boolean).length;
    expect(moved).toBeGreaterThan(10);
  });

  it("reset 은 어디서든 idle", () => {
    for (const p of ALL) expect(nextPhase(p, "reset")).toBe("idle");
  });
});
