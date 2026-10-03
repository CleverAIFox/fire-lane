/**
 * cv.test.ts — **영상 통과폭이 경로·안내에 들어오는 규율.** (DECISIONS §363)
 *
 * ★ 이 파일이 지키는 것은 세 문장이다 —
 *     ① 좁히는 쪽만 받는다. 넓히는 쪽은 **안 쓴다**
 *     ② 못 쟀다(`null`)를 **넓다로 안 읽는다**
 *     ③ 영상이 없으면 오늘과 **한 글자도 다르지 않다**
 *   셋 다 반대 방향까지 민다 — 한 방향만 보면 「항상 통과하는 시험」이 된다.
 */
import { describe, expect, it } from "vitest";

import {
  CV_FRESH_MS,
  CV_ROUTE_CONF,
  CV_STALE_MS,
  ageOf,
  effectiveWidth,
  fold,
  narrowedToBlocked,
  phrase,
  urgencyOf,
  type CvReading,
} from "../src/domain/cv";

const NOW = 1_800_000_000_000;

function r(x: Partial<CvReading> = {}): CvReading {
  return { t: "cv", seg: "DM-1", passM: 2.1, at: NOW, cam: "C1", conf: 0.9, ...x };
}

describe("나이", () => {
  it("방금 잰 것은 fresh 다", () => {
    expect(ageOf(r(), NOW)).toBe("fresh");
  });
  it("문턱 경계에서 갈린다", () => {
    expect(ageOf(r({ at: NOW - CV_FRESH_MS }), NOW)).toBe("fresh");
    expect(ageOf(r({ at: NOW - CV_FRESH_MS - 1 }), NOW)).toBe("aging");
    expect(ageOf(r({ at: NOW - CV_STALE_MS }), NOW)).toBe("aging");
    expect(ageOf(r({ at: NOW - CV_STALE_MS - 1 }), NOW)).toBe("stale");
  });
  it("★ 시계가 앞선 측정을 stale 로 안 버린다 — 기기 시각은 어긋난다", () => {
    expect(ageOf(r({ at: NOW + 10_000 }), NOW)).toBe("fresh");
  });
});

describe("접기", () => {
  it("같은 구간이면 **가장 최근**이 이긴다 — 가장 좁은 것이 아니다", () => {
    const v = fold([
      r({ passM: 1.2, at: NOW - 60_000 }),
      r({ passM: 3.4, at: NOW - 1_000 }),
    ], NOW).get("DM-1");
    expect(v?.routeM).toBe(3.4);
  });
  it("낡은 것은 아예 안 든다", () => {
    expect(fold([r({ at: NOW - CV_STALE_MS - 1 })], NOW).size).toBe(0);
  });
  it("aging 은 말은 해도 **경로는 안 바꾼다**", () => {
    const v = fold([r({ at: NOW - CV_FRESH_MS - 1 })], NOW).get("DM-1");
    expect(v?.sayM).toBe(2.1);
    expect(v?.routeM).toBeNull();
  });
  it("신뢰도가 낮으면 말만 한다", () => {
    const v = fold([r({ conf: CV_ROUTE_CONF - 0.01 })], NOW).get("DM-1");
    expect(v?.sayM).toBe(2.1);
    expect(v?.routeM).toBeNull();
  });
  it("★ 못 쟀으면(null) 경로도 말도 없다 — 못 잰 것은 넓다가 아니다", () => {
    const v = fold([r({ passM: null })], NOW).get("DM-1");
    expect(v?.routeM).toBeNull();
    expect(v?.sayM).toBeNull();
    expect(phrase(v!, false)).toBeNull();
  });
});

describe("합치기 — 좁히는 쪽만", () => {
  const v = (passM: number | null, at = NOW, conf = 0.9) =>
    fold([r({ passM, at, conf })], NOW).get("DM-1");

  it("영상이 좁으면 영상이 이긴다", () => {
    expect(effectiveWidth(4.0, v(2.1))).toBe(2.1);
  });
  it("★ 영상이 넓어도 **안 쓴다** — 거짓 넓음은 못 되돌린다", () => {
    expect(effectiveWidth(2.0, v(4.0))).toBe(2.0);
  });
  it("영상이 없으면 정적 그대로다 — 퇴행이 무손실이다", () => {
    expect(effectiveWidth(3.3, undefined)).toBe(3.3);
    expect(effectiveWidth(null, undefined)).toBeNull();
  });
  it("정적이 모르면 영상 하나로 안 연다", () => {
    expect(effectiveWidth(null, v(4.0))).toBeNull();
  });
  it("aging 측정은 폭을 안 바꾼다", () => {
    expect(effectiveWidth(4.0, v(2.1, NOW - CV_FRESH_MS - 1))).toBe(4.0);
  });
});

describe("막혔는가", () => {
  const fresh = (passM: number) => fold([r({ passM })], NOW).get("DM-1");

  it("지나던 길이 영상으로 막히면 참이다", () => {
    expect(narrowedToBlocked(4.0, fresh(2.1), 2.9)).toBe(true);
  });
  it("원래 못 지나던 길은 **새로 막힌 것이 아니다**", () => {
    expect(narrowedToBlocked(2.0, fresh(1.5), 2.9)).toBe(false);
  });
  it("좁아져도 아직 지나면 거짓이다", () => {
    expect(narrowedToBlocked(4.0, fresh(3.2), 2.9)).toBe(false);
  });
  it("영상이 없으면 거짓이다", () => {
    expect(narrowedToBlocked(4.0, undefined, 2.9)).toBe(false);
  });
});

describe("급함", () => {
  it("★ 막은 fresh 측정이 최상위다 — 회전보다 앞이다", () => {
    expect(urgencyOf(true, "fresh")).toBe("critical");
  });
  it("막았어도 aging 이면 한 단 내린다", () => {
    expect(urgencyOf(true, "aging")).toBe("normal");
  });
  it("안 막았으면 보통이다", () => {
    expect(urgencyOf(false, "fresh")).toBe("normal");
  });
  it("낡은 것은 아무 말도 안 한다", () => {
    expect(urgencyOf(true, "stale")).toBeNull();
  });
});

describe("문구", () => {
  const v = (at: number) => fold([r({ at })], NOW).get("DM-1")!;
  it("막았으면 **못 지난다**고 말한다", () => {
    expect(phrase(v(NOW), true)).toContain("못 지납니다");
  });
  it("조금 지난 값이면 그렇다고 말한다 — 확정으로 말하지 않는다", () => {
    expect(phrase(v(NOW - CV_FRESH_MS - 1), false)).toContain("지난 값");
  });
  it("문구가 폭을 소수 첫째 자리로 든다", () => {
    expect(phrase(v(NOW), false)).toContain("2.1미터");
  });
});
