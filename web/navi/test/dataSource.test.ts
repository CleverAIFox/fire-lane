/**
 * dataSource.test.ts — `web/data` 를 읽는 셋. **서버는 없다.** (DECISIONS §483)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 센 마지막 다섯 중 셋이 여기였다 —
 * `loadAll` · `loadFleet` · `loadHistory`. 묶음을 받는 **첫 관문**이고,
 * 그 셋이 가르는 것은 「없어도 도는 것」과 「없으면 죽어야 하는 것」이다.
 *
 * ★ 그 가름이 선언으로만 있었다. `loadAll` 머리말이 **「style 이 없으면
 *   죽는다. 기본색을 두면 `config.js` 를 아무도 안 고치고 그 기본색이
 *   화면에 남는다」**고 적는데, 그 죽음을 미는 자가 없었다. 누가 기본색을
 *   슬쩍 넣어도 아무도 안 운다.
 *
 * ★ `fetch` 를 가짜로 세운다. 진짜 서버를 띄우면 시험이 포트와 파일 배치에
 *   매이고, 매인 시험은 CI 에서 이따금 빨개진다 — 그런 빨강은 아무도 안
 *   읽는다(`opsLink.test.ts` 가 가짜 소켓을 쓰는 것과 같은 사유).
 *
 * 밖    **발행물이 옳은가는 안 본다** — 그것은 `tests/test_contract.py` 와
 *       `dataBase.test.ts`(주소) 소관이다. 여기가 드는 것은 **없을 때의
 *       처신** 하나다.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

/** 최소한의 그래프 — `style` 이 있어야 `loadAll` 이 산다. */
const GRAPH = { style: { clear: "#1a9660" }, edges: [], nodes: [], turns: [] };
const SPEC = { kind: "중형펌프차", width_m: 2.5 };

/**
 * 가짜 `web/data`. 표에 없는 이름은 **404** 다.
 *
 * ★ 모듈을 **다시 들인다.** `dataSource` 는 적재 시각에 `dataBase()` 를
 *   부르고 그 함수가 `location` 을 본다 — 들인 뒤에 가짜를 세우면 늦다
 *   (`dataBase.test.ts` 가 같은 수법을 쓴다).
 */
async function serve(files: Record<string, unknown>) {
  const asked: string[] = [];
  vi.resetModules();
  vi.stubEnv("BASE_URL", "/fire-lane/navi/");
  vi.stubGlobal("location", { origin: "https://x.github.io" } as Location);
  vi.stubGlobal("fetch", (url: string) => {
    const name = url.split("/").pop() ?? "";
    asked.push(name);
    const body = files[name];
    if (body === undefined) {
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.reject() });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
  });
  const mod = await import("../src/infra/dataSource");
  return { asked, ...mod };
}

/** 다 있는 상태. 갈래마다 여기서 하나씩 뺀다. */
const ALL: Record<string, unknown> = {
  "navi_graph.json": GRAPH,
  "vehicle_spec.json": SPEC,
  "view.json": { center: [126.9266, 35.151], zoom: 15 },
  "dest.geojson": { type: "FeatureCollection", features: [] },
  "route_vehicle.json": {},
  "stations.geojson": { type: "FeatureCollection", features: [] },
  "context.geojson": { type: "FeatureCollection", features: [] },
  "fleet.json": { vehicles: [] },
  "history.geojson": { type: "FeatureCollection", features: [] },
};

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("① 묶음 — 다 있으면 다 싣는다", () => {
  it("일곱을 읽고 그대로 넘긴다", async () => {
    const { asked, loadAll } = await serve(ALL);
    const b = await loadAll();
    expect(b.graph).toEqual(GRAPH);
    expect(b.spec).toEqual(SPEC);
    expect(b.stations).not.toBeNull();
    expect(b.context).not.toBeNull();
    // 사본을 만들지 않는다 — 읽은 것이 그대로 간다
    expect(asked).toContain("navi_graph.json");
    expect(asked).toContain("route_vehicle.json");
  });
});

describe("② 없으면 죽는 것 · 없어도 도는 것", () => {
  it("★ `style` 이 없으면 **죽는다** — 기본색을 두면 그 색이 화면에 남는다", async () => {
    const { loadAll } = await serve({ ...ALL, "navi_graph.json": { edges: [], nodes: [] } });
    await expect(loadAll()).rejects.toThrow(/style/);
  });

  it("죽을 때 **고치는 길**을 말한다", async () => {
    const { loadAll } = await serve({ ...ALL, "navi_graph.json": { edges: [] } });
    await expect(loadAll()).rejects.toThrow(/publish_navi/);
  });

  it.each(["navi_graph.json", "vehicle_spec.json", "view.json", "dest.geojson",
    "route_vehicle.json"])("★ 필수 %s 가 없으면 **그 이름을 말하며** 죽는다", async (name) => {
    const files = { ...ALL };
    delete files[name];
    const { loadAll } = await serve(files);
    await expect(loadAll()).rejects.toThrow(new RegExp(name.replace(".", "\\.")));
  });

  it.each(["stations.geojson", "context.geojson"])(
    "★ 곁다리 %s 가 없어도 묶음은 **산다**", async (name) => {
      const files = { ...ALL };
      delete files[name];
      const { loadAll } = await serve(files);
      const b = await loadAll();
      const key = name.startsWith("stations") ? "stations" : "context";
      expect(b[key as "stations" | "context"]).toBeNull();
      expect(b.graph).toEqual(GRAPH);     // 나머지는 그대로 왔다
    });
});

describe("③ 차종 · 이력", () => {
  it("둘을 읽는다", async () => {
    const { loadFleet } = await serve(ALL);
    const got = await loadFleet();
    expect(got.fleet).toEqual({ vehicles: [] });
    expect(got.spec).toEqual(SPEC);
  });

  it("★ `fleet.json` 이 없어도 **던지지 않는다** — 발행 안 한 저장소에서도 개발한다", async () => {
    const files = { ...ALL };
    delete files["fleet.json"];
    const { loadFleet } = await serve(files);
    const got = await loadFleet();
    expect(got.fleet).toBeNull();
    expect(got.spec).toEqual(SPEC);       // 제원은 여전히 와야 한다
  });

  it("제원이 없으면 차종 읽기는 죽는다 — 그것은 필수다", async () => {
    const files = { ...ALL };
    delete files["vehicle_spec.json"];
    const { loadFleet } = await serve(files);
    await expect(loadFleet()).rejects.toThrow(/vehicle_spec/);
  });

  it("이력은 **없으면 null** 이다 — 이력 없이 관제가 돈다", async () => {
    const first = await serve(ALL);
    expect(await first.loadHistory()).not.toBeNull();
    const files = { ...ALL };
    delete files["history.geojson"];
    const second = await serve(files);
    expect(await second.loadHistory()).toBeNull();
  });
});
