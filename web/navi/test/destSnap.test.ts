/**
 * 목적지 색인(dest.geojson) 전점이 도로에 붙는가 — PLAN #59 ②의 **기계 쪽 확인**.
 *
 * ★ 이것은 눈 확인이 아니다. 「스냅 결과가 지도에서 맞는 건물 앞인가」는 사람이 본다.
 *   여기서 닫는 것은 하나뿐이다 — 어느 목적지도 `onRoad`(OpsApp · 60m)가 포기하고
 *   색인 원좌표를 그대로 쓰는 처지에 놓이지 않는다.
 * 실측 2026-11-07: 1,592점 · 최대 34.0m · 60m 초과 0.
 *
 * ★ 2026-11-14 (PLAN #227 · DECISIONS §730-3 의 2). 검색 범위가 **지도 이동 범위**가 됐다
 *   (2,347점 = 상가 987 · 건물 1,321 · 관공서 · 학교 38 · 지점 1). 도로망은 판정 스코프만
 *   덮어서 가장자리의 관공서 23 과 지점 1 이 60m 밖이다(동구청 124m · 최대 410m).
 *   「전부 60m 안」은 이제 **건물 · 상가**에만 참이고, 먼 점은 **이름으로 고정**한다 —
 *   새로 먼 점이 생기면 여기서 운다. 먼 점을 고르면 화면이 `farFromRoadNote` 를 띄운다.
 *
 * IN    web/data/dest.geojson · web/data/navi_graph.json
 * OUT   없음(검사)
 * PARAM 스냅 한도 60m(`SNAP_MAX_M` = `OpsApp.onRoad`)
 * 밖    스냅 결과가 맞는 건물 앞인가(사람 눈 · PLAN #59 ②) · 초성 · 부분일치의 점수 규칙(`domain.test.ts`)
 */
import { describe, expect, it } from "vitest";
import { prepare, snap } from "../src/domain/snap";
import { addressLines, asOfDate, farFromRoadNote, preparePois, searchPois, SNAP_MAX_M, walkNote } from "../src/domain/search";
import graph from "../../data/navi_graph.json";
import view from "../../data/view.json";
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
const snapM = (p: { point: [number, number] }) => snap(p.point[0], p.point[1], prep, {})?.dist_m ?? Infinity;

/** 도로망(판정 스코프) 밖이라 60m 안에 구간이 없는 점 — 2026-11-14 실측. 전부 관공서 · 학교 · 지점이다. */
const FAR = [
  "계림1동행정복지센터", "계림2동행정복지센터", "광주 인공지능사관학교", "광주동부금남지구대",
  "광주동부산수파출소", "광주동부지산파출소", "광주산수동우체국", "광주산수초등학교", "광주세무서",
  "광주장원초등학교", "광주충장로우체국", "광주충장중학교", "동구청", "보건소", "산수1동행정복지센터",
  "산수2동행정복지센터", "서남동행정복지센터", "조선대학교 교육대학원", "조선대학교 대학원",
  "조선대학교 디자인대학원", "조선대학교부속중학교", "조선대학교여자고등학교", "조선대학교우편취급국",
  "충장동행정복지센터",
];

describe("목적지 → 스냅", () => {
  it("건물 · 상가는 전점이 60m 안에서 도로에 붙는다", () => {
    const near = pois.filter((p) => p.src === "build" || p.src === "store");
    expect(near.length).toBeGreaterThan(2200);
    expect(near.filter((p) => snapM(p) > SNAP_MAX_M).map((p) => p.name)).toEqual([]);
  });

  it("60m 밖은 이름으로 고정한 관공서 · 지점뿐이다(새로 먼 점이 생기면 운다)", () => {
    const far = pois.filter((p) => snapM(p) > SNAP_MAX_M);
    expect(far.map((p) => p.name).sort()).toEqual([...FAR].sort());
    expect(far.every((p) => p.src === "civil" || p.src === "landmark")).toBe(true);
  });

  it("먼 목적지는 화면이 말한다 · 가까우면 말이 없다", () => {
    const gu = pois.find((p) => p.name === "동구청");
    expect(gu).toBeDefined();
    expect(farFromRoadNote(snapM(gu!))).toMatch(/약 1\d\dm/);
    expect(farFromRoadNote(SNAP_MAX_M)).toBeNull();
    expect(farFromRoadNote(0)).toBeNull();
    expect(farFromRoadNote(Number.NaN)).toBeNull();
  });

  it("남은 직선거리 한 마디는 대체 접근 안내와 같은 말이다(화면 글자를 안 늘린다)", () => {
    expect(walkNote(123.6)).toBe("도보 약 124m(직선)");
    expect(farFromRoadNote(SNAP_MAX_M + 1)).toBe(walkNote(SNAP_MAX_M + 1));
  });

  it("같은 단지의 동은 뭉개지지 않는다", () => {
    const a = searchPois(pois, "조대명품타운 104동").filter((h) => h.name.includes("104동"));
    const b = searchPois(pois, "조대명품타운 105동").filter((h) => h.name.includes("105동"));
    expect(a.length).toBeGreaterThan(0);
    expect(b.length).toBeGreaterThan(0);
    expect(a[0].point).not.toEqual(b[0].point);
  });
});

describe("검색 범위 = 지도 이동 범위 (PLAN #227 도착 ②)", () => {
  const top = (q: string) => searchPois(pois, q)[0];

  it("지도 안에 보이는 관공서가 검색에 뜬다 — 동구청 · 동부소방서 · 서석초", () => {
    expect(top("동구청")?.name).toBe("동구청");
    expect(top("동부소방서")?.name).toBe("동부소방서");
    expect(top("서석초")?.name).toBe("광주서석초등학교");
    expect(top("ㄷㄱㅊ")?.name).toBe("동구청");
    expect(pois.filter((p) => p.src === "civil").length).toBe(38);
  });

  it("지점(navi_graph.landmarks)은 전부 같은 좌표로 색인에 든다 — 광주 인공지능사관학교", () => {
    const lms = (graph as unknown as NaviGraph).landmarks ?? [];
    expect(lms.map((l) => l.name)).toContain("광주 인공지능사관학교");
    for (const l of lms) {
      const hit = searchPois(pois, l.name)[0];
      expect(hit?.name).toBe(l.name);
      expect(hit?.src).toBe("landmark");
      expect(Math.abs(hit!.point[0] - l.lng)).toBeLessThan(1e-5);
      expect(Math.abs(hit!.point[1] - l.lat)).toBeLessThan(1e-5);
    }
    expect(top("인공지능")?.name).toBe("광주 인공지능사관학교");
    expect(top("ㅇㄱㅈㄴㅅㄱㅎㄱ")?.name).toBe("광주 인공지능사관학교");
  });

  it("색인은 지도 이동 범위(view.maxBounds)를 안 넘는다 · 동명동 밖 상가도 든다", () => {
    const [[w, s2], [e, n]] = view.maxBounds;
    expect(pois.filter((p) => p.point[0] < w || p.point[0] > e || p.point[1] < s2 || p.point[1] > n)
      .map((p) => p.name)).toEqual([]);
    const [[ew, es], [ee, en]] = view.emdBounds;
    const outEmd = pois.filter((p) => p.src === "store"
      && (p.point[0] < ew || p.point[0] > ee || p.point[1] < es || p.point[1] > en));
    expect(outEmd.length).toBeGreaterThan(300);
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
    const noRoad = pois.filter((p) => (p.src === "build" || p.src === "store") && !p.addr);
    expect(noRoad.map((p) => p.name)).toEqual([]);
  });
});
