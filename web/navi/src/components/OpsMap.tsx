/**
 * components/OpsMap.tsx — 관제 화면의 지도.  (DECISIONS §214-4)
 *
 * 내비 지도(`NaviMap`)와 **같은 바탕**(도로면 · 보도 · 건물 · 아이콘 — `layers.ts`)을 쓰고,
 * 그 위에 관제가 보는 것을 얹는다 —
 *
 *     판정 4색            구간 색. 정본(`style`) 그대로 — 음영이 아니라 원색. 폭에 비례해 굵다
 *     도달 불가 겹침       고른 센터 · 차종 기준으로 닿지 않는 구간을 회색 사선으로
 *     CCTV 25m 반경       영상판정이 성립하는 범위(`seg/params.py` CCTV_RANGE 와 같은 수)
 *     정사영상 25cm        로컬 타일(`web/data/ortho`). 키가 필요 없다
 *     출동 미리보기        센터 → 사건 지점 경로(파랑) · 대체 접근 지점이면 도보 점선
 *     출동 중인 차         내비 탭이 보내는 위치 · 경로 · 상태(`opsProtocol`)
 *     공유된 지점          병목 · 통행 불가 · 도착 보고
 *
 * ★ 판정색을 여기서 만들지 않는다. `style` 은 `navi_graph.json.style` 이고 그 정본은
 *   `web/config.js` 다.
 * ★ 25m 는 **표시용 사본**이다 — 정본은 `seg/params.py` 의 CCTV_RANGE 다. 레거시 지도
 *   (`web/config.js` markers[].cover.radius)도 같은 수를 따로 들고 있다.
 */
import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { LngLat } from "../domain/geo";
import type { VerdictStyle, View } from "../domain/types";
import type { FeedItem, Unit } from "../domain/opsProtocol";
import {
  GLYPHS, sources, baseLayers, opsSegLayers, opsHistoryLayers, opsOverlayLayers, hillshadeLayer, applyTerrain, markerLayers, stationLayers,
  cctvIcon, hydrantIcon, bumpIcon, camIcon, zoneIcon, pillImage, pillOptions,
} from "./layers";

maplibregl.setWorkerUrl(workerUrl);

/** CCTV 영상판정 유효 반경(m). 정본은 seg/params.py CCTV_RANGE — 표시용 사본 */
const CCTV_RANGE_M = 25;

export interface OpsLayers {
  ortho: boolean;
  reach: boolean;
  cctvCov: boolean;
  /** 3D 건물(비스듬히). 끄면 평면 건물 — 관제 기본 */
  bldg: boolean;
  /** 119 신고 · 구조 이력 — 밀도 + 실제 도착 시간 색(§216-3) */
  history: boolean;
  /** 과속방지턱 · 단속카메라 · 보호구역 시설(§216-3) */
  context: boolean;
  /** 지형 — 음영(평면) + 3D 에서 지면 휨(§217-2) */
  terrain: boolean;
}

/**
 * 관제실 톤 — 어두운 바탕에 판정 4색이 뜬다(§216-4).
 * ★ 판정색은 안 바꾼다(정본 `style`). 바탕 · 도로면 · 건물 · 글자만 어둡게 한다 —
 *   밝은 바탕에서는 초록 · 주황이 도로 회색과 붙어 보였다.
 */
const DARK = {
  bg: "#0b1220", sidewalk: "#131c2e", road: "#1f2a3d", roadEdge: "#26334a", segRoad: "#2b384f",
  bldgFlat: "#172033", bldgEdge: "#2a3650", label: "#cbd5e1", halo: "#0b1220",
};

interface Props {
  view: View;
  /** 지형 — `navi_graph.json.terrain`(정본 config.js) */
  terrain?: { enabled: boolean; exaggeration: number };
  style: Record<string, VerdictStyle>;
  layers: OpsLayers;
  hidden: ReadonlySet<string>;
  /** 닿는 구간. null 이면 겹침 없음 */
  reachable: ReadonlySet<string> | null;
  incident: LngLat | null;
  preview: LngLat[] | null;
  previewWalk: LngLat[] | null;
  units: Unit[];
  feed: FeedItem[];
  selectedSeg: string | null;
  focus: { n: number; at: LngLat; zoom?: number } | null;
  onPick: (lon: number, lat: number) => void;
  onSeg: (uid: string | null) => void;
}

const EMPTY = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;
const line = (c: LngLat[] | null): GeoJSON.FeatureCollection => (c && c.length > 1 ? {
  type: "FeatureCollection",
  features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: c } }],
} : EMPTY);

