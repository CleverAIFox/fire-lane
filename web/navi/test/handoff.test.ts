/**
 * handoff.test.ts — 관제 지령을 읽는 자리.  (DECISIONS §386)
 *
 * ★ 이 내비는 **지령을 상속만 받는다.** 기사는 목적지를 고르지 않는다 —
 *   고를 수 있게 두면 지령과 화면이 갈린다.
 */
import { describe, expect, it } from "vitest";
import { readHandoff, routeOf } from "../src/domain/handoff";

/** ★ `node:fs` 를 안 쓴다 — `wiring.test.ts` 와 같은 이유로 vite 가 준다. */
const SRC: Record<string, string> = {
  ...import.meta.glob("../src/**/*.tsx", { query: "?raw", import: "default", eager: true }),
  // ★ 2026-10-05 (§400). `.ts` 도 넣는다 — 화면 갈래(`app/useScreens.ts`)가
  //   거기 살고, `.tsx` 만 보던 그물에는 **안 걸렸다.**
  ...import.meta.glob("../src/**/*.ts", { query: "?raw", import: "default", eager: true }),
} as Record<string, string>;

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

describe("경로 모드 — 관제가 정한다", () => {
  it("지령이 준 값을 그대로 쓴다", () => {
    expect(routeOf(readHandoff("?incident=126.92,35.15&route=fast")))
      .toEqual({ mode: "fast", fromOrder: true });
  });

  it("지령에 없으면 안전이되 **지시가 아니라고** 적는다", () => {
    expect(routeOf(readHandoff("?incident=126.92,35.15")))
      .toEqual({ mode: "safe", fromOrder: false });
  });

  it("어휘 밖은 없는 것이다 — 오타를 지시로 읽지 않는다", () => {
    expect(readHandoff("?route=빠름").route).toBeNull();
    expect(readHandoff("?route=FAST").route).toBeNull();
  });
});

/**
 * ── 운전석은 **아무것도 안 고른다**  (DECISIONS §400) ──────────
 *
 * ★ 2026-10-05. 종전에 이 자리에는 `canPickDestination` · `editHands` 가 있었다 —
 *   「기사가 고를 수 있는 경우」를 전제로 손을 열어 두는 문이다. 사람이 그
 *   전제를 잘랐다: 「내비가 스스로 고를 수 있는건 없다」. 카카오택시 기사는
 *   손님도 목적지도 경로도 안 고른다.
 *
 * ★ 그래서 여기가 묻는 것은 「지령이 왔을 때 묶이는가」가 아니라
 *   **「손이 아예 없는가」**다. 조건부로 묶는 것은 조건이 틀리면 열리지만,
 *   없는 것은 틀릴 조건이 없다.
 */
describe("운전석에 바꾸는 손이 0 인가", () => {
  it("고르는 화면이 셋 다 없다", () => {
    const names = Object.keys(SRC).map((k) => k.split("/").pop());
    for (const gone of ["DispatchPanel.tsx", "SearchPanel.tsx", "VehiclePicker.tsx"]) {
      expect(names, `${gone} 가 살아 있으면 고르는 화면이 돌아온 것이다`)
        .not.toContain(gone);
    }
  });

  it("화면 갈래에 고르는 자리가 없다", () => {
    const s = src("app/useScreens.ts");
    expect(s).toContain('"wait" | "brief" | "drive"');
    for (const gone of ["dispatch", "search", "vehicle", "compare"]) {
      expect(s, `화면 ${gone} 는 고르는 자리였다`).not.toContain(`"${gone}"`);
    }
  });

  it("경로 설명 판은 고르는 손을 **받지도 않는다**", () => {
    const s = src("ui/RouteCompare.tsx");
    const props = s.slice(s.indexOf("interface Props"), s.indexOf("export function RouteBrief"));
    for (const hand of ["onSelect", "onPick", "onChangeVehicle"]) {
      expect(props, `${hand} 를 받으면 언젠가 누가 넘긴다`).not.toContain(hand);
    }
  });

  it("App 에 기사 손이 없다", () => {
    const code = src("App.tsx").split("\n")
      .filter((ln) => !/^\s*(\/\/|\*|\/\*)/.test(ln)).join("\n");
    for (const hand of ["setArmed", "onSelect="]) {
      expect(code, `${hand} 는 기사가 고르는 손이다`).not.toContain(hand);
    }
    // ★ 목적지와 차량을 **놓는** 자리는 남는다 — 지령을 적용하는 기계 손이다.
    //   그러나 **각각 한 번뿐**이어야 한다. 둘이면 하나는 사람이 부른다.
    for (const once of ["fleet.select(", "n.setDestAt("]) {
      expect(code.split(once).length - 1,
             `${once} 가 둘 이상이면 하나는 기사 손이다`).toBe(1);
    }
  });

  it("주행 중 경로 전환도 없다", () => {
    const code = src("App.tsx").split("\n")
      .filter((ln) => !/^\s*(\/\/|\*|\/\*)/.test(ln)).join("\n");
    expect(code).toContain("onSwitchRoute={undefined}");
  });
});
