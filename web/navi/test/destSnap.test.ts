/**
 * 목적지 색인(dest.geojson) 전점이 도로에 붙는가 — PLAN #59 ②의 **기계 쪽 확인**.
 *
 * ★ 이것은 눈 확인이 아니다. 「스냅 결과가 지도에서 맞는 건물 앞인가」는 사람이 본다.
 *   여기서 닫는 것은 하나뿐이다 — 어느 목적지도 `onRoad`(OpsApp · 60m)가 포기하고
 *   색인 원좌표를 그대로 쓰는 처지에 놓이지 않는다.
 * 실측 2026-11-07: 1,592점 · 최대 34.0m · 60m 초과 0.
 */
import { describe, expect, it } from "vitest";
import { prepare, snap } from "../src/domain/snap";
import { addressLines, asOfDate, preparePois, searchPois } from "../src/domain/search";
import graph from "../../data/navi_graph.json";
import type { NaviGraph } from "../src/domain/types";

// ★ `node:fs` 를 안 쓴다(타입이 없다) — vite 가 빌드 시각에 문자열로 준다(domain.test 와 같다).
const destRaw = Object.values(
  import.meta.glob("../../data/dest.geojson", { query: "?raw", import: "default", eager: true }) as Record<string, string>,
)[0] ?? "";
const dest = JSON.parse(destRaw) as GeoJSON.FeatureCollection;

const prep = prepare((graph as unknown as NaviGraph).edges.map((e) => ({
  seg_uid: e.seg_uid, verdict: e.verdict, width_min_m: e.width_min_m, seg_label: e.seg_label, coords: e.coords,
})));
const pois = preparePois(dest);

describe("목적지 → 스냅", () => {
  it("색인 전점이 60m 안에서 도로에 붙는다", () => {
    expect(pois.length).toBeGreaterThan(1500);
    const far = pois.filter((p) => {
      const r = snap(p.point[0], p.point[1], prep, {});
      return !r || r.dist_m > 60;
    });
    expect(far.map((p) => p.name)).toEqual([]);
  });

  it("같은 단지의 동은 뭉개지지 않는다", () => {
    const a = searchPois(pois, "조대명품타운 104동").filter((h) => h.name.includes("104동"));
    const b = searchPois(pois, "조대명품타운 105동").filter((h) => h.name.includes("105동"));
    expect(a.length).toBeGreaterThan(0);
    expect(b.length).toBeGreaterThan(0);
    expect(a[0].point).not.toEqual(b[0].point);
  });
});

describe("접수 카드 표기 (PLAN #73 진술 1 · 3)", () => {
  it("도로명주소가 먼저, 지번이 뒤다 · 없는 것은 지어내지 않는다", () => {
    expect(addressLines({ addr: "동구 동계천로 162 (동명동)", alt: "동명동 78-1" }))
      .toEqual(["동구 동계천로 162 (동명동)", "동명동 78-1"]);
    expect(addressLines({ addr: "", alt: "동명동 78-1" })).toEqual(["동명동 78-1"]);
    expect(addressLines({ addr: "동구 동명로 1", alt: "동구 동명로 1" })).toEqual(["동구 동명로 1"]);
    expect(addressLines({ addr: "", alt: "" })).toEqual([]);
  });

  it("자료 기준일은 날짜만 · 못 읽으면 null(오늘로 채우지 않는다)", () => {
    expect(asOfDate("2026-11-07T01:02:33+09:00")).toBe("2026-11-07");
    expect(asOfDate("2026-11-07")).toBe("2026-11-07");
    expect(asOfDate(undefined)).toBeNull();
    expect(asOfDate("어제")).toBeNull();
  });

  it("색인의 건물 · 상가는 도로명주소를 든다(지번만인 점이 없다)", () => {
    const noRoad = pois.filter((p) => p.src !== "civil" && !p.addr);
    expect(noRoad.map((p) => p.name)).toEqual([]);
  });
});
