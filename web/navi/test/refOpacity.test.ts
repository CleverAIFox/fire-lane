/**
 * test/refOpacity.test.ts — 발행 범위 밖(reference) 구간 흐림 (PLAN #62 · DECISIONS §614).
 */
import { describe, expect, it } from "vitest";
import { andFilter, refFilter, OPS_SEG_OPACITY, REF_FACTOR, parseShowRef, refOpacity, refOpacityValue } from "../src/components/opsLayers";

const IN_SCOPE = ["target", "corridor", "listed"];
const VERDICTS = ["clear", "needs_cv", "blocked", "unknown"];

describe("refOpacityValue", () => {
  it("show=false 면 reference 는 0", () => {
    for (const v of VERDICTS) expect(refOpacityValue(false, "reference", v, 1)).toBe(0);
  });
  it("reference blocked 하한이 일반 reference 보다 높다", () => {
    expect(REF_FACTOR.blocked).toBeGreaterThan(REF_FACTOR.general);
    expect(refOpacityValue(true, "reference", "blocked", 1))
      .toBeGreaterThan(refOpacityValue(true, "reference", "needs_cv", 1));
  });
  it("reference 는 어느 쪽이든 기존값보다 흐리거나 같다", () => {
    for (const v of VERDICTS) expect(refOpacityValue(true, "reference", v, 0.9)).toBeLessThanOrEqual(0.9);
  });
  it("target · corridor · listed 는 기존값 그대로 (show 와 무관)", () => {
    for (const t of IN_SCOPE) for (const v of VERDICTS) for (const show of [true, false])
      expect(refOpacityValue(show, t, v, 0.55)).toBe(0.55);
  });
  it("scope_tier 가 없는 구간(옛 발행물)은 기존값", () => {
    expect(refOpacityValue(false, null, "blocked", 1)).toBe(1);
    expect(refOpacityValue(false, undefined, "blocked", 1)).toBe(1);
  });
});

describe("refOpacity (식)", () => {
  it("끄면 reference 가지가 0, 아니면 blocked/일반 수가 식에 박힌다", () => {
    expect(JSON.stringify(refOpacity(false, 1))).toBe(
      JSON.stringify(["case", ["==", ["get", "scope_tier"], "reference"], 0, 1]));
    const on = JSON.stringify(refOpacity(true, 1));
    expect(on).toContain(String(REF_FACTOR.blocked));
    expect(on).toContain(String(REF_FACTOR.general));
  });
  it("기본(마지막 가지)은 기존값이다", () => {
    for (const base of Object.values(OPS_SEG_OPACITY)) {
      const e = refOpacity(true, base) as unknown[];
      expect(e[e.length - 1]).toBe(base);
    }
  });
});

describe("parseShowRef (?ref=)", () => {
  it("없으면 기본(보임)", () => { expect(parseShowRef("")).toBe(true); expect(parseShowRef("?terrain=0")).toBe(true); });
  it("0 이면 숨김, 1 이면 보임", () => { expect(parseShowRef("?ref=0")).toBe(false); expect(parseShowRef("?ref=1")).toBe(true); });
  it("잘못된 값이면 기본(보임) — 오타가 막힌 길을 지우지 않는다", () => {
    for (const q of ["?ref=", "?ref=off", "?ref=false", "?ref=2", "?ref=00"]) expect(parseShowRef(q)).toBe(true);
  });
});

/** 거르기 식 `["!=", ["get","scope_tier"], X]` 를 한 구간에 대 본다 — 질의에 잡히는가. */
function queryable(f: unknown[] | null, tier: string): boolean {
  if (f === null) return true;
  if (f[0] === "all") return (f.slice(1) as unknown[][]).every((x) => queryable(x, tier));
  if (f[0] === "!=") return tier !== f[2];
  throw new Error("시험이 모르는 식");
}

describe("refFilter (숨김일 때만 클릭을 막는다)", () => {
  it("숨김에서 reference 는 질의에 안 잡히고 나머지는 잡힌다", () => {
    const f = refFilter(false);
    expect(queryable(f, "reference")).toBe(false);
    for (const t of IN_SCOPE) expect(queryable(f, t)).toBe(true);
  });
  it("흐림(보임)에서는 거르지 않는다 — reference 도 눌린다", () => {
    expect(refFilter(true)).toBeNull();
    expect(queryable(refFilter(true), "reference")).toBe(true);
  });
  it("판정 숨김 거르기와 합쳐도 reference 가 빠진다", () => {
    const hid = ["!", ["in", ["get", "verdict"], ["literal", ["clear"]]]];
    const f = andFilter(hid, refFilter(false)) as unknown[];
    expect(f[0]).toBe("all");
    expect(f).toContainEqual(refFilter(false));
    expect(andFilter(hid, refFilter(true))).toEqual(hid);
    expect(andFilter(null, null)).toBeNull();
  });
});

describe("ops-unreach 도 흐림 대상", () => {
  it("OPS_SEG_OPACITY 에 든다 — 기존값 그대로 + reference 는 곱한다", () => {
    expect(OPS_SEG_OPACITY["ops-unreach"]).toBe(0.75);
    expect(refOpacityValue(true, "reference", "clear", OPS_SEG_OPACITY["ops-unreach"])).toBeCloseTo(0.75 * REF_FACTOR.general);
  });
});