/** 위도 35.15° 에서 줌 z 의 m/px */
const mpp = (z: number) => (156543.03 * Math.cos((35.15 * Math.PI) / 180)) / 2 ** z;

export function OpsMap(props: Props) {
  const P = useRef(props);
  P.current = props;
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const pending = useRef<((m: maplibregl.Map) => void)[]>([]);
  const unitMk = useRef<Record<string, maplibregl.Marker>>({});
  const feedMk = useRef<Record<string, maplibregl.Marker>>({});
  const incMk = useRef<maplibregl.Marker | null>(null);

  const whenReady = (f: (m: maplibregl.Map) => void) => {
    const m = map.current;
    if (!m) return;
    if (ready.current) f(m); else pending.current.push(f);
  };

  useEffect(() => {
    if (!box.current || map.current) return;
    const D = new URL("../data/", document.baseURI).href;
    const v = P.current.view;
    const st = P.current.style;
    const col = (k: string) => st[k]?.color ?? "rgb(120,128,140)";
    const m = new maplibregl.Map({
      container: box.current,
      center: v.center ?? [126.9266, 35.1512], zoom: 15.4, pitch: 0,
      minZoom: v.minZoom ?? 13, maxZoom: v.maxZoom ?? 20, maxBounds: v.maxBounds,
      attributionControl: { compact: true },
      localIdeographFontFamily: "Pretendard, 'Noto Sans KR', sans-serif",
      style: {
        version: 8, glyphs: GLYPHS,
        sources: {
          ...sources(D, v.terrainBounds),
          ortho: {
            type: "raster", tiles: [D + "ortho/{z}/{x}/{y}.jpg"], tileSize: 256,
            minzoom: 15, maxzoom: 19,
            ...(v.orthoBounds ? { bounds: v.orthoBounds } : {}),
          },
        },
        layers: baseLayers(st),
      },
    });
    map.current = m;
    // 계측용 손잡이 — `?debug=1` 일 때만(내비와 같다). 레이어가 실제로 올랐는지 헤드리스가 본다(§217-3)
    if (new URLSearchParams(location.search).get("debug") === "1") (window as unknown as { __flMap?: unknown }).__flMap = m;
    m.on("error", (e) => console.warn("[ops map]", e.error?.message ?? e));

    m.on("load", () => {
      m.addImage("ic-cctv", cctvIcon(), { pixelRatio: 2 });
      m.addImage("ic-hyd", hydrantIcon(), { pixelRatio: 2 });
      m.addImage("ic-bump", bumpIcon(), { pixelRatio: 2 });
      m.addImage("ic-cam", camIcon(), { pixelRatio: 2 });
      m.addImage("ic-zone", zoneIcon(), { pixelRatio: 2 });
      // ── 관제실 톤 (§216-4) ──
      m.setPaintProperty("bg", "background-color", DARK.bg);
      m.setPaintProperty("sidewalk", "fill-color", DARK.sidewalk);
      m.setPaintProperty("road-area", "fill-color", DARK.road);
      m.setPaintProperty("road-area", "fill-outline-color", DARK.roadEdge);
      m.setPaintProperty("seg-road", "line-color", DARK.segRoad);
      m.setPaintProperty("seg-marking", "line-opacity", 0.25);
      m.setPaintProperty("bldg-flat", "fill-color", DARK.bldgFlat);
      m.setPaintProperty("bldg-flat", "fill-outline-color", DARK.bldgEdge);
      m.setPaintProperty("bldg", "fill-extrusion-color", "#24304a");
      // ── 지형 음영 (§217-2) — 위에서 본 평면에서도 등성이 · 골이 보인다 ──
      if (m.getSource("dem")) {
        m.addLayer(hillshadeLayer(), "sidewalk");
      }
      // ── 출동 이력 (§216-3) — 밀도 + 실제 도착 시간 색 ──
      m.addSource("history", { type: "geojson", data: D + "history.geojson" });
      for (const L of opsHistoryLayers()) m.addLayer(L);
      m.addImage("pill", pillImage(), pillOptions);
      for (const id of ["preview", "preview-walk", "unit-routes"]) m.addSource(id, { type: "geojson", data: EMPTY });

      // 정사영상은 바탕 **위** · 판정 **밑**. 켜면 도로면 · 건물이 사진으로 바뀐다
      m.addLayer({ id: "ortho", type: "raster", source: "ortho",
                   layout: { visibility: "none" }, paint: { "raster-opacity": 1 } }, "seg-road");

      for (const L of opsSegLayers(col)) m.addLayer(L);

      for (const L of opsOverlayLayers(CCTV_RANGE_M / mpp(14), CCTV_RANGE_M / mpp(20))) m.addLayer(L);

      for (const L of markerLayers()) m.addLayer(L);
      for (const L of stationLayers()) m.addLayer(L);
      // ★ 글자 색은 글자 레이어가 **생긴 뒤에** 입힌다 — 앞에서 입히면 레이어가 없어 조용히 건너뛴다
      //   (독립 검토 2026-09-22: 어두운 바탕에 밝은 테마 글자가 그대로 남았다)
      //   건물 · 상호 이름은 **흰 알약** 위에 앉으므로 알약을 어둡게 하고 글자는 밝게 둔다
      for (const id of ["lbl-road", "lbl-bldg", "lbl-poi", "lbl-station"]) {
        if (!m.getLayer(id)) continue;
        m.setPaintProperty(id, "text-color", DARK.label);
        m.setPaintProperty(id, "text-halo-color", DARK.halo);
        m.setPaintProperty(id, "text-halo-width", id === "lbl-road" || id === "lbl-station" ? 1.4 : 0);
        if (id === "lbl-bldg" || id === "lbl-poi") m.setPaintProperty(id, "icon-opacity", 0.18);
      }
      ready.current = true;
      const q = pending.current; pending.current = [];
      for (const f of q) f(m);
    });

    m.on("click", (e) => {
      const hit = m.queryRenderedFeatures(e.point, { layers: ["ops-verdict"] })[0];
      P.current.onPick(e.lngLat.lng, e.lngLat.lat);
      P.current.onSeg(hit ? String(hit.properties?.seg_uid ?? "") || null : null);
    });
    m.on("mouseenter", "ops-verdict", () => { m.getCanvas().style.cursor = "pointer"; });
    m.on("mouseleave", "ops-verdict", () => { m.getCanvas().style.cursor = ""; });
    return () => { m.remove(); map.current = null; ready.current = false; };
  }, []);

  // ── 레이어 토글 ───────────────────────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      const L = P.current.layers;
      const vis = (id: string, on: boolean) => m.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      vis("ortho", L.ortho);
      vis("cctv-cov", L.cctvCov);
      vis("bldg", L.bldg && !L.ortho);
      vis("bldg-flat", !L.bldg && !L.ortho);
      vis("hist-heat", L.history);
      vis("hist-pt", L.history);
      vis("ctx", L.context);
      if (m.getLayer("hillshade")) vis("hillshade", L.terrain && !L.ortho);
      // 3D(비스듬히)일 때만 지면을 휜다 — 위에서 본 평면은 음영으로 충분하고 그리기가 가볍다
      if (m.getSource("dem")) applyTerrain(m, P.current.terrain, L.terrain && L.bldg);
      vis("road-area", !L.ortho);
      vis("sidewalk", !L.ortho);
      vis("seg-road", !L.ortho);
      vis("ops-unreach", L.reach && !!P.current.reachable);
      m.easeTo({ pitch: L.bldg && !L.ortho ? 45 : 0, duration: 400 });
    });
  }, [props.layers]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 판정 거르기 · 도달 불가 · 선택 ─────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      const hid = [...P.current.hidden];
      m.setFilter("ops-verdict", hid.length ? ["!", ["in", ["get", "verdict"], ["literal", hid]]] as never : null);
      m.setFilter("ops-verdict-case", hid.length ? ["!", ["in", ["get", "verdict"], ["literal", hid]]] as never : null);
      const r = P.current.reachable;
      m.setFilter("ops-unreach", r ? ["!", ["in", ["get", "seg_uid"], ["literal", [...r]]]] as never : null);
      m.setLayoutProperty("ops-unreach", "visibility", P.current.layers.reach && r ? "visible" : "none");
      m.setFilter("ops-selected", ["==", ["get", "seg_uid"], P.current.selectedSeg ?? ""] as never);
    });
  }, [props.hidden, props.reachable, props.selectedSeg, props.layers.reach]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 출동 미리보기 ─────────────────────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      (m.getSource("preview") as maplibregl.GeoJSONSource).setData(line(P.current.preview));
      (m.getSource("preview-walk") as maplibregl.GeoJSONSource).setData(line(P.current.previewWalk));
    });
  }, [props.preview, props.previewWalk]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 사건 지점 ─────────────────────────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      incMk.current?.remove(); incMk.current = null;
      const at = P.current.incident;
      if (at) incMk.current = new maplibregl.Marker({ element: firePin(), anchor: "bottom" }).setLngLat(at).addTo(m);
    });
  }, [props.incident]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 출동 중인 차 ──────────────────────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      const seen = new Set<string>();
      const routes: GeoJSON.Feature[] = [];
      for (const u of P.current.units) {
        seen.add(u.unit);
        if (u.route && u.route.length > 1) {
          routes.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: u.route } });
        }
        const pos = u.last.pos;
        if (!pos) continue;
        let mk = unitMk.current[u.unit];
        if (!mk) {
          mk = new maplibregl.Marker({ element: unitEl(), anchor: "center", rotationAlignment: "map" })
            .setLngLat(pos).addTo(m);
          unitMk.current[u.unit] = mk;
        }
        mk.setLngLat(pos).setRotation(u.last.brg);
        const lab = mk.getElement().querySelector("span");
        if (lab) lab.textContent = u.last.vehicle;
      }
      for (const [k, mk] of Object.entries(unitMk.current)) {
        if (!seen.has(k)) { mk.remove(); delete unitMk.current[k]; }
      }
      (m.getSource("unit-routes") as maplibregl.GeoJSONSource).setData({ type: "FeatureCollection", features: routes });
    });
  }, [props.units]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 공유된 지점 ───────────────────────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      const seen = new Set<string>();
      for (const f of P.current.feed) {
        if (!f.point) continue;
        seen.add(f.shareId);
        const old = feedMk.current[f.shareId];
        const want = `${f.kind}-${f.ackedAt ? "a" : "w"}`;
        if (old && old.getElement().dataset.k === want) continue;
        old?.remove();
        const el = feedEl(f);
        el.dataset.k = want;
        feedMk.current[f.shareId] = new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(f.point).addTo(m);
      }
      for (const [k, mk] of Object.entries(feedMk.current)) {
        if (!seen.has(k)) { mk.remove(); delete feedMk.current[k]; }
      }
    });
  }, [props.feed]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 초점 ──────────────────────────────────────────────────────
  useEffect(() => {
    const f = P.current.focus;
    if (!f) return;
    whenReady((m) => m.easeTo({ center: f.at, zoom: f.zoom ?? 17, duration: 600 }));
  }, [props.focus?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={box} style={{ position: "absolute", inset: 0 }} />;
}

function firePin(): HTMLElement {
  const el = document.createElement("div");
  el.style.cssText = "filter:drop-shadow(0 3px 6px rgba(0,0,0,.4))";
  el.innerHTML =
    `<svg width="42" height="52" viewBox="0 0 50 62">
       <path d="M25 60 C25 60 4 36 4 23 A21 21 0 0 1 46 23 C46 36 25 60 25 60 Z" fill="#ef2d2d" stroke="#fff" stroke-width="3"/>
       <path d="M25 11 C28 17 33 19 33 26 A8 8 0 0 1 17 26 C17 22 20 20 21 16 C22 20 24 21 25 11 Z" fill="#fff"/>
     </svg>`;
  return el;
}
function unitEl(): HTMLElement {
  const el = document.createElement("div");
  el.style.cssText = "display:flex;flex-direction:column;align-items:center;pointer-events:none";
  el.innerHTML =
    `<svg width="26" height="44" viewBox="0 0 26 44" style="filter:drop-shadow(0 2px 4px rgba(0,0,0,.45))">
       <rect x="2" y="2" width="22" height="40" rx="5" fill="#dc2626" stroke="#fff" stroke-width="2"/>
       <rect x="5" y="4" width="16" height="8" rx="2" fill="#0f172a"/>
       <path d="M8 16 V38 M18 16 V38" stroke="#e5e7eb" stroke-width="1.6"/>
     </svg>
     <span style="margin-top:2px;background:#0f172a;color:#fff;border-radius:6px;padding:2px 6px;font:700 11px Pretendard,sans-serif;white-space:nowrap"></span>`;
  return el;
}
function feedEl(f: FeedItem): HTMLElement {
  const el = document.createElement("div");
  const c = f.kind === "blocked" ? "#991b1b" : f.kind === "arrival" ? "#1d4ed8" : "#d97706";
  const t = f.kind === "blocked" ? "통행 불가" : f.kind === "arrival" ? "도착" : "병목";
  el.style.cssText = `background:${f.ackedAt ? "#fff" : c};color:${f.ackedAt ? c : "#fff"};border:2px solid ${c};`
    + "border-radius:999px;padding:3px 10px;font:800 12px Pretendard,sans-serif;white-space:nowrap;"
    + "box-shadow:0 2px 8px rgba(0,0,0,.3);pointer-events:none";
  el.textContent = `${t}${f.ackedAt ? " ✓" : ""}`;
  return el;
}
