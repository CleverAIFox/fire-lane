/**
 * components/NaviMap.tsx — 지도 인스턴스와 **차 고정 카메라**.
 *
 * 레이어 선언은 `layers.ts` 가 든다. 이 파일은 셋만 한다 —
 * 지도 생성 · 카메라 · 데이터 갱신.
 *
 * ══ 카메라 ═══════════════════════════════════════════════════
 *
 * ── 내비 카메라는 차를 쫓아가지 않는다 ──────────────────────────
 * 차가 화면에 **못 박혀 있고 지도가 밑에서 흐른다.** 쫓아가는 구조로
 * 짜면 항상 반 박자 늦고, 그것이 곧 떨림이다.
 *
 * ★ `easeTo` 를 쓰지 않는다. 애니메이션이라 끝나기 전에 새로 부르면
 *   이전 것이 잘린다. 카메라 상태를 직접 들고 rAF 에서 보간한 뒤
 *   `jumpTo` 로 즉시 반영한다.
 *
 * ★ 위치는 `live`(ref)로 받는다. React state 로 흘리면 프레임마다
 *   전체가 리렌더된다.
 *
 * ── 모드 셋 (2026-09-21 · 와이어프레임 09-21) ───────────────────
 *
 *     plan    00 · 01 · 02. 좌측 패널을 비켜 출발·도착·경로를 한눈에 담는다
 *     1인칭    주행. 카메라가 주행을 따른다. 조작 잠금
 *     탐색     카메라 루프 정지. 드래그·회전·틸트 전부 허용
 *
 * ★ 1인칭에서 확대·축소는 **줌 오프셋**을 바꾼다. 카메라 루프가 매 프레임
 *   줌을 덮어쓰므로 지도에 직접 걸면 다음 프레임에 되돌아온다(2026-09-06 에
 *   드래그가 그렇게 되돌아온 것과 같은 병).
 *
 * ── 왜 항공정사영상을 안 쓰나 ───────────────────────────────────
 * 위에서 찍은 평면 사진을 눕히면 건물이 벽이 아니라 바닥의 얼룩이 된다.
 * 내비에 필요한 것은 건물 **형상**이고 `buildings.geojson` 의 h·z·flo 다.
 */
import { useEffect, useRef } from "react";
// ★ 2026-09-15. `import maplibregl from` 이 아니다. maplibre-gl 6 은
//   ESM 전용이 되면서 **기본 내보내기를 없앴다.** 네임스페이스 임포트만 산다.
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// ★ 2026-09-15. v6 는 워커 URL 을 런타임에 계산한다. `?worker&url` 로 Vite 에게
//   명시해야 산출물에 워커가 들어간다 — 빠지면 빌드는 초록이고 지도만 안 그려진다.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { angleDelta, type LngLat } from "../domain/geo";
import type { GraphEdge, RoutePlan, VerdictStyle, View } from "../domain/types";
import type { RouteLook } from "../domain/status";
import type { LiveFix } from "../app/useNavigation";
import { C, S } from "../ui/tokens";
import {
  GLYPHS, sources, baseLayers, markerLayers, routeLayers, altRouteLayers,
  stationLayers, chevronImage,
} from "./layers";

maplibregl.setWorkerUrl(workerUrl);

export interface MapMarks {
  origin?: LngLat | null;
  incident?: LngLat | null;
  /** 최종 접근 지점(P) — 차량 경로의 끝 */
  approach?: LngLat | null;
}

interface Props {
  view: View;
  live: React.MutableRefObject<LiveFix>;
  plan: RoutePlan | null;
  /** 02 경로 비교에서만 — 주 경로 밑에 주황으로 */
  altPlan?: RoutePlan | null;
  style: Record<string, VerdictStyle>;
  look: RouteLook;
  /** 통행 불가로 신고한 구간 */
  blockedEdges: GraphEdge[];
  marks: MapMarks;
  /** P → 사건 위치 점선 */
  finalLeg: LngLat[] | null;
  mode: "plan" | "drive";
  /** drive 에서만 의미가 있다. true 면 주행 추종 */
  firstPerson: boolean;
  /** 배경 도로 판정 음영 */
  tint: boolean;
  /** 조작 명령. `n` 이 바뀔 때만 한 번 실행한다 */
  cmd: { n: number; kind: "in" | "out" | "north" } | null;
  onMapClick?: (lon: number, lat: number) => void;
  onUserPan?: () => void;
}

