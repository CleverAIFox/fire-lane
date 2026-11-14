/**
 * opsUplink.test.ts — **「끝에 끊김」 을 가짜 타이머로 가른다.**  (PLAN #234 · `app/useOpsUplink.ts::startUplink`)
 *
 * ★ 왜 생겼나. 중개자를 띄운 날(DECISIONS §763) 관제 화면의 시연 차량이 끝에 「끊김」 이 됐고, 원인을
 *   「탭 타이머가 느려 `HB_TTL_MS`(4초)를 넘긴 것으로 보인다 — 확인은 안 했다」 로 적어 뒀다. 여기서 확인한다.
 *   먼저 자가 틀렸다 — 관제의 「끊김」 은 `HB_TTL_MS` 가 아니라 **`UNIT_STALE_MS`(5초)** 다(`unitStale`).
 *   `HB_TTL_MS` 는 반대쪽(내비가 관제를 보는 자)이다.
 *
 * 가설 넷을 가른다(셋은 행이 적었고 넷째는 코드를 읽다 나왔다):
 *     ㉮ 주기 대 자       앞 탭이면 0.5초 대 5초 — 안 끊긴다
 *     ㉯ 뒤 탭 1초 묶임   1초 대 5초 — **안 끊긴다.** 5분 넘게 뒤에 있으면 1분 묶임이 되고 그때는 **끊긴다**
 *     ㉰ 재접속 간격      1초 + 악수 + 0 — 악수가 4초를 넘겨야 보인다
 *     ㉱ 인사 없이 떠남   `bye` 가 안 닿으면(탭 죽음 · 망 끊김) 그 차는 **영원히 「끊김」** 으로 남는다 — 「끝에」 와 맞는다
 *   그리고 행이 적은 `at` — 관제의 `hb.at` 을 내 시계와 빼던 것(기계 둘의 시계 어긋남)을 고쳤고 여기서 문다.
 *
 * ★ **브라우저의 묶임은 흉내다.** 크롬의 규칙(뒤 탭 = 1초에 한 번 깨움 · 5분 뒤 = 1분에 한 번)을 「타이머가 격자에서만
 *   깬다」 로 옮겼다. 실제 브라우저가 이대로인지는 사람이 본다(행의 도착 ①). 여기가 무는 것은 **그 격자에서 우리 수가 견디는가**다.
 *
 * IN    가짜 소켓 · 가짜 시계 · 격자(0 = 앞 탭 · 1,000 = 뒤 탭 · 60,000 = 5분 넘게 뒤)
 * OUT   관제 쪽에서 본 가장 긴 침묵(ms) · 「끊김」 이었던 시간(ms)
 * PARAM `STATE_MS` 500 · `RETRY_MS` 1,000 · `UNIT_STALE_MS` 5,000 · `HB_MS` 1,500 · `HB_TTL_MS` 4,000 — 전부 제품 상수를 읽는다
 * 밖    실제 브라우저의 묶임 규칙 · 실제 중개자(Cloudflare)의 지연 · 차 여러 대 · 30분 지속 — 사람 몫이다(도착 ②③)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  HB_MS, HB_TTL_MS, OPS_EMPTY, UNIT_STALE_MS, asNaviMsg, opsPresent, opsReduce, unitStale,
  type OpsState,
} from "../src/domain/opsProtocol";
import type { UnitSnapshot, VisDoc } from "../src/app/useOpsUplink";

const OPS_APP = Object.values(import.meta.glob(
  "../src/OpsApp.tsx", { query: "?raw", import: "default", eager: true },
))[0] as string;

/** 가짜 소켓. 붙어 있을 때 보낸 글자는 곧장 `wire` 로 간다(중개자는 글자를 그대로 옮긴다). */
class FakeWS {
  static OPEN = 1;
  static made: FakeWS[] = [];
  static wire: (text: string) => void = () => {};
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) { FakeWS.made.push(this); }
  open() { this.readyState = 1; this.onopen?.(); }
  send(s: string) { if (this.readyState === 1) FakeWS.wire(s); }
  /** 서버가 끊었다 — 브라우저가 `onclose` 를 준다 */
  close() { this.readyState = 3; this.onclose?.(); }
  /** 탭이 죽었다 · 망이 끊겼다 — **아무 말도 못 하고** 사라진다 */
  vanish() { this.readyState = 3; }
  recv(o: unknown) { this.onmessage?.({ data: JSON.stringify(o) }); }
  static get last(): FakeWS { return FakeWS.made[FakeWS.made.length - 1]; }
}

