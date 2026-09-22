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
  opsSegLayers, opsHistoryLayers, opsOverlayLayers, hillshadeLayer,
} from "../src/components/layers";

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
});

test("관제 레이어 — 판정선 · 이력 · 덧그림 (무효 식이 조용히 빠지던 자리)", () => {
  const segs = opsSegLayers(() => "#888888");
  ok(segs.map((l) => l.id).join() === "ops-verdict-case,ops-verdict,ops-unreach,ops-selected", "판정선 넷이 아니다");
  check("ops-seg", segs);
  check("ops-history", opsHistoryLayers());
  check("ops-overlay", opsOverlayLayers(3, 200));
  check("hillshade", [hillshadeLayer()]);
});

test("검증기가 살아 있다 — 줌 보간을 + 로 감싼 옛 식은 운다", () => {
  const bad = [{ id: "x", type: "line", source: "segments",
    paint: { "line-width": ["+", ["interpolate", ["linear"], ["zoom"], 14, 1, 18, 4], 2] } }];
  let threw = false;
  try { check("canary", bad as never); } catch { threw = true; }
  ok(threw, "옛 무효 식을 검증기가 통과시켰다 — 이 시험은 빈 그물이다");
});
