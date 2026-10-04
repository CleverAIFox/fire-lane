/**
 * handoff.test.ts — 관제 지령을 읽는 자리.  (DECISIONS §386)
 *
 * ★ 이 내비는 **지령을 상속만 받는다.** 기사는 목적지를 고르지 않는다 —
 *   고를 수 있게 두면 지령과 화면이 갈린다.
 */
import { describe, expect, it } from "vitest";
import { canPickDestination, readHandoff } from "../src/domain/handoff";

describe("관제 지령 읽기", () => {
  it("사건 좌표가 오면 상속으로 본다", () => {
    const h = readHandoff("?incident=126.9222,35.1466&label=지산동");
    expect(h.inherited).toBe(true);
    expect(h.incident).toEqual([126.9222, 35.1466]);
    expect(h.label).toBe("지산동");
  });

  it("라벨이 없으면 「접수 위치」로 둔다", () => {
    expect(readHandoff("?incident=126.92,35.15").label).toBe("접수 위치");
  });

  it("좌표가 없으면 상속이 아니다", () => {
    const h = readHandoff("?vehicle=p1&station=지산");
    expect(h.inherited).toBe(false);
    expect(h.incident).toBeNull();
    expect(h.vehicle).toBe("p1");
    expect(h.station).toBe("지산");
  });

  it("좌표가 망가졌으면 없는 것으로 본다", () => {
    for (const bad of ["?incident=abc", "?incident=126.92", "?incident=,",
                       "?incident=126.92,35.15,7", "?incident=999,35.15"]) {
      expect(readHandoff(bad).inherited, bad).toBe(false);
    }
  });

  it("라벨은 좌표가 있을 때만 붙는다", () => {
    expect(readHandoff("?label=떠돌이").label).toBeNull();
  });
});

describe("깃발은 켜는 쪽을 명시한다", () => {
  it("인자가 없으면 꺼져 있다", () => {
    const h = readHandoff("");
    expect(h.dev).toBe(false);
    expect(h.demo).toBe(false);
  });

  // ★ 종전 `!== "0"` 이 배포본에 시연 막대를 달고 나갔다. 운전석에서 손이
  //   스치면 모의 주행이 실제 GPS 를 대체한다(§W13-1).
  it("0 이 아닌 아무 값으로 켜지면 안 된다", () => {
    for (const s of ["?dev=2", "?dev=true", "?dev=", "?demo=yes", "?demo=0"]) {
      const h = readHandoff(s);
      expect(h.dev, s).toBe(false);
      expect(h.demo, s).toBe(false);
    }
  });

  it("1 일 때만 켜진다", () => {
    expect(readHandoff("?dev=1").dev).toBe(true);
    expect(readHandoff("?demo=1").demo).toBe(true);
  });
});

describe("목적지 선택 가능 여부", () => {
  it("지령이 왔으면 기사는 못 고른다", () => {
    expect(canPickDestination(readHandoff("?incident=126.92,35.15"))).toBe(false);
  });

  it("지령이 없으면 고를 수 있다 — 훈련과 점검이 그 길이다", () => {
    expect(canPickDestination(readHandoff(""))).toBe(true);
  });
});