const LERP_POS = 0.20;
const LERP_BRG = 0.08;
const DRIVE_ZOOM = 18.2;

export function NaviMap(props: Props) {
  // ★ 지도가 뜨기 전에 쌓인 갱신은 **뜬 뒤에** 실행된다. 그때 닫힌 옛 props 를
  //   보면 늦게 온 갱신이 이른 갱신을 덮는다(출발지 없이 사건 위치만 담는
  //   카메라가 마지막에 이겼다 — 2026-09-21 검수 스크린샷). 항상 최신을 읽는다.
  const P = useRef(props);
  P.current = props;
  const p = props;
  const styleRef = useRef(p.style);
  styleRef.current = p.style;
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const car = useRef<maplibregl.Marker | null>(null);
  const marks = useRef<Record<string, maplibregl.Marker | null>>({});
  const ready = useRef(false);
  /** 지도가 뜨기 전에 들어온 갱신. `load` 에서 한 번에 비운다 */
  const pending = useRef<((m: maplibregl.Map) => void)[]>([]);
  const click = useRef(p.onMapClick); click.current = p.onMapClick;
  const pan = useRef(p.onUserPan); pan.current = p.onUserPan;
  const cam = useRef({ lon: 0, lat: 0, brg: 0, init: false });
  const follow = useRef(false);
  const zoomBias = useRef(0);

  useEffect(() => {
    if (!box.current || map.current) return;
    const D = new URL("../data/", document.baseURI).href;
    const home = p.view.center ?? ([126.9266, 35.1512] as LngLat);

    const m = new maplibregl.Map({
      container: box.current,
      center: home, zoom: 15.6, pitch: 45, maxPitch: 75,
      minZoom: p.view.minZoom ?? 13, maxZoom: p.view.maxZoom ?? 20,
      maxBounds: p.view.maxBounds,
      attributionControl: { compact: true },
      style: {
        version: 8, glyphs: GLYPHS,
        sources: sources(D),
        layers: baseLayers(styleRef.current),
      },
    });
    map.current = m;
    m.on("error", (e) => console.warn("[map]", e.error?.message ?? e));

    m.on("load", () => {
      m.addImage("chev", chevronImage());
      for (const id of ["route", "route-alt", "blocked", "final-leg"]) {
        m.addSource(id, { type: "geojson", data: EMPTY });
      }
      // 순서가 곧 겹침 순서다 — 비교 경로 → 주 경로 → 마커 → 안전센터.
      for (const L of altRouteLayers()) m.addLayer(L);
      for (const L of routeLayers()) m.addLayer(L);
      for (const L of markerLayers()) m.addLayer(L);
      for (const L of stationLayers()) m.addLayer(L);
      ready.current = true;
      const q = pending.current; pending.current = [];
      for (const f of q) f(m);
    });

    m.on("click", (e) => click.current?.(e.lngLat.lng, e.lngLat.lat));
    m.on("dragstart", () => { if (follow.current) pan.current?.(); });

    car.current = new maplibregl.Marker({ element: truckEl(), rotationAlignment: "map" })
      .setLngLat(home);

    // ── 카메라 루프 ──────────────────────────────────────────────
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const t = p.live.current;
      if (t.on) {
        if (!car.current!.getElement().isConnected) car.current!.addTo(m);
        car.current!.setLngLat([t.lon, t.lat]).setRotation(t.brg);
      }
      if (!follow.current || !t.on) { cam.current.init = false; return; }
      const c = cam.current;
      if (!c.init) { c.lon = t.lon; c.lat = t.lat; c.brg = t.brg; c.init = true; }
      else {
        c.lon += (t.lon - c.lon) * LERP_POS;
        c.lat += (t.lat - c.lat) * LERP_POS;
        c.brg = (c.brg + angleDelta(c.brg, t.brg) * LERP_BRG + 360) % 360;
      }
      const h = m.getContainer().clientHeight;
      m.jumpTo({
        center: [c.lon, c.lat], bearing: c.brg, pitch: 60,
        zoom: DRIVE_ZOOM + zoomBias.current,
        // ★ 상단은 안내 바가 덮는다. 그만큼 더 밀지 않으면 차가 가린다.
        padding: { top: S.guideBarH + h * 0.34, bottom: 0, left: 0, right: 0 },
      });
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      m.remove(); map.current = null; ready.current = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /** 지도가 준비된 뒤 한 번 실행한다. */
  const whenReady = (f: (m: maplibregl.Map) => void) => {
    const m = map.current;
    if (!m) return;
    if (ready.current) f(m); else pending.current.push(f);
  };

  // ── 모드 전환 ─────────────────────────────────────────────────
  useEffect(() => {
    const m = map.current;
    const on = p.mode === "drive" && p.firstPerson;
    follow.current = on;
    if (!m) return;
    if (on) {
      m.dragRotate.disable(); m.touchZoomRotate.disableRotation(); m.dragPan.disable();
      cam.current.init = false;
    } else {
      m.dragPan.enable(); m.dragRotate.enable(); m.touchZoomRotate.enableRotation();
      if (p.mode === "drive") m.easeTo({ pitch: 45, zoom: 16.8, duration: 500 });
    }
  }, [p.mode, p.firstPerson]);

  // ── 조작 명령 ─────────────────────────────────────────────────
  useEffect(() => {
    const m = map.current;
    if (!m || !p.cmd) return;
    if (p.cmd.kind === "north") { m.easeTo({ bearing: 0, duration: 400 }); return; }
    const d = p.cmd.kind === "in" ? 0.6 : -0.6;
    if (follow.current) zoomBias.current = Math.max(-3, Math.min(1.6, zoomBias.current + d));
    else m.easeTo({ zoom: m.getZoom() + d, duration: 250 });
  }, [p.cmd?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 판정 음영 ─────────────────────────────────────────────────
  useEffect(() => {
    whenReady((m) => m.setLayoutProperty("seg-tint", "visibility", P.current.tint ? "visible" : "none"));
  }, [p.tint]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 경로 ──────────────────────────────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      (m.getSource("route") as maplibregl.GeoJSONSource).setData(routeFc(P.current.plan, P.current.look));
      (m.getSource("route-alt") as maplibregl.GeoJSONSource).setData(routeFc(P.current.altPlan ?? null, "solid"));
      (m.getSource("blocked") as maplibregl.GeoJSONSource).setData({
        type: "FeatureCollection",
        features: P.current.blockedEdges.map((e) => ({
          type: "Feature" as const, properties: {},
          geometry: { type: "LineString" as const, coordinates: e.coords },
        })),
      });
      (m.getSource("final-leg") as maplibregl.GeoJSONSource).setData(P.current.finalLeg ? {
        type: "FeatureCollection", features: [{
          type: "Feature", properties: {},
          geometry: { type: "LineString", coordinates: P.current.finalLeg },
        }],
      } : EMPTY);
    });
  }, [p.plan, p.altPlan, p.look, p.blockedEdges, p.finalLeg]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 마커 (출발 · 사건 · P) ────────────────────────────────────
  useEffect(() => {
    whenReady((m) => {
      const put = (k: string, at: LngLat | null | undefined, el: () => HTMLElement,
                   anchor: maplibregl.PositionAnchor) => {
        const cur = marks.current[k];
        if (!at) { cur?.remove(); marks.current[k] = null; return; }
        if (cur) cur.setLngLat(at);
        else marks.current[k] = new maplibregl.Marker({ element: el(), anchor }).setLngLat(at).addTo(m);
      };
      put("origin", P.current.marks.origin, () => pinEl("출발", C.station), "bottom");
      put("incident", P.current.marks.incident, incidentEl, "bottom");
      put("approach", P.current.marks.approach, pEl, "center");
    });
  }, [p.marks.origin, p.marks.incident, p.marks.approach]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── plan 모드 카메라 — 출발·도착·경로를 한눈에 ──────────────────
  useEffect(() => {
    if (P.current.mode !== "plan") return;
    whenReady((m) => {
      const pts: LngLat[] = [];
      if (P.current.marks.origin) pts.push(P.current.marks.origin);
      if (P.current.marks.incident) pts.push(P.current.marks.incident);
      for (const pl of [P.current.plan, P.current.altPlan]) if (pl) pts.push(...pl.coords);
      if (!pts.length) return;
      let [x0, y0, x1, y1] = [pts[0][0], pts[0][1], pts[0][0], pts[0][1]];
      for (const [x, y] of pts) {
        x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
      }
      if (pts.length === 1) { m.easeTo({ center: pts[0], zoom: 16.2, pitch: 45, bearing: -18, duration: 600 }); return; }
      m.fitBounds([[x0, y0], [x1, y1]], {
        padding: { top: 110, bottom: 80, left: S.sheetW + 70, right: 110 },
        pitch: 45, bearing: -18, duration: 700, maxZoom: 17.2,
      });
    });
  }, [p.mode, p.plan, p.altPlan, p.marks.origin, p.marks.incident]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={box} style={{ position: "absolute", inset: 0 }} />;
}

/**
 * 경로를 **진행 방향**으로 이어 그린다.
 * ★ 구간 형상은 a→b 로 저장돼 있고 경로의 21% 가 거꾸로 지난다. 뒤집지 않으면
 *   갈매기표가 반대로 선다(`RoutePlan.forward` 머리말과 같은 이유).
 */
function routeFc(plan: RoutePlan | null, look: RouteLook): GeoJSON.FeatureCollection {
  if (!plan) return EMPTY;
  return {
    type: "FeatureCollection",
    features: plan.edges.map((e, i) => ({
      type: "Feature" as const,
      geometry: { type: "LineString" as const,
                  coordinates: plan.forward[i] ? e.coords : [...e.coords].reverse() },
      properties: { seg_uid: e.seg_uid, verdict: e.verdict, look },
    })),
  };
}

function truckEl(): HTMLElement {
  const el = document.createElement("div");
  el.innerHTML =
    `<svg width="30" height="52" viewBox="0 0 30 52">
       <rect x="3" y="3" width="24" height="46" rx="5" fill="#dc2626" stroke="#fff" stroke-width="2"/>
       <rect x="6" y="5" width="18" height="9" rx="2" fill="#1f2937"/>
       <path d="M9 18 V44 M21 18 V44 M9 22 H21 M9 28 H21 M9 34 H21 M9 40 H21" stroke="#e5e7eb" stroke-width="1.6"/>
     </svg>`;
  el.style.cssText = "filter:drop-shadow(0 3px 5px rgba(0,0,0,.45))";
  return el;
}
function pinEl(label: string, color: string): HTMLElement {
  const el = document.createElement("div");
  el.innerHTML =
    `<svg width="46" height="58" viewBox="0 0 46 58">
       <path d="M23 56 C23 56 4 34 4 22 A19 19 0 0 1 42 22 C42 34 23 56 23 56 Z" fill="${color}" stroke="#fff" stroke-width="3"/>
       <text x="23" y="27" text-anchor="middle" font-size="12" font-weight="800" fill="#fff" font-family="Pretendard,sans-serif">${label}</text>
     </svg>`;
  el.style.cssText = "filter:drop-shadow(0 3px 6px rgba(0,0,0,.35))";
  return el;
}
function incidentEl(): HTMLElement {
  const el = document.createElement("div");
  el.innerHTML =
    `<svg width="50" height="62" viewBox="0 0 50 62">
       <path d="M25 60 C25 60 4 36 4 23 A21 21 0 0 1 46 23 C46 36 25 60 25 60 Z" fill="#ef2d2d" stroke="#fff" stroke-width="3"/>
       <path d="M25 11 C28 17 33 19 33 26 A8 8 0 0 1 17 26 C17 22 20 20 21 16 C22 20 24 21 25 11 Z" fill="#fff"/>
     </svg>`;
  el.style.cssText = "filter:drop-shadow(0 3px 6px rgba(0,0,0,.4))";
  return el;
}
function pEl(): HTMLElement {
  const el = document.createElement("div");
  el.innerHTML =
    `<svg width="44" height="44" viewBox="0 0 44 44">
       <circle cx="22" cy="22" r="19" fill="#1d4ed8" stroke="#fff" stroke-width="3"/>
       <text x="22" y="29" text-anchor="middle" font-size="20" font-weight="800" fill="#fff" font-family="Pretendard,sans-serif">P</text>
     </svg>`;
  el.style.cssText = "filter:drop-shadow(0 3px 6px rgba(0,0,0,.35))";
  return el;
}

const EMPTY = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;