/** 탭 하나의 타이머 격자. 0 이면 안 묶인다. 이미 걸린 타이머는 그대로 두고 **다음 것부터** 격자를 탄다. */
const tab = { grid: 0 };
function installThrottle() {
  const st = globalThis.setTimeout, ct = globalThis.clearTimeout;     // 가짜 시계의 것
  const due = (ms: number) => {
    const at = Date.now() + ms;
    return (tab.grid > 0 ? Math.ceil(at / tab.grid) * tab.grid : at) - Date.now();
  };
  const live = new Map<number, ReturnType<typeof setTimeout>>();
  let seq = 0;
  vi.stubGlobal("setTimeout", (fn: () => void, ms = 0) => st(fn, due(ms)));
  vi.stubGlobal("setInterval", (fn: () => void, ms = 0) => {
    const id = ++seq;
    const arm = () => live.set(id, st(() => { fn(); if (live.has(id)) arm(); }, due(ms)));
    arm();
    return id;
  });
  vi.stubGlobal("clearInterval", (id: number) => { const h = live.get(id); if (h !== undefined) ct(h); live.delete(id); });
}

const SNAP: UnitSnapshot = {
  vehicle: "펌프차", station: "지산", incident: null, pos: [126.92, 35.15], brg: 0,
  status: "guiding", title: "안내 중", remainM: 1200, etaText: "3분", demo: true,
  route: [[126.92, 35.15], [126.93, 35.16]],
};

/** 관제 쪽 — `OpsApp.tsx` 의 접기를 그대로 쓴다(`opsReduce` · `unitStale`). 시계는 관제의 것이다. */
class Board {
  st: OpsState = OPS_EMPTY;
  got: Array<ReturnType<typeof asNaviMsg>> = [];
  /** 상태 두 통 사이의 가장 긴 틈(ms) — 도착 시각으로 잰다 */
  gap = 0;
  private lastAt: number | null = null;
  constructor() {
    FakeWS.wire = (t) => {
      const m = asNaviMsg(JSON.parse(t));
      this.got.push(m);
      if (!m) return;
      if (m.t === "state") { if (this.lastAt != null) this.gap = Math.max(this.gap, Date.now() - this.lastAt); this.lastAt = Date.now(); }
      this.st = opsReduce(this.st, m, Date.now());
    };
  }
  unit(id: string) { return this.st.units[id]; }
}

/** 0.1초마다 관제 화면을 본다. 가장 긴 침묵과 「끊김」 이었던 시간을 센다. */
async function watch(b: Board, unit: string, ms: number) {
  let stale = 0;
  b.gap = 0;
  for (let t = 0; t < ms; t += 100) {
    await vi.advanceTimersByTimeAsync(100);
    const u = b.unit(unit);
    if (u && unitStale(u, Date.now())) stale += 100;
  }
  const u = b.unit(unit);
  return { stale, gap: Math.max(b.gap, u ? Date.now() - u.heardAt : 0) };
}

async function load() {
  vi.resetModules();
  vi.doMock("../src/config", () => ({ OPS_URL: "ws://broker.test", OPS_TOKEN: "" }));
  const up = await import("../src/app/useOpsUplink");
  const link = await import("../src/infra/opsLink");
  return { ...up, RETRY_MS: link.RETRY_MS };
}

const MIN = 60_000;

