/**
 * opsLink.test.ts — 문 하나 뒤의 전송 둘. (DECISIONS §343 · `infra/opsLink.ts`)
 *
 * ★ 종전에 이 파일은 `BroadcastChannel` 하나였고 **시험이 없었다.** 그래서
 *   「같은 브라우저의 탭끼리만 닿는다」는 사실이 코드에만 있었고, 그것이
 *   출동에 모자란다는 판단은 아무 데도 없었다.
 *
 * ★ 가짜 소켓으로 잰다. 진짜 서버를 띄우면 시험이 포트와 시각에 매이고,
 *   매인 시험은 CI 에서 **이따금** 빨개진다 — 그런 빨강은 아무도 안 읽는다.
 *   서버 쪽 실물 왕복은 `tests/test_ops.py` 가 든다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/** 가짜 WebSocket. 열림·닫힘·메시지를 시험이 손으로 민다. */
class FakeWS {
  static OPEN = 1;
  static made: FakeWS[] = [];
  readyState = 0;
  sent: string[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) { FakeWS.made.push(this); }
  open() { this.readyState = 1; }
  send(s: string) { this.sent.push(s); }
  close() { this.closed = true; this.readyState = 3; this.onclose?.(); }
}

async function load(url: string) {
  vi.resetModules();
  vi.doMock("../src/config", () => ({ OPS_URL: url }));
  return (await import("../src/infra/opsLink")) as typeof import("../src/infra/opsLink");
}

beforeEach(() => {
  FakeWS.made = [];
  vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.doUnmock("../src/config");
});

describe("① 어느 전송을 고르는가 — 설정이 고른다", () => {
  it("주소가 있으면 WebSocket 으로 간다", async () => {
    const { openLink } = await load("ws://broker.test");
    openLink(() => {}, { kind: "ops" });
    expect(FakeWS.made).toHaveLength(1);
  });

  it("주소가 없으면 소켓을 안 만든다 — 탭끼리만 닿는 옛 전송이다", async () => {
    const { openLink } = await load("");
    vi.stubGlobal("BroadcastChannel", undefined);
    const l = openLink(() => {}, { kind: "ops" });
    expect(FakeWS.made).toHaveLength(0);
    expect(l.available).toBe(false);   // 채널도 없으면 「관제 없음」이다
  });

  it("★ 부르는 쪽은 어느 전송인지 안 적는다 — 두 호출부가 어긋날 자리가 없다", async () => {
    const { openLink } = await load("ws://broker.test");
    const a = openLink(() => {}, { kind: "ops" });
    const b = openLink(() => {}, { kind: "unit", unit: "navi-7" });
    expect(typeof a.send).toBe("function");
    expect(typeof b.send).toBe("function");
  });
});

describe("② 문이 갈린다 — 관제와 차가 다른 주소로 붙는다", () => {
  it("관제는 /ops", async () => {
    const { openLink } = await load("ws://broker.test");
    openLink(() => {}, { kind: "ops" });
    expect(FakeWS.made[0].url).toBe("ws://broker.test/ops");
  });

  it("차는 /unit/<id>", async () => {
    const { openLink } = await load("ws://broker.test");
    openLink(() => {}, { kind: "unit", unit: "navi-7" });
    expect(FakeWS.made[0].url).toBe("ws://broker.test/unit/navi-7");
  });

  it("★ 꼬리 슬래시가 겹치지 않는다 — `//ops` 는 다른 경로다", async () => {
    const { openLink } = await load("ws://broker.test/");
    openLink(() => {}, { kind: "ops" });
    expect(FakeWS.made[0].url).toBe("ws://broker.test/ops");
  });

  it("★ 차 id 를 그대로 붙이지 않는다 — 공백·슬래시가 경로를 바꾼다", async () => {
    const { openLink } = await load("ws://broker.test");
    openLink(() => {}, { kind: "unit", unit: "a/b c" });
    expect(FakeWS.made[0].url).toBe("ws://broker.test/unit/a%2Fb%20c");
  });
});

describe("③ 보내기 — 쌓아 두지 않는다", () => {
  it("열려 있으면 JSON 으로 보낸다", async () => {
    const { openLink } = await load("ws://broker.test");
    const l = openLink(() => {}, { kind: "ops" });
    FakeWS.made[0].open();
    l.send({ a: 1 });
    expect(FakeWS.made[0].sent).toEqual(['{"a":1}']);
  });

  it("★ 안 열렸으면 **버린다.** 쌓아 두면 붙는 순간 지난 위치가 쏟아진다", async () => {
    const { openLink } = await load("ws://broker.test");
    const l = openLink(() => {}, { kind: "unit", unit: "a" });
    l.send({ a: 1 });
    l.send({ a: 2 });
    FakeWS.made[0].open();
    expect(FakeWS.made[0].sent).toEqual([]);   // 붙은 뒤에도 안 흘러나온다
    l.send({ a: 3 });
    expect(FakeWS.made[0].sent).toEqual(['{"a":3}']);
  });

  it("available 이 소켓의 실제 상태를 본다 — 「붙었다」를 믿지 않는다", async () => {
    const { openLink } = await load("ws://broker.test");
    const l = openLink(() => {}, { kind: "ops" });
    expect(l.available).toBe(false);
    FakeWS.made[0].open();
    expect(l.available).toBe(true);
    FakeWS.made[0].close();
    expect(l.available).toBe(false);
  });
});

