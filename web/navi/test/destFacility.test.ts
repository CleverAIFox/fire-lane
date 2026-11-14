/**
 * 건물 면의 이름이 목적지 색인에 들어 검색에 뜬다 — PLAN #244 · DECISIONS §785 · §786.
 *
 * ★ 사람이 관제 화면에서 「전당 · 법원 부지가 검게 비었고 이름도 안 뜬다」고 지적했다(세 번째). 면은 데이터에 있었고
 *   이름이 색인에 없었다. 여기서 문다 — 다섯 곳을 **이름으로** 쳐서 `build` 원천의 점이 뜨는가.
 * ★ 「전남대병원」 이라는 글자는 건물 데이터에 없다 — 면의 이름은 `전남의대부속병원` · `전남대학교병원` 이다.
 *   ★ 그런데 그 두 면은 **지도 이동 범위 밖**이다(대표점 위도 35.14185 < `maxBounds` 남쪽 35.1431 · 2026-11-14 실측). 색인은 범위를 안 넘으므로
 *   (`destSnap.test.ts`) 둘은 안 든다 — **범위 안에 있는 의료 면**(`노벨병원` · `서남대학교병원`)으로 건다. 둘을 넣으려면 범위를 넓히는 별도 결정이다.
 *   광주지방법원은 면 이름이 `광주지방.고등법원` 이고 `광주지방법원` 은 동 상세명(`alt`)에 있다.
 *
 * IN    web/data/dest.geojson
 * OUT   없음(검사)
 * PARAM 없음
 * 밖    점이 맞는 건물 위인가(사람 눈) · 도로 스냅(`destSnap.test.ts`)
 */
import { describe, expect, it } from "vitest";
import { preparePois, searchPois } from "../src/domain/search";

const destRaw = Object.values(
  import.meta.glob("../../data/dest.geojson", { query: "?raw", import: "default", eager: true }) as Record<string, string>,
)[0] ?? "";
const pois = preparePois(JSON.parse(destRaw) as GeoJSON.FeatureCollection);

const CASES: [string, string][] = [
  ["아시아문화전당", "국립아시아문화전당"],
  ["광주지방법원", "광주지방.고등법원"],
  ["동구국민체육센터", "동구국민체육센터"],
  ["노벨병원", "노벨병원"],
  ["서남대학교병원", "서남대학교병원"],
  ["롯데백화점", "롯데백화점 광주점"],
];

describe("건물 면 이름 → 검색", () => {
  for (const [q, name] of CASES) {
    it(`「${q}」 → ${name} (건물 원천)`, () => {
      const hit = searchPois(pois, q, 20).find((h) => h.name === name);
      expect(hit, `${q} 로 ${name} 가 안 뜬다`).toBeTruthy();
      expect(hit!.src).toBe("build");
    });
  }
});
