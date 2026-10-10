/**
 * test/style.test.ts — 모든 지도 레이어가 MapLibre style-spec 검증기를 통과하는가.
 *
 * ★ 2026-09-22 (DECISIONS §217-3). 관제 판정선 셋(테두리 · 도달 불가 · 선택)이 **무효 식**
 *   (`["+", 줌보간, 2]`)이라 v0.33 부터 한 번도 안 그려졌다. MapLibre 는 무효 레이어를
 *   예외 없이 건너뛰고 콘솔 경고 하나만 남긴다 — tsc(`as never`)도 빌드도 초록이었다.
 *   검증기는 maplibre-gl 이 이미 끌고 오는 의존성이다(`@maplibre/maplibre-gl-style-spec`).
 *   손으로 식 규칙을 재구현하지 않고 **그것에 맡긴다.**
 */
import { validateStyleMin } from "@maplibre/maplibre-gl-style-spec";
import type { StyleSpecification } from "maplibre-gl";
import { FL, test, ok } from "./harness";
import {
  GLYPHS, sources, baseLayers, altRouteLayers, routeLayers, markerLayers, stationLayers,
} from "../src/components/layers";
// ★ 2026-09-29 (§311). 관제 전용 층이 `opsLayers.ts` 로 갈라졌다 — 두 화면의 일이 다르다.
import {
  VERDICT_DASH, opsSegLayers, opsHistoryLayers, opsOverlayLayers, hillshadeLayer,
  opsClearanceBand, opsClearanceColor, landmarkSource, landmarkLayers,
} from "../src/components/opsLayers";
import { CLEARANCE_SCALE } from "../src/ui/clearanceMeaning";
import { CLEARANCE_WIDE_M, type ClearanceBand } from "../src/domain/clearance";
import { TUNING } from "../src/domain/vehicle";

const style = FL.graph.style ?? {};

function check(name: string, layers: StyleSpecification["layers"]) {
  const src = {
    ...sources("../data/", [126.9, 35.14, 126.94, 35.16]),
  } as StyleSpecification["sources"];
  // 앱이 실행 중에 붙이는 geojson 원천(경로 · 미리보기 · 이력)은 빈 것으로 세운다 — 여기서 보는 것은 **식**이다
  const used = new Set(layers.map((l) => ("source" in l ? l.source : undefined)).filter(Boolean) as string[]);
  const sub: StyleSpecification["sources"] = {};
  for (const k of used) sub[k] = src[k] ?? { type: "geojson", data: { type: "FeatureCollection", features: [] } };
  const errs = validateStyleMin({ version: 8, glyphs: GLYPHS, sources: sub, layers } as never);
  ok(!errs.length, `${name}: ${errs.map((e: { message: string }) => e.message).join(" | ")}`);
}

test("내비 레이어 — 바탕 · 경로 · 대안 · 표지 · 센터", () => {
  check("base", baseLayers(style));
  check("alt", altRouteLayers());
  check("route", routeLayers(style));
  check("marker", markerLayers());
  check("station", stationLayers());
  check("landmark", landmarkLayers());
});

/**
 * ★ 2026-10-09 (DECISIONS §444 · PLAN #148). 지점 핀은 **발행물에서 온다.**
 *   옛 발행물에는 `landmarks` 가 없고, 그때 소스를 안 만들면 `addLayer` 가
 *   없는 소스를 가리켜 **지도 전체가 죽는다**(§217-3 과 같은 조용한 자리).
 *   그래서 「없음」이 **빈 모음**이 되는지를 여기서 못박는다.
 */
