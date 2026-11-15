/**
 * opsPinPanel.test.ts — **같은 차를 지도 핀과 상황판이 다르게 판정하던 결함을 가짜 타이머로 가른다.**  (PLAN #251 · `domain/unitBoard.ts`)
 *
 * ★ 왜 생겼나. 2026-11-15 관제 화면에서 지도 핀은 「시연 중」인데 차량 상황판은 「끊김」이었다. 잠시 뒤 둘 다 「시연 중」으로 돌아왔다.
 *   원인(읽었다): 상황판은 1초 시계(`now`)로 `unitChip(u, now)` → `unitStale`(마지막으로 들은 시각 + `UNIT_STALE_MS` 5초)를 **매번** 다시 판정하고,
 *   지도 핀(`OpsMap`)은 **끊김 판정이 아예 없었다** — 마지막 메시지의 `demo` 칸만 읽고 `units` 가 바뀔 때(메시지가 올 때)만 다시 그렸다.
 *   그래서 말이 끊긴 차는 핀이 마지막 상태(시연 중)로 **영원히** 남고 상황판만 「끊김」이 된다 — 「패널만 끊김」. 메시지가 오면 둘이 다시 맞는다.
 *
 * 고침: 끊김은 한 곳(`lostUnits` ← `unitStale`)이 정하고 상황판 칩(`unitChip`)과 핀(`pinLook`)이 **같은 `chipOf`** 를 읽는다.
 *   정본은 상황판 쪽이다(마지막으로 들은 **내 시계** `heardAt` + 1초 재평가 — #234 가 이미 `hb.at`(남의 시계)을 내 시계로 바꿨다). 핀에는 시계를 주지 않는다 —
 *   `lost` 는 **글자**(끊긴 차 이름 목록)라 끊김이 **바뀔 때만** 새 값이고 지도 효과가 매초 돌지 않는다.
 *
 * 묻는 것: ① 격자(나이 × 시연 × 출동)에서 핀과 칩이 어느 쪽으로도 안 갈리나 — 「패널만 끊김」 · 「핀만 끊김」 둘 다 0
 *          ② 옛 규칙(핀이 `demo` 만 읽는다)은 같은 격자에서 갈린다 — 결함의 재현
 *          ③ 핀에 다른 시각을 주면 갈린다 — 둘이 **같은 `now`** 를 읽어야 하는 이유
 *          ④ 소스 문(핀이 끊김을 스스로 계산하지 않는다 · 효과가 `lost` 에 반응한다 · 상황판 시계 1초)
 *          ⑤ 5분 동안 효과가 도는 횟수 — 끊김이 바뀔 때만이다
 *          ⑥ 관제사가 보는 차 수 — 핀(살아 있는 것)의 수가 상황판 합계와 같다
 * IN    가짜 시계 · 합성 차량 목록
 * 밖    실제 지도(MapLibre)의 그리기 · 실제 브라우저의 타이머 묶임 — 핀의 DOM 은 `pinLook` 이 낸 값을 칠할 뿐이다(소스 문으로 본다)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UNIT_STALE_MS, type Unit } from "../src/domain/opsProtocol";
import { chipOf, liveCounts, lostUnits, pinLook, unitChip } from "../src/domain/unitBoard";

const SRC = (g: Record<string, unknown>) => Object.values(g)[0] as string;
const OPS_MAP = SRC(import.meta.glob("../src/components/OpsMap.tsx", { query: "?raw", import: "default", eager: true }));
const OPS_APP = SRC(import.meta.glob("../src/OpsApp.tsx", { query: "?raw", import: "default", eager: true }));

const T0 = 1_800_000_000_000;
beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(T0); });
afterEach(() => { vi.useRealTimers(); });

function unit(name: string, heardAgoMs: number, demo: boolean, remainM: number | null): Unit {
  return {
    unit: name, route: null, routeRev: 0, heardAt: Date.now() - heardAgoMs,
    last: { t: "state", unit: name, vehicle: `펌프차(${name})`, demo, remainM, pos: [126.92, 35.15], brg: 0 } as unknown as Unit["last"],
  };
}
const AGES = [0, 1_000, UNIT_STALE_MS - 1, UNIT_STALE_MS, UNIT_STALE_MS + 1, 6_000, 30_000, 300_000];
const GRID = AGES.flatMap((a) => [true, false].flatMap((d) => [null, 120].map((r) => ({ a, d, r }))));

describe("지도 핀과 상황판은 같은 값을 읽는다", () => {
  it("격자 전부에서 핀과 칩이 어느 쪽으로도 안 갈린다(패널만 끊김 0 · 핀만 끊김 0)", () => {
    let panelOnly = 0, pinOnly = 0;
    for (const { a, d, r } of GRID) {
      const u = unit("u", a, d, r);
      const now = Date.now();
      const chip = unitChip(u, now);
      const pin = pinLook(u, lostUnits([u], now).split("|").includes("u"));
      if (chip.kind === "lost" && pin.kind !== "lost") panelOnly += 1;
      if (pin.kind === "lost" && chip.kind !== "lost") pinOnly += 1;
      expect(pin.kind, `나이 ${a} 시연 ${d} 남은 ${r}`).toBe(chip.kind);
      expect(pin.text.startsWith("끊김")).toBe(chip.label === "끊김");
      expect(pin.text.startsWith("시연 중")).toBe(chip.label === "시연 중");
    }
    expect(panelOnly).toBe(0);
    expect(pinOnly).toBe(0);
  });

  it("시연 차가 말이 끊기면 핀도 「끊김」이다 — 2026-11-15 관제 화면의 재현", () => {
    const u = unit("demo-1", 0, true, 1900);
    expect(pinLook(u, false).kind).toBe("demo");
    vi.advanceTimersByTime(UNIT_STALE_MS + 1_000);                  // 메시지 없이 6초
    const lost = lostUnits([u], Date.now()).split("|").includes("demo-1");
    expect(unitChip(u, Date.now()).label).toBe("끊김");
    expect(pinLook(u, lost).text).toBe("끊김 · 펌프차(demo-1)");
    expect(pinLook(u, lost).fill).toBe("#9ca3af");
  });
});

describe("옛 규칙은 같은 격자에서 갈린다(결함의 재현)", () => {
  /** 고치기 전 `OpsMap` — 마지막 메시지의 `demo` 칸만 읽는다. 시계가 없다. */
  const oldPinKind = (u: Unit): string => (u.last.demo ? "demo" : u.last.remainM != null ? "dispatching" : "idle");

  it("패널만 끊김 — 말이 5초를 넘게 끊긴 차에서 옛 핀은 안 끊긴다", () => {
    const diverged = GRID.filter(({ a, d, r }) => {
      const u = unit("u", a, d, r);
      return unitChip(u, Date.now()).kind === "lost" && oldPinKind(u) !== "lost";
    });
    expect(diverged.length).toBe(GRID.filter((g) => g.a > UNIT_STALE_MS).length);   // 5초 넘는 격자 칸 전부가 갈린다
    expect(diverged.length).toBeGreaterThan(0);
  });

  it("핀만 끊김 — 핀에 상황판보다 앞선 시각을 주면 핀이 먼저 끊긴다(그래서 같은 `now` 다)", () => {
    const u = unit("u", UNIT_STALE_MS - 500, false, 120);            // 상황판 시각에서는 아직 안 끊겼다
    const panelNow = Date.now();
    expect(unitChip(u, panelNow).kind).toBe("dispatching");
    const skew = 1_000;                                               // 핀이 다른 시계(1초 앞)를 읽으면
    const pinLost = lostUnits([u], panelNow + skew).split("|").includes("u");
    expect(pinLook(u, pinLost).kind).toBe("lost");                    // 핀만 끊김
  });
});