describe("④ 받기", () => {
  it("JSON 을 풀어서 준다 — 서버는 글자만 옮긴다", async () => {
    const got: unknown[] = [];
    const { openLink } = await load("ws://broker.test");
    openLink((d) => got.push(d), { kind: "ops" });
    FakeWS.made[0].open();
    FakeWS.made[0].onmessage?.({ data: '{"t":"hb","at":5}' });
    expect(got).toEqual([{ t: "hb", at: 5 }]);
  });

  it("★ 깨진 글자는 버린다 — 여기서 던지면 연결이 죽는다", async () => {
    const got: unknown[] = [];
    const { openLink } = await load("ws://broker.test");
    openLink((d) => got.push(d), { kind: "ops" });
    FakeWS.made[0].open();
    expect(() => FakeWS.made[0].onmessage?.({ data: "JSON 이 아니다" })).not.toThrow();
    expect(got).toEqual([]);
  });
});

describe("⑤ 재접속 — 출동 중에 끊기면 다시 붙는다", () => {
  it("끊기면 1초 뒤에 다시 붙는다", async () => {
    const { openLink } = await load("ws://broker.test");
    openLink(() => {}, { kind: "unit", unit: "a" });
    FakeWS.made[0].open();
    FakeWS.made[0].close();
    expect(FakeWS.made).toHaveLength(1);
    vi.advanceTimersByTime(1000);
    expect(FakeWS.made).toHaveLength(2);
  });

  it("★ 간격이 늘지 않는다 — 2·4·8초로 늘면 관제가 그동안 차를 잃는다", async () => {
    const { openLink } = await load("ws://broker.test");
    openLink(() => {}, { kind: "unit", unit: "a" });
    for (let i = 0; i < 4; i++) {
      FakeWS.made[FakeWS.made.length - 1].close();
      vi.advanceTimersByTime(1000);
    }
    expect(FakeWS.made).toHaveLength(5);   // 매번 1초면 넷 더 붙는다
  });

  it("★ 닫은 뒤에는 다시 안 붙는다 — 화면을 떠났는데 계속 붙으면 연결이 샌다", async () => {
    const { openLink } = await load("ws://broker.test");
    const l = openLink(() => {}, { kind: "unit", unit: "a" });
    FakeWS.made[0].open();
    l.close();
    vi.advanceTimersByTime(10_000);
    expect(FakeWS.made).toHaveLength(1);
  });

  it("★ 주소가 틀려 생성이 던져도 다시 시도한다 — .env 를 고치는 동안", async () => {
    vi.stubGlobal("WebSocket", class { constructor() { throw new Error("bad url"); } });
    const { openLink } = await load("ws://broker.test");
    expect(() => openLink(() => {}, { kind: "ops" })).not.toThrow();
    vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
    vi.advanceTimersByTime(1000);
    expect(FakeWS.made).toHaveLength(1);
  });
});

// ── 2026-10-12 (DECISIONS §483) ────────────────────────────────────
describe("탭 id — 관제가 차를 가른다", () => {
  it("★ 접두를 지키고 **서로 다르다** — 겹치면 두 차가 한 차로 보인다", async () => {
    const { newId } = await import("../src/infra/opsLink");
    const ids = new Set<string>();
    for (let i = 0; i < 2000; i++) {
      const id = newId("navi");
      expect(id.startsWith("navi-")).toBe(true);
      ids.add(id);
    }
    // 같은 밀리초에 여러 개를 만들어도 뒤의 글자들이 가른다.
    // 2,000개에서 겹침이 몇이라도 나오면 그 글자가 모자란 것이다.
    expect(ids.size).toBe(2000);
  });

  // ★ 2026-10-12 (DECISIONS §506). **위 시험은 주사위였다.**
  //   `beforeEach` 가 가짜 타이머를 켜므로 `Date.now()` 가 얼어 있고, 그러면
  //   2,000개를 가르는 것은 난수뿐이었다 — 다섯 글자로는 **2.4% 가 겹친다.**
  //   2026-10-12 `contract-shared` 가 `expected 1999 to be 2000` 으로 죽었다.
  //
  //   위 시험은 **안 낮췄다**(느슨해지는 쪽이다). 대신 **운을 빼고** 같은 것을
  //   다시 묻는다 — 난수를 상수로 못 박으면 남는 가름은 차례 하나뿐이다.
  //   위가 확률로 묻는 것을 이것이 **확정으로** 묻는다.
  it("★ 난수가 **죽어도** 서로 다르다 — 한 탭 안의 겹침은 운이 아니라 0 이어야 한다", async () => {
    const { newId } = await import("../src/infra/opsLink");
    const spy = vi.spyOn(Math, "random").mockReturnValue(0.5);
    try {
      const ids = new Set<string>();
      for (let i = 0; i < 2000; i++) ids.add(newId("navi"));
      expect(ids.size).toBe(2000);
    } finally {
      spy.mockRestore();
    }
  });

  it("난수 글자 수가 **모자라지 않는다** — 둥근 값이 나와도", async () => {
    const { newId } = await import("../src/infra/opsLink");
    // Math.random() 이 0.5 면 "0.i" 라 종전 자르기로는 한 글자만 나왔다.
    const spy = vi.spyOn(Math, "random").mockReturnValue(0.5);
    try {
      // `ops-` + 시각 4 + 차례 ≥1 + 난수 8 → 최소 17 자
      expect(newId("ops").length).toBeGreaterThanOrEqual(17);
    } finally {
      spy.mockRestore();
    }
  });

  it("짧고, 전송이 깨질 글자가 없다", async () => {
    const { newId } = await import("../src/infra/opsLink");
    const id = newId("ops");
    // 관제 화면이 이 id 를 줄에 얹는다 — 공백·따옴표·줄바꿈이 끼면 꼴이 깨진다
    expect(id).toMatch(/^ops-[0-9a-z]+$/);
    expect(id.length).toBeLessThan(24);
  });
});
