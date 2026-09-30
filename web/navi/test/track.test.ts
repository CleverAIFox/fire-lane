/**
 * track.test.ts — 주행 정책 넷. (DECISIONS §336 · `domain/track.ts`)
 *
 * ★ 넷 다 `app/useNavigation.ts`(482줄) 안에 살던 것이고, 옮기기 전에는 시험이
 *   **하나도 없었다.** 훅 안에서는 물으려면 렌더러가 필요하고 `vitest` 환경이
 *   `node` 다 — §329 가 `useVoice` 에서 배운 그대로다.
 */
import { describe, expect, it } from "vitest";
import { chooseSource, edgeShare, nextBearing, weakCrossed } from "../src/domain/track";
import type { Phase, PosMode } from "../src/domain/types";

const src = (phase: Phase, simSpeed: number, hasPlan: boolean, posMode: PosMode) =>
  chooseSource({ phase, simSpeed, hasPlan, posMode });

describe("① 위치원 선택", () => {
  it("주행 전에는 아무것도 안 붙인다", () => {
    for (const p of ["loading", "idle", "picked", "preview"] as Phase[]) {
      expect(src(p, 4, true, "gpsSim")).toBe("none");
    }
  });

  it("도착 뒤에도 안 붙인다 — 끝난 뒤에 따라다닐 이유가 없다", () => {
    expect(src("arrived", 4, true, "gpsSim")).toBe("none");
  });

  it("시연 배속이 있고 경로가 있으면 모드가 고른다", () => {
    expect(src("guiding", 4, true, "gpsSim")).toBe("replay");
    expect(src("guiding", 4, true, "route")).toBe("simulation");
  });

  it("배속이 0 이면 시연이 아니다 — 경로가 있어도 실제 GPS", () => {
    expect(src("guiding", 0, true, "gpsSim")).toBe("gps");
    expect(src("guiding", 0, true, "route")).toBe("gps");
  });

  it("경로가 없으면 배속이 있어도 실제 GPS — 따라갈 선이 없다", () => {
    expect(src("guiding", 4, false, "route")).toBe("gps");
  });
});

describe("② 진행방향", () => {
  const A: [number, number] = [127.0, 35.0];

  it("heading 이 오면 그대로 쓴다 — 단말이 잰 값이 낫다", () => {
    const r = nextBearing(10, { lon: A[0], lat: A[1], heading: 271 }, [126.9, 35.0], 1.2);
    expect(r.brg).toBe(271);
    expect(r.lastPos).toEqual(A);
  });

  it("heading 이 0 이어도 없는 것으로 안 읽는다 — 정북이다", () => {
    expect(nextBearing(180, { lon: A[0], lat: A[1], heading: 0 }, null, 1.2).brg).toBe(0);
  });

  it("문턱만큼 안 움직였으면 **옛 방위를 지킨다**", () => {
    // 같은 자리에서 1cm 떨린 것 — 서 있는 차의 GPS 다
    const near: [number, number] = [A[0] + 0.0000001, A[1]];
    const r = nextBearing(77, { lon: near[0], lat: near[1] }, A, 1.2);
    expect(r.brg).toBe(77);
    expect(r.lastPos).toEqual(A);         // 잰 자리도 안 옮긴다
  });

  it("문턱을 넘으면 두 점에서 낸다", () => {
    const east: [number, number] = [A[0] + 0.001, A[1]];   // 약 91m 동쪽
    const r = nextBearing(77, { lon: east[0], lat: east[1] }, A, 1.2);
    expect(r.brg).toBeGreaterThan(80);
    expect(r.brg).toBeLessThan(100);      // 동쪽 ≈ 90°
    expect(r.lastPos).toEqual(east);
  });

  it("★ 첫 측위는 방위를 0 으로 안 떨어뜨린다 — 북쪽이라는 거짓말이 된다", () => {
    const r = nextBearing(123, { lon: A[0], lat: A[1] }, null, 1.2);
    expect(r.brg).toBe(123);
    expect(r.lastPos).toEqual(A);         // 자리는 기억한다
  });
});

describe("③ 정확도 보고", () => {
  it("같은 쪽에 머물면 안 올린다 — 1Hz 숫자가 화면을 덮는다", () => {
    expect(weakCrossed(12, 13, 20)).toBe(false);
    expect(weakCrossed(40, 55, 20)).toBe(false);
  });

  it("넘나들 때만 올린다", () => {
    expect(weakCrossed(12, 25, 20)).toBe(true);
    expect(weakCrossed(25, 12, 20)).toBe(true);
  });

  it("★ 못 잰 것(null)은 제 갈래다 — 멀쩡한 것으로 묶으면 안 된다", () => {
    expect(weakCrossed(null, 12, 20)).toBe(true);
    expect(weakCrossed(12, null, 20)).toBe(true);
    expect(weakCrossed(null, null, 20)).toBe(false);
  });

  it("임계 위는 약함, 임계 자신은 아니다", () => {
    expect(weakCrossed(20, 21, 20)).toBe(true);
    expect(weakCrossed(19, 20, 20)).toBe(false);
  });
});

describe("④ 구간 내 비율", () => {
  const L = [100, 50, 200];

  it("구간 처음과 끝", () => {
    expect(edgeShare(L, 0, 0)).toBe(0);
    expect(edgeShare(L, 0, 100)).toBe(1);
    expect(edgeShare(L, 1, 100)).toBe(0);
    expect(edgeShare(L, 1, 125)).toBe(0.5);
    expect(edgeShare(L, 2, 250)).toBe(0.5);
  });

  it("★ 0..1 로 자른다 — 추정기가 경계에서 넘치면 진행률이 100%를 넘는다", () => {
    expect(edgeShare(L, 1, 400)).toBe(1);
    expect(edgeShare(L, 1, 0)).toBe(0);
  });

  it("★ 길이 없는 구간은 1 로 본다 — 0 으로 나누면 Infinity 가 화면까지 간다", () => {
    expect(edgeShare([100, 0, 200], 1, 100)).toBe(1);
    expect(edgeShare([100, null, 200], 1, 100)).toBe(1);
    expect(Number.isFinite(edgeShare([0], 0, 0))).toBe(true);
  });

  it("앞 구간에 길이가 없어도 뒤가 안 깨진다", () => {
    expect(edgeShare([null, 100], 1, 50)).toBe(0.5);
  });
});
