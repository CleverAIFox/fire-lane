/**
 * mapPitch.test.ts — 기울임 상한을 주소 질의로 고른다. (PLAN #78 ② · `infra/mapPitch.ts`)
 *
 * ★ 85 대 75 는 **눈 본 사람이 정한다.** 여기가 무는 것은 그 사람이 고를 수 있는가(`?pitch=85`)와,
 *   질의가 없거나 틀리면 **지금 값(75)이 그대로인가**다 — 손잡이가 기본 화면을 바꾸면 안 된다.
 *
 * IN    주소 질의 글자
 * OUT   기울임 상한(도)
 * PARAM 기본 75 · 범위 60‥85
 * 밖    어느 값이 보기 좋은가(사람 눈) · maplibre 가 그 값을 실제로 받는가(브라우저)
 */
import { describe, expect, it } from "vitest";
import { MAX_PITCH_DEFAULT, MAX_PITCH_HI, MAX_PITCH_LO, maxPitchFrom } from "../src/infra/mapPitch";

/** ★ `node:fs` 를 안 쓴다 — `layering.test.ts` 와 같이 vite 가 글자로 준다. */
const NAVI_MAP = Object.values(import.meta.glob(
  "../src/components/NaviMap.tsx", { query: "?raw", import: "default", eager: true },
))[0] as string;

describe("기본값 — 질의가 없으면 아무것도 안 바뀐다", () => {
  it("★ 기본은 75 다 — 행이 적은 85 가 아니라 **지금 코드의 값**", () => {
    expect(MAX_PITCH_DEFAULT).toBe(75);
    expect(maxPitchFrom("")).toBe(75);
    expect(maxPitchFrom("?dev=1&debug=1")).toBe(75);
  });
});

describe("고르기 — 둘 다 된다", () => {
  it("?pitch=85 · ?pitch=75", () => {
    expect(maxPitchFrom("?pitch=85")).toBe(85);
    expect(maxPitchFrom("?pitch=75")).toBe(75);
  });
  it("다른 질의와 같이 와도 읽는다", () => {
    expect(maxPitchFrom("?dev=1&pitch=85&vehicle=pump-js")).toBe(85);
  });
  it("범위의 양 끝은 든다", () => {
    expect(maxPitchFrom(`?pitch=${MAX_PITCH_LO}`)).toBe(MAX_PITCH_LO);
    expect(maxPitchFrom(`?pitch=${MAX_PITCH_HI}`)).toBe(MAX_PITCH_HI);
  });
});

describe("★ 없는 값 · 범위 밖은 기본값이다 — 가까운 쪽으로 당기지 않는다", () => {
  const bad = [
    "?pitch=", "?pitch=abc", "?pitch=85deg", "?pitch=8.5e1", "?pitch=85.0", "?pitch=-85", "?pitch=+85",
    "?pitch=%2085", "?pitch=59", "?pitch=86", "?pitch=0", "?pitch=850", "?pitch=9999", "?pitch=NaN", "?pitch=Infinity",
  ];
  for (const q of bad) {
    it(`${q} → 75`, () => { expect(maxPitchFrom(q)).toBe(MAX_PITCH_DEFAULT); });
  }
  it("둘이 오면 첫째를 읽는다 — 첫째가 틀리면 기본값이다(뒤의 것으로 넘어가지 않는다)", () => {
    expect(maxPitchFrom("?pitch=85&pitch=60")).toBe(85);
    expect(maxPitchFrom("?pitch=xx&pitch=85")).toBe(MAX_PITCH_DEFAULT);
  });
  it("하한이 코드가 주는 기울임(1인칭 60)보다 낮지 않다 — 낮으면 추적 카메라가 잘린다", () => {
    const given = [...NAVI_MAP.matchAll(/\bpitch:\s*(\d+)/g)].map((m) => Number(m[1]));
    expect(given.length).toBeGreaterThan(0);
    expect(MAX_PITCH_LO).toBeGreaterThanOrEqual(Math.max(...given));
  });
});

describe("배선 — 지도가 이 값을 쓴다", () => {
  it("★ `NaviMap` 의 `maxPitch` 가 숫자로 박혀 있지 않다 — 박히면 손잡이가 죽는다", () => {
    expect(NAVI_MAP).toMatch(/maxPitch:\s*maxPitchFrom\(location\.search\)/);
    expect(NAVI_MAP).not.toMatch(/maxPitch:\s*\d/);
  });
});
