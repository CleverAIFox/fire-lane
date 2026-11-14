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
import { MAP } from "../src/ui/tokens";
import { withLanduse, landuseLayers, landuseSources, attachLanduse } from "../src/components/landuse";
import { CLEARANCE_WIDE_M, type ClearanceBand } from "../src/domain/clearance";
import { TUNING } from "../src/domain/vehicle";

const style = FL.graph.style ?? {};

// ★ `.geojson` 은 JSON 모듈이 아니라 글롭으로 읽는다(`destSnap.test.ts` 와 같다) — 파일이 없으면 모음이 비어 시험이 우는 쪽이다
const LANDUSE_RAW = Object.values(
  import.meta.glob("../../data/landuse.geojson", { query: "?raw", import: "default", eager: true }),
)[0] as string | undefined;

function check(name: string, layers: StyleSpecification["layers"]) {
  const src = {
    ...sources("../data/", [126.9, 35.14, 126.94, 35.16]), ...landuseSources("../data/"),
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


/**
 * ★ PLAN 행 144(닫힘). 토지이용 면은 **진짜로 그려진다** — 소스가 서 있고 · 레이어가 보도 · 도로면 **아래에** 있고 ·
 *   갈래 색 둘이 모두 쓰이며 · 발행물의 모든 면이 알려진 갈래(`cls`)를 든다.
 *   소스 이름만 적고 레이어가 없거나, 레이어만 있고 데이터가 안 맞으면 읽는 코드가 아니다.
 */
test("토지이용 면 — 소스 · 레이어 순서(보도 · 도로면 아래) · 갈래 색 · 발행물의 갈래", () => {
  // ★ PLAN 행 235 — 두 소스는 층과 함께 `landuse.ts` 에 산다. 진입 청크가 받는 `sources()` 에 도로 들어오면 운다(꺼 둔 층의 578KB 를 첫 화면이 받는다).
  const entry = sources("../data/", [126.9, 35.14, 126.94, 35.16]) as Record<string, unknown>;
  ok(!("landuse" in entry) && !("daeji" in entry), "토지이용 소스가 첫 스타일(`sources()`)에 들었다 — 미룬 청크의 몫이다");
  const src = landuseSources("../data/") as Record<string, { type: string; data?: unknown }>;
  ok(src.landuse?.type === "geojson" && String(src.landuse.data).endsWith("landuse.geojson"), "토지이용 소스가 안 선다");
  ok(!baseLayers(style).some((l) => l.id === "landuse"), "관제 화면과 나눠 쓰는 baseLayers 에 landuse 가 들었다(공유 층 래칫이 오른다)");
  check("landuse", landuseLayers());
  const layers = withLanduse(baseLayers(style)) as { id: string; source?: string; paint?: Record<string, unknown> }[];
  const ids = layers.map((l) => l.id);
  const lu = layers.find((l) => l.id === "landuse");
  ok(!!lu && lu.source === "landuse", "landuse 레이어가 없다");
  ok(ids.indexOf("bg") < ids.indexOf("landuse") && ids.indexOf("landuse") < ids.indexOf("sidewalk") && ids.indexOf("sidewalk") < ids.indexOf("road-area"),
     "토지이용 면이 보도 · 도로면 위에 그려진다(길을 가린다)");
  const paint = JSON.stringify(lu!.paint);
  ok(paint.includes(MAP.landGreen) && paint.includes(MAP.landPlaza), "두 갈래 색이 다 안 쓰인다");
  ok(String(MAP.landGreen) !== String(MAP.landPlaza) && String(MAP.landGreen) !== `rgb(${MAP.bg.join(",")})`, "갈래 색이 구별되지 않는다");
  ok(LANDUSE_RAW !== undefined, "web/data/landuse.geojson 이 없다");
  const fc = JSON.parse(LANDUSE_RAW!) as { features: { properties: { cls: string } }[] };
  ok(fc.features.length > 0, "발행물에 토지이용 면이 0개다 — 빈 바탕이다");
  const KNOWN = ["green", "plaza", "inst", "campus", "jm_forest", "jm_farm", "jm_water", "jm_inst", "jm_green", "jm_paved"];
  ok(fc.features.every((f) => KNOWN.includes(f.properties.cls)), "모르는 갈래가 발행물에 있다");
  // ★ DECISIONS §768 — 대지 면(맨 아래) · 대학 경계선은 선 · 판정 색과 길이 항상 위다
  ok(src.daeji?.type === "geojson" && String(src.daeji.data).endsWith("daeji.geojson"), "대지 소스가 안 선다");
  ok(ids.indexOf("bg") < ids.indexOf("daeji") && ids.indexOf("daeji") < ids.indexOf("landuse"), "대지 면이 landuse 위거나 바탕 밑이다");
  const campus = layers.find((l) => l.id === "landuse-campus") as { type?: string } | undefined;
  ok(campus?.type === "line", "대학 경계선이 선 층이 아니다(칠하면 캠퍼스 안의 길을 가린다)");
  ok(ids.indexOf("landuse-campus") < ids.indexOf("sidewalk"), "대학 경계선이 보도 위에 그려진다");
  for (const k of ["landInst", "landForest", "landFarm", "landWater", "landPaved", "landDaeji"] as const)
    ok(String(paint + JSON.stringify(layers.find((l) => l.id === "daeji")!.paint)).includes(String(MAP[k])), `갈래 색 ${k} 이 안 쓰인다`);
});

/**
 * ★ PLAN 행 235. 내비는 토지이용 면을 **뜬 지도에 나중에** 얹는다(`attachLanduse` · 미룬 청크). 목록에 끼우는 `withLanduse` 와
 *   **같은 순서**가 나와야 한다 — 다르면 면이 길 · 건물 위로 올라온다(DECISIONS §778 C). 가짜 지도로 `addLayer(층, before)` 를 그대로 흉내 낸다.
 */
test("토지이용 면 — 뜬 지도에 얹어도 목록에 끼운 것과 같은 순서 · 두 번 불러도 한 번", () => {
  const order = baseLayers(style).map((l) => l.id);
  const srcs: Record<string, unknown> = {};
  const fake = {
    getLayersOrder: () => [...order],
    getSource: (id: string) => srcs[id],
    addSource: (id: string, s: unknown) => { ok(!(id in srcs), `소스 ${id} 를 두 번 세웠다`); srcs[id] = s; },
    getLayer: (id: string) => (order.includes(id) ? { id } : undefined),
    addLayer: (l: { id: string }, before?: string) => {
      ok(!order.includes(l.id), `층 ${l.id} 를 두 번 얹었다`);
      const at = before === undefined ? order.length : order.indexOf(before);
      ok(at >= 0, `없는 층 ${before} 앞에 얹으려 했다`);
      order.splice(at, 0, l.id);
    },
  };
  attachLanduse(fake as never, "../data/");
  attachLanduse(fake as never, "../data/");
  ok(JSON.stringify(order) === JSON.stringify(withLanduse(baseLayers(style)).map((l) => l.id)),
     `얹은 순서가 끼운 순서와 다르다: ${order.slice(0, 6).join(" > ")}`);
  ok(Object.keys(srcs).sort().join() === "daeji,landuse", "두 소스가 다 안 섰다");
});

/**
 * ★ PLAN 행 239. 지형(`setTerrain`)이 켜진 두 화면에서 건물 압출의 `base` 는 **상수 0** 이다. MapLibre 는 지형이 켜지면 건물을 발자국 중심의 지형 표고에 올리고
 *   `base > 0` 은 그 위에 더한다 — `z`(해발 기준 지반고)를 `base` 로 주면 건물이 그만큼 뜬다(§216-2 · 2026-11-14 헤드리스 재확인). `base` 0 일 때만 벽이 지형 아래로 내려가 틈을 막는다.
 */
test("건물 압출 — 지형 위에서 base 는 상수 0 이고 높이는 h 하나다(지반고 z 를 더하면 뜬다)", () => {
  const bldg = baseLayers(style).find((l) => l.id === "bldg") as { type: string; paint: Record<string, unknown> };
  ok(bldg.type === "fill-extrusion", "bldg 가 압출 층이 아니다");
  ok(bldg.paint["fill-extrusion-base"] === 0, `base 가 0 이 아니다: ${JSON.stringify(bldg.paint["fill-extrusion-base"])}`);
  ok(JSON.stringify(bldg.paint["fill-extrusion-height"]) === JSON.stringify(["get", "h"]), "높이가 h 하나가 아니다");
  ok(!JSON.stringify(bldg.paint).includes('"z"'), "압출 식에 지반고 z 가 들어왔다 — 지형이 이미 올려 준 높이를 한 번 더 더한다");
});

/**
 * ★ PLAN 행 241 · 242. 지점 핀은 **안전센터 점보다 작지 않고**(센터 반지름 7) 글자는 건물 이름(12.5px)보다 작지 않다 — 어두운 3D 건물 위에서 묻혔던 것이 원인의 반이다.
 *   채우지 않은 고리라는 꼴(판정 색을 안 먹는다 · §444)은 그대로다.
 */
test("지점 핀 — 고리는 안전센터 점보다 작지 않고 속이 비었으며 글자는 건물 이름보다 작지 않다", () => {
  const [ring, lbl] = landmarkLayers() as { id: string; paint: Record<string, unknown>; layout?: Record<string, unknown> }[];
  ok(ring.id === "landmark-ring" && lbl.id === "lbl-landmark", "지점 층 둘의 이름 · 순서가 바뀌었다");
  ok(Number(ring.paint["circle-radius"]) >= 7 && Number(ring.paint["circle-stroke-width"]) >= 2.5, "고리가 안전센터 점(7)보다 작다");
  ok(ring.paint["circle-color"] === "rgba(0,0,0,0)", "고리 속을 채웠다 — 채운 점은 안전센터의 꼴이다");
  ok(Number(lbl.layout!["text-size"]) >= 12.5, "지점 글자가 건물 이름(12.5px)보다 작다");
});