beforeEach(() => {
  FakeWS.made = [];
  tab.grid = 0;
  vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-14T00:00:00Z"));
  installThrottle();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.doUnmock("../src/config");
});

describe("㉮ 앞 탭 — 주기 0.5초 대 「끊김」 자 5초", () => {
  it("5분 동안 한 번도 안 끊긴다 · 가장 긴 침묵이 주기다", async () => {
    const { startUplink, STATE_MS } = await load();
    const b = new Board();
    const u = startUplink("navi-a", () => SNAP);
    FakeWS.last.open();
    const r = await watch(b, "navi-a", 5 * MIN);
    expect(r.stale).toBe(0);
    expect(r.gap).toBeLessThanOrEqual(STATE_MS);
    u.stop();
  });
});

describe("㉯ 뒤 탭 — 타이머가 묶인다", () => {
  it("★ 1초 묶임(뒤로 간 지 5분 안)은 **안 끊긴다** — 침묵 1초 대 자 5초", async () => {
    const { startUplink } = await load();
    const b = new Board();
    const u = startUplink("navi-a", () => SNAP);
    FakeWS.last.open();
    tab.grid = 1000;
    const r = await watch(b, "navi-a", 5 * MIN);
    expect(r.stale).toBe(0);
    expect(r.gap).toBe(1000);
    // 남는 폭 — 묶인 채로 네 통을 연달아 잃어도 자를 안 넘긴다
    expect(Math.floor(UNIT_STALE_MS / 1000) - 1).toBe(4);
    u.stop();
  });

  it("★ 1분 묶임(뒤로 간 지 5분 넘음)은 **끊긴다** — 이것이 「끝에 끊김」 의 한 갈래다", async () => {
    const { startUplink } = await load();
    const b = new Board();
    const u = startUplink("navi-a", () => SNAP);
    FakeWS.last.open();
    await watch(b, "navi-a", 2000);
    tab.grid = MIN;
    const r = await watch(b, "navi-a", 5 * MIN);
    expect(r.gap).toBe(MIN);
    // 1분 중 5초만 살아 있다 — 화면은 거의 내내 「끊김」 이다
    expect(r.stale / (5 * MIN)).toBeGreaterThan(0.85);
    u.stop();
  });

  it("★ 앞으로 돌아오는 **그 순간** 한 통이 간다 — 묶인 타이머(최대 1분 뒤)를 안 기다린다", async () => {
    const { startUplink } = await load();
    const b = new Board();
    let onVis: (() => void) | null = null;
    const doc = {
      visibilityState: "hidden",
      addEventListener: (_: string, fn: () => void) => { onVis = fn; },
      removeEventListener: () => { onVis = null; },
    };
    const u = startUplink("navi-a", () => SNAP, { doc: doc as unknown as VisDoc });
    FakeWS.last.open();
    tab.grid = MIN;
    await watch(b, "navi-a", 2 * MIN + 10_000);            // 격자 위 10초 — 다음 타이머는 50초 뒤다
    expect(unitStale(b.unit("navi-a"), Date.now())).toBe(true);
    // 숨은 채로는 안 보낸다(가시성 이벤트가 숨는 쪽으로도 온다)
    const before = b.got.length;
    onVis!();
    expect(b.got.length).toBe(before);
    tab.grid = 0; doc.visibilityState = "visible";
    onVis!();
    expect(b.got.length).toBe(before + 1);
    expect(unitStale(b.unit("navi-a"), Date.now())).toBe(false);
    u.stop();
    expect(onVis).toBeNull();                               // 떠날 때 듣기를 거둔다
  });
});