describe("소스 문 — 핀은 끊김을 스스로 계산하지 않는다", () => {
  it("OpsMap 이 시계 · 끊김 자를 안 읽는다", () => {
    for (const bad of ["unitStale", "heardAt", "UNIT_STALE_MS", "HB_TTL_MS", "Date.now"]) {
      expect(OPS_MAP.includes(bad), `OpsMap 이 ${bad} 를 읽는다 — 끊김은 한 곳이 정한다`).toBe(false);
    }
    expect(OPS_MAP).toContain("pinLook(");
  });
  it("차량 효과가 `lost` 에 반응한다 · 상황판은 같은 `now` 로 `lostUnits` 를 부른다 · 1초 시계가 있다", () => {
    expect(OPS_MAP).toMatch(/\[props\.units,\s*props\.lost\]/);
    expect(OPS_APP).toContain("lostUnits(units, now)");
    expect(OPS_APP).toContain("unitChip(u, now)");
    expect(OPS_APP).toMatch(/setInterval\(\(\)\s*=>\s*setNow\(Date\.now\(\)\),\s*1000\)/);
    expect(OPS_APP).toContain("lost={lostUnits(units, now)}");   // 끊김은 상황판과 같은 `now` 로 한 곳에서 계산해 글자로 넘긴다
  });
});

describe("효과가 도는 횟수와 관제사가 보는 차 수", () => {
  it("5분 동안 `lost` 글자가 바뀌는 횟수 = 끊김이 바뀐 횟수(매초 300번이 아니다)", () => {
    const values: string[] = [];
    let heardB = Date.now();
    for (let s = 0; s < 300; s += 1) {
      const now = Date.now();
      if (s < 120 || s >= 180) heardB = now;                         // 둘째 차는 120~180초에 말이 끊긴다
      const units = [unit("a", 0, false, 100), { ...unit("b", 0, true, 100), heardAt: heardB }];
      values.push(lostUnits(units, now));
      vi.advanceTimersByTime(1_000);
    }
    const flips = values.filter((v, i) => i > 0 && v !== values[i - 1]).length;
    expect(flips).toBe(2);                                            // 끊김 한 번 · 복구 한 번
    expect(values.length).toBe(300);                                  // 시계는 매초 돌아도 효과 입력은 두 번만 바뀐다
  });

  it("살아 있는 핀의 수가 상황판 합계와 같다 — 관제사가 지도와 패널에서 다른 대수를 읽지 않는다", () => {
    const units = [unit("a", 0, false, 100), unit("b", 0, true, 100), unit("c", 9_000, false, 100), unit("d", 12_000, true, null)];
    const now = Date.now();
    const lost = new Set(lostUnits(units, now).split("|").filter(Boolean));
    const alivePins = units.filter((u) => pinLook(u, lost.has(u.unit)).kind !== "lost").length;
    const { real, demo } = liveCounts(units, now);
    expect(alivePins).toBe(real + demo);
    expect(chipOf(units[2], true).kind).toBe("lost");
  });
});