test("지점 핀 — 없으면 빈 모음 · 있으면 그 점 (경로 밖)", () => {
  // ★ `as unknown as` — 소스 규약은 합집합이라(이미지 소스에는 `data` 가 없다)
  //   한 번에 못 좁힌다. 좁히는 꼴은 `tsc` 가 든다.
  const empty = landmarkSource(undefined) as unknown as { data: { features: unknown[] } };
  ok(empty.data.features.length === 0, "옛 발행물에서 핀이 생긴다");
  ok(landmarkSource([]) !== undefined, "빈 선언에서 소스가 아예 안 선다");

  const one = landmarkSource([{ name: "ㄱ", lng: 126.92, lat: 35.14, note: "ㄴ" }]) as unknown as {
    data: { features: { properties: { name: string }; geometry: { coordinates: number[] } }[] } };
  ok(one.data.features.length === 1, "점 하나가 안 들어간다");
  ok(one.data.features[0].properties.name === "ㄱ", "이름이 안 실린다");
  ok(one.data.features[0].geometry.coordinates[0] === 126.92, "경도·위도 순서가 뒤집혔다");

  // ★ **판정 4색을 안 쓴다.** 하나라도 쓰면 「통행 가능한 지점」으로 읽힌다.
  const paints = JSON.stringify(landmarkLayers());
  for (const [k, v] of Object.entries(style)) {
    ok(!paints.includes(v.color), `지점 핀이 판정색(${k})을 쓴다`);
  }
});

test("관제 레이어 — 판정선 · 이력 · 덧그림 (무효 식이 조용히 빠지던 자리)", () => {
  const segs = opsSegLayers(() => "#888888");
  // ★ 2026-10-10 (DECISIONS §448 · PLAN #145 닫힘). **둘째 채널**이 들어왔다 —
  //   판정마다 바탕색 점선을 한 겹 더 깐다. 목록을 손으로 적으면 패턴이 늘 때마다
  //   이 줄이 낡으므로 **선언에서 낸다**(`VERDICT_DASH`). 순서는 그대로 본다 —
  //   점선이 색 선 **위**가 아니면 무늬가 안 보인다.
  const dashIds = Object.keys(VERDICT_DASH).map((k) => `ops-verdict-dash-${k}`);
  ok(segs.map((l) => l.id).join() ===
     ["ops-verdict-case", "ops-verdict", ...dashIds, "ops-unreach", "ops-selected"].join(),
     `판정선 차례가 다르다 — ${segs.map((l) => l.id).join()}`);
  // ★ 넷을 가르는 채널이 **둘**인가. 색 하나면 `blocked` ↔ `unknown` 이 휘도비
  //   1.00 이라 밝기만 보는 자리에서 같은 선이 된다(§383).
  const dashes = Object.values(VERDICT_DASH).map((d) => d.join());
  ok(new Set(dashes).size === dashes.length, "판정 둘이 같은 무늬다 — 채널이 하나로 돌아간다");
  ok(!("clear" in VERDICT_DASH), "`clear` 에 무늬를 줬다 — 기준이 실선이어야 나머지가 무늬로 읽힌다");
  check("ops-seg", segs);
  check("ops-history", opsHistoryLayers());
  check("ops-overlay", opsOverlayLayers(3, 200));
  check("hillshade", [hillshadeLayer()]);
});

/**
 * ★ 2026-09-23 (§220). 여유폭 모드는 `line-color` · `filter` 를 **실행 중에** 갈아 끼운다.
 *   무효 식이면 §217-3 과 똑같이 조용히 안 그려지므로 여기서도 검증기에 건다.
 *   거르기 식(`opsClearanceBand`)은 `in` 의 왼쪽에 들어가므로 그 모양 그대로 시험한다.
 */
test("관제 여유폭 모드 — 색 식 · 거르기 식", () => {
  const col = opsClearanceColor(3.0, TUNING.tightMarginM, CLEARANCE_WIDE_M,
                                (k) => CLEARANCE_SCALE[k as ClearanceBand].color);
  check("ops-clearance", [{ id: "ops-verdict", type: "line", source: "segments",
    paint: { "line-color": col } }] as never);
  const band = opsClearanceBand(3.0, TUNING.tightMarginM, CLEARANCE_WIDE_M);
  check("ops-clearance-filter", [{ id: "ops-verdict", type: "line", source: "segments",
    filter: ["!", ["in", band, ["literal", ["neg", "unknown"]]]],
    paint: { "line-color": "#888888" } }] as never);
});

test("검증기가 살아 있다 — 줌 보간을 + 로 감싼 옛 식은 운다", () => {
  const bad = [{ id: "x", type: "line", source: "segments",
    paint: { "line-width": ["+", ["interpolate", ["linear"], ["zoom"], 14, 1, 18, 4], 2] } }];
  let threw = false;
  try { check("canary", bad as never); } catch { threw = true; }
  ok(threw, "옛 무효 식을 검증기가 통과시켰다 — 이 시험은 빈 그물이다");
});