describe("㉰ 재접속 — 간격 1초 + 악수", () => {
  /** 끊긴 뒤 악수가 `h` ms 걸렸을 때 관제가 본 침묵과 끊김 */
  async function reconnect(h: number, grid = 0) {
    const { startUplink, RETRY_MS } = await load();
    const b = new Board();
    const u = startUplink("navi-a", () => SNAP);
    FakeWS.last.open();
    tab.grid = grid;
    await watch(b, "navi-a", 3000);
    const n = FakeWS.made.length;
    FakeWS.last.close();
    const w1 = await watch(b, "navi-a", RETRY_MS + (grid || 0));
    expect(FakeWS.made.length).toBe(n + 1);                 // 다시 붙으러 갔다
    const w2 = await watch(b, "navi-a", h);
    const at = b.got.length;
    FakeWS.last.open();
    const first = b.got[at];
    const w3 = await watch(b, "navi-a", 3000);
    u.stop();
    return { stale: w1.stale + w2.stale + w3.stale, gap: Math.max(w1.gap, w2.gap, w3.gap), first, RETRY_MS };
  }

  it("★ 악수가 3초여도 안 끊긴다 — 침묵 = 1초 + 악수 (붙는 순간 보내므로 주기를 안 더한다)", async () => {
    for (const h of [0, 300, 1000, 3000]) {
      const r = await reconnect(h);
      expect(r.stale, `악수 ${h}ms`).toBe(0);
      expect(r.gap, `악수 ${h}ms`).toBeLessThanOrEqual(r.RETRY_MS + h + 500);
    }
  });

  it("★ 간격 + 악수가 자(5초)를 넘으면 **끊김이 보인다** — 재접속이 느려지면 이렇게 된다", async () => {
    const r = await reconnect(4500);
    expect(r.gap).toBeGreaterThan(UNIT_STALE_MS);
    expect(r.stale).toBeGreaterThan(0);
  });

  it("뒤 탭(1초 묶임)에서 재접속해도 안 끊긴다 — 재접속 타이머도 격자를 탄다", async () => {
    const r = await reconnect(1000, 1000);
    expect(r.stale).toBe(0);
  });

  it("★ 붙는 순간의 첫 통에 **경로가 실린다** — 중개자의 기억은 차가 떠날 때 비워진다", async () => {
    const r = await reconnect(300);
    expect(r.first?.t).toBe("state");
    expect((r.first as { route?: unknown }).route).toEqual(SNAP.route);
  });

  it("★ 수의 관계 — 재접속 간격 + 묶인 주기 뒤에도 악수에 2초가 남는다", async () => {
    const { RETRY_MS, STATE_MS } = await load();
    // 뒤 탭이면 재접속 타이머는 최대 `RETRY_MS + 1초`(격자 맞춤)다. 붙는 순간 보내므로 주기는 안 더한다.
    expect(UNIT_STALE_MS - (RETRY_MS + 1000)).toBeGreaterThanOrEqual(2000);
    // 자는 주기의 열 배 · 묶인 주기(1초)의 다섯 배다
    expect(UNIT_STALE_MS / STATE_MS).toBeGreaterThanOrEqual(10);
    expect(UNIT_STALE_MS / Math.max(STATE_MS, 1000)).toBeGreaterThanOrEqual(5);
  });
});

describe("㉱ 인사 없이 떠남 — 「끝에 끊김」 의 다른 갈래", () => {
  it("★ `bye` 가 닿으면 상황판에서 **빠진다**", async () => {
    const { startUplink } = await load();
    const b = new Board();
    const u = startUplink("navi-a", () => SNAP);
    FakeWS.last.open();
    await watch(b, "navi-a", 2000);
    u.stop();
    expect(b.unit("navi-a")).toBeUndefined();
  });

  it("★ `bye` 가 안 닿으면(탭 죽음 · 망 끊김) 5초 뒤 「끊김」 이 되고 **10분 뒤에도 그대로다** — 관제는 스스로 안 지운다", async () => {
    const { startUplink } = await load();
    const b = new Board();
    const u = startUplink("navi-a", () => SNAP);
    FakeWS.last.open();
    await watch(b, "navi-a", 2000);
    FakeWS.last.vanish();
    u.stop();                                               // 떠나며 `bye` 를 보내지만 소켓이 이미 죽었다
    await vi.advanceTimersByTimeAsync(UNIT_STALE_MS + 100);
    expect(unitStale(b.unit("navi-a"), Date.now())).toBe(true);
    await vi.advanceTimersByTimeAsync(10 * MIN);
    expect(b.unit("navi-a")).toBeDefined();
    expect(unitStale(b.unit("navi-a"), Date.now())).toBe(true);
  });
});

