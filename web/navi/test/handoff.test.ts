/**
 * handoff.test.ts — 관제 지령을 읽는 자리.  (DECISIONS §386)
 *
 * ★ 이 내비는 **지령을 상속만 받는다.** 기사는 목적지를 고르지 않는다 —
 *   고를 수 있게 두면 지령과 화면이 갈린다.
 */
import { describe, expect, it } from "vitest";
import { canPickDestination, editHands, readHandoff } from "../src/domain/handoff";

/** ★ `node:fs` 를 안 쓴다 — `wiring.test.ts` 와 같은 이유로 vite 가 준다. */
const SRC: Record<string, string> = import.meta.glob(
  "../src/**/*.tsx", { query: "?raw", import: "default", eager: true },
);

function src(tail: string): string {
  const k = Object.keys(SRC).find((x) => x.endsWith(tail));
  if (!k) throw new Error(`소스를 못 찾았다: ${tail}`);
  return SRC[k];
}

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

/**
 * ── 바꾸는 손  (DECISIONS §393) ────────────────────────────────
 *
 * ★ 2026-10-04 실측. `canPickDestination` 은 서 있었는데 `App.tsx` 가 그것을
 *   **핸들러에만** 걸었다 — `onArm={canPick ? setArmed : () => {}}`. 버튼은
 *   그대로 그려졌고, 지령이 온 운전석 화면에서 「위치 변경」과 「지도에서
 *   직접 선택」이 말없이 씹혔다(족1). 그리고 `onSwap` 에는 **조건이 아예
 *   없어서** 출발·도착이 실제로 뒤집혔다.
 *
 * ★ 그래서 여기가 묻는 것은 두 가지다 — ① 묶음이 통째로 `null` 이 되는가
 *   ② **그 모양이 되돌아올 수 없는가**. ②가 없으면 다음 손이 늘 때 또
 *   하나를 묶는 걸 잊는다.
 */
describe("바꾸는 손", () => {
  const HANDS = { onStation: () => {}, onArm: () => {}, onSearch: () => {}, onSwap: () => {} };

  it("지령이 왔으면 손이 통째로 없다 — 빈 함수가 아니라 null 이다", () => {
    expect(editHands(readHandoff("?incident=126.92,35.15"), HANDS)).toBeNull();
  });

  it("지령이 없으면 넘긴 묶음을 그대로 돌려준다", () => {
    expect(editHands(readHandoff(""), HANDS)).toBe(HANDS);
  });

  it("출발 센터도 같은 문이다 — 목적지만 고정하면 화면이 지령과 갈린다", () => {
    expect(editHands(readHandoff("?incident=126.92,35.15&station=지산"), HANDS)).toBeNull();
  });

  // ★ 여기부터는 **모양**을 본다. 값이 아니라 소스다.
  it("DispatchPanel 은 바꾸는 손을 낱개로 안 받는다", () => {
    const s = src("ui/DispatchPanel.tsx");
    const props = s.slice(s.indexOf("interface Props"), s.indexOf("export function DispatchPanel"));
    for (const name of ["onStation", "onArm", "onSearch", "onSwap"]) {
      expect(props, `Props 가 ${name} 를 낱개로 받으면 하나를 묶는 걸 잊는다`)
        .not.toContain(name);
    }
    expect(props).toContain("edit: EditHands | null");
  });

  it("App 은 그 묶음을 editHands 를 거쳐서만 넘긴다", () => {
    const s = src("App.tsx");
    expect(s).toContain("edit={editHands(hand,");
    // 빈 함수로 묶는 옛 모양이 되살아나면 운다.
    // ★ **한 줄 안에서만** 본다. `[^}]*` 로 두면 줄을 넘어 파일 저쪽의
    //   아무 빈 함수에나 걸린다 — 처음 쓴 판이 실제로 그랬다.
    // ★ 주석 줄은 코드가 아니다 — 옛 모양을 **적어 둔 설명**이 제 시험에
    //   걸렸다(첫 판이 그랬다). 설명을 지우면 왜 묶였는지가 사라진다.
    const bad = s.split("\n")
      .filter((ln) => !/^\s*(\/\/|\*|\/\*)/.test(ln))
      .filter((ln) => /canPick\s*\?.*\(\s*\)\s*=>\s*\{\s*\}/.test(ln));
    expect(bad, "`canPick ? f : () => {}` 는 버튼을 그려 놓고 손만 묶는 모양이다")
      .toEqual([]);
  });
});
