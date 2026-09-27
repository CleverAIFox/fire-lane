/**
 * serviceArea.test.ts — 측위가 데이터 범위 밖인가.  (DECISIONS §275)
 *
 * ★ 여기가 재는 것은 **「안내할 수 있는가」** 하나다. 범위 밖일 때 무엇을
 *   할지(갈아타기 · 안내)는 `usePositionSource` 소관이고 아래 마지막 둘이
 *   그 배선만 확인한다 — 훅 자체는 브라우저가 있어야 돈다.
 */
import { describe, expect, it } from "vitest";
import { EDGE_MARGIN_M, metresOutside, outsideNotice, outsideServiceArea }
  from "../src/domain/serviceArea";
import type { LngLat } from "../src/domain/geo";

/** `web/data/view.json` 의 실물 값. 상수를 베끼지 않는다 — 두 벌이 된다. */
const BOX: [LngLat, LngLat] = [[126.9095, 35.1431], [126.9438, 35.1593]];
const DONGMYEONG: LngLat = [126.926648, 35.151173];   // view.json 의 center
const SEOUL: LngLat = [126.9780, 37.5665];
const GWANGJU_WEST: LngLat = [126.8514, 35.1601];   // 광주 서구 — 같은 시, 데이터 밖

describe("범위 판정", () => {
  it("동명동 한가운데는 안이다", () => {
    expect(outsideServiceArea(DONGMYEONG, BOX)).toBe(false);
    expect(metresOutside(DONGMYEONG, BOX)).toBe(0);
  });

  it("★ 서울은 밖이다 — GPS 는 잡히지만 안내할 수 없다", () => {
    expect(outsideServiceArea(SEOUL, BOX)).toBe(true);
    // 265km 쯤. 자릿수가 맞는지만 본다 — 정확한 수는 이 검사의 관심이 아니다
    expect(metresOutside(SEOUL, BOX)).toBeGreaterThan(200_000);
  });

  it("★ 같은 광주 안에서도 밖이다 — 데이터가 동명동 한 동네뿐이다", () => {
    expect(outsideServiceArea(GWANGJU_WEST, BOX)).toBe(true);
    expect(metresOutside(GWANGJU_WEST, BOX)).toBeGreaterThan(5_000);
  });

  it("경계 바로 밖 GPS 오차 한 번치는 안으로 본다", () => {
    const [[w, s]] = BOX;
    const near: LngLat = [w - 0.0005, s];          // 약 45m 서쪽
    expect(metresOutside(near, BOX)).toBeLessThan(EDGE_MARGIN_M);
    expect(outsideServiceArea(near, BOX)).toBe(false);
  });

  it("여유를 넘으면 밖이다 — 그보다 멀면 오차가 아니라 다른 동네다", () => {
    const [[w, s]] = BOX;
    const far: LngLat = [w - 0.005, s];            // 약 455m 서쪽
    expect(metresOutside(far, BOX)).toBeGreaterThan(EDGE_MARGIN_M);
    expect(outsideServiceArea(far, BOX)).toBe(true);
  });

  it("★ 경계를 모르면 막지 않는다 — 오탐이 장치를 죽인다", () => {
    expect(outsideServiceArea(SEOUL, undefined)).toBe(false);
    expect(metresOutside(SEOUL, undefined)).toBe(0);
  });

  it("안내문이 거리를 든다 — 「밖」만 적으면 튄 것인지 딴 도시인지 모른다", () => {
    expect(outsideNotice(265_000)).toContain("265km");
    expect(outsideNotice(450)).toContain("450m");
    expect(outsideNotice(265_000)).toContain("경로 주행");
  });
});

describe("배선", () => {
  /** ★ `node:fs` 를 안 쓴다 — `@types/node` 를 더하지 않으려고 vite 가 이미 주는
   *  것을 쓴다(`layering.test.ts` 와 같은 규율). */
  const FILES: Record<string, string> = import.meta.glob(
    "../src/app/*.ts", { query: "?raw", import: "default", eager: true },
  );
  const src = (p: string) => FILES[p] ?? "";

  it("★ 실제 GPS 팔이 범위를 본다 — 안 보면 이 파일 전체가 장식이다", () => {
    const s = src("../src/app/usePositionSource.ts");
    expect(s).not.toBe("");
    expect(s).toContain("outsideServiceArea");
    // 주석은 걷는다. 설명에 이름이 나온 것을 배선으로 세면 안 된다
    const code = s.split("\n").filter((l: string) => !l.trim().startsWith("//")).join("\n");
    expect(code).toContain("outsideServiceArea(p, area)");
  });

  it("★ 경계가 `view.json` 에서 온다 — 상수를 박으면 두 벌이 된다", () => {
    const s = src("../src/app/useNavigation.ts");
    expect(s).not.toBe("");
    expect(s).toContain("data?.view.maxBounds");
    expect(s).not.toMatch(/area:\s*\[\[/);
  });
});