describe("`at` — 관제를 들은 시각은 **내 시계**다", () => {
  /** 관제 기계의 시계가 `skew` ms 어긋났을 때, 내비가 본 「관제 있음」 */
  async function present(skew: number) {
    const { startUplink } = await load();
    let heard: number | null = null;
    const u = startUplink("navi-a", () => SNAP, { hb: (t) => { heard = t; } });
    const ws = FakeWS.last; ws.open();
    const seen: boolean[] = [];
    for (let i = 0; i < 20; i++) {
      ws.recv({ t: "hb", ops: "ops-1", at: Date.now() + skew });
      await vi.advanceTimersByTimeAsync(HB_MS);
      seen.push(opsPresent(heard, Date.now()));
    }
    // 관제가 떠났다 — 더는 안 온다
    await vi.advanceTimersByTimeAsync(HB_TTL_MS + 100);
    const after = opsPresent(heard, Date.now());
    u.stop();
    return { during: seen.every(Boolean), after };
  }

  it("시계가 같으면 있는 동안 있고, 떠나면 4초 뒤 없다", async () => {
    expect(await present(0)).toEqual({ during: true, after: false });
  });
  it("★ 관제 시계가 **10초 늦어도** 있는 것으로 본다 — 종전에는 「관제 없음(시연)」 이었다", async () => {
    expect(await present(-10_000)).toEqual({ during: true, after: false });
  });
  it("★ 관제 시계가 **10초 빨라도** 떠나면 4초 뒤 없다 — 종전에는 14초 동안 남았다", async () => {
    expect(await present(+10_000)).toEqual({ during: true, after: false });
  });
});

describe("관제 심장박동(1.5초) 대 내비의 자(4초)", () => {
  it("`OpsApp` 이 `setInterval(hb, HB_MS)` 로 보낸다 — 아래 흉내가 그 꼴이다", () => {
    expect(OPS_APP).toMatch(/setInterval\(hb,\s*HB_MS\)/);
  });

  /** 관제 탭이 격자 `grid` 에 묶였을 때 내비가 본 「관제 있음」 이 꺼진 시간(ms) */
  async function absent(grid: number, ms: number) {
    const { startUplink } = await load();
    let heard: number | null = null;
    const u = startUplink("navi-a", () => SNAP, { hb: (t) => { heard = t; } });
    const ws = FakeWS.last; ws.open();
    const hb = () => ws.recv({ t: "hb", ops: "ops-1", at: Date.now() });
    hb();
    tab.grid = grid;                                        // 관제 탭의 타이머가 묶인다(내비는 시계만 읽는다)
    const t = setInterval(hb, HB_MS);
    let off = 0;
    for (let i = 0; i < ms; i += 100) {
      await vi.advanceTimersByTimeAsync(100);
      if (!opsPresent(heard, Date.now())) off += 100;
    }
    clearInterval(t);
    u.stop();
    return off;
  }

  it("앞 탭 · 1초 묶임(박동이 2초로 늘어난다) 모두 안 꺼진다", async () => {
    expect(await absent(0, 5 * MIN)).toBe(0);
    expect(await absent(1000, 5 * MIN)).toBe(0);
    expect(HB_TTL_MS).toBeGreaterThan(Math.ceil(HB_MS / 1000) * 1000);
  });

  it("★ 1분 묶임이면 꺼진다 — 관제 탭을 5분 넘게 뒤에 두면 내비가 「시연」 으로 떨어진다", async () => {
    expect(await absent(MIN, 5 * MIN) / (5 * MIN)).toBeGreaterThan(0.85);
  });
});
