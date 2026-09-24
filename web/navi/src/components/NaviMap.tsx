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
import { egoBox, egoFeature } from "../domain/egobox";
import type { GraphEdge, RoutePlan, VehicleSpec, VerdictStyle, View } from "../domain/types";
import type { RouteLook } from "../domain/status";
import type { LiveFix } from "../app/useNavigation";
import { C, S } from "../ui/tokens";
import {
  GLYPHS, sources, baseLayers, markerLayers, routeLayers, altRouteLayers,
  stationLayers, applyTerrain, chevronImage, cctvIcon, hydrantIcon, bumpIcon, camIcon, zoneIcon, pillImage, pillOptions,
} from "./layers";

maplibregl.setWorkerUrl(workerUrl);

export interface MapMarks {
  origin?: LngLat | null;
  incident?: LngLat | null;
  /** 최종 접근 지점(P) — 차량 경로의 끝 */
  approach?: LngLat | null;
  /** P 아래 알약 문구. 대체 접근 지점이면 그렇게 말한다 */
  approachLabel?: string | null;
}

/** 지도 위 알약 표지 — 02 의 「공통 구간」 · 「확인 필요 NNm」 */
export interface MapNote {
  id: string;
  at: LngLat;
  kind: "common" | "check";
  text: string;
}

interface Props {
  view: View;
  /** 지형 — `navi_graph.json.terrain`(정본 config.js). 없으면 평면(§217-2) */
  terrain?: { enabled: boolean; exaggeration: number };
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
  /** 자차를 **실측 크기 상자**로 놓는다. 전장·전고가 없으면 납작 마커로 남는다(§232) */
  spec?: VehicleSpec | null;
  /** 조작 명령. `n` 이 바뀔 때만 한 번 실행한다. focus 는 그 점으로 카메라를 옮긴다 */
  cmd: { n: number; kind: "in" | "out" | "north" | "focus"; at?: LngLat } | null;
  /** 지도 위 알약 표지 */
  notes?: MapNote[];
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
  const noteMk = useRef<Record<string, maplibregl.Marker>>({});
  const ready = useRef(false);
  /** 지도가 뜨기 전에 들어온 갱신. `load` 에서 한 번에 비운다 */
  const pending = useRef<((m: maplibregl.Map) => void)[]>([]);
  const click = useRef(p.onMapClick); click.current = p.onMapClick;
  const pan = useRef(p.onUserPan); pan.current = p.onUserPan;
  const cam = useRef({ lon: 0, lat: 0, brg: 0, init: false, plon: 0, plat: 0, pbrg: 0, pzb: NaN });
  const follow = useRef(false);
  /** 마지막으로 **그린** 자차 자리. 같으면 다시 안 그린다(W13-4). */
  const ego = useRef({ lon: 0, lat: 0, brg: 0, on: false });
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
      // ★ 2026-09-22 (§216-2) 사용자 보고 「내비가 끊긴다」. 계측하면 시간이 JS(React ·
      //   경로 계산)가 아니라 **GL 그리기**(drawElements · bufferSubData)에 간다. 고해상도
      //   노트북(DPR 2)은 화소가 4배다 — 1.5 로 묶는다. 글자 페이드도 끈다(매 프레임 다시 그림).
      pixelRatio: Math.min(window.devicePixelRatio || 1, 1.5),
      fadeDuration: 0,
      // ★ 한글은 글꼴 서버(PBF)에 없다 — 로컬 글꼴로 그린다. 와이어프레임 글꼴을 쓴다
      localIdeographFontFamily: "Pretendard, 'Noto Sans KR', sans-serif",
      style: {
        version: 8, glyphs: GLYPHS,
        // ★ 2026-09-22 (§214-2). 1인칭(피치 60°)에서 지평선 위가 바탕색 벽이었다 — 하늘을 준다
        sky: {
          "sky-color": "#a9cdf0", "horizon-color": "#e6eef6", "fog-color": "#eef1f4",
          "sky-horizon-blend": 0.55, "horizon-fog-blend": 0.7, "fog-ground-blend": 0.85,
        },
        // ★ 2026-09-22 (§213-4) 빛을 비스듬히 준다. 기본(정수리 · 0.5)은 벽 네 면이
        //   같은 밝기라 건물이 덩어리로 뭉친다. 방위 210° · 고도 30° 에서 남서면이 밝고
        //   북동면이 어둡다.
        light: { anchor: "viewport", color: "#ffffff", intensity: 0.45, position: [1.3, 210, 30] },
        sources: sources(D, p.view.terrainBounds),
        layers: baseLayers(styleRef.current),
      },
    });
    map.current = m;
    // 계측용 손잡이 — `?debug=1` 일 때만. 프레임 계측 스크립트가 레이어를 끄고 켜 본다(§216-2)
    if (new URLSearchParams(location.search).get("debug") === "1") (window as unknown as { __flMap?: unknown }).__flMap = m;
    m.on("error", (e) => console.warn("[map]", e.error?.message ?? e));

    m.on("load", () => {
      m.addImage("chev", chevronImage());
      m.addImage("ic-cctv", cctvIcon(), { pixelRatio: 2 });
      m.addImage("ic-hyd", hydrantIcon(), { pixelRatio: 2 });
      m.addImage("ic-bump", bumpIcon(), { pixelRatio: 2 });
      m.addImage("ic-cam", camIcon(), { pixelRatio: 2 });
      m.addImage("ic-zone", zoneIcon(), { pixelRatio: 2 });
      m.addImage("pill", pillImage(), pillOptions);
      for (const id of ["route", "route-alt", "blocked", "final-leg"]) {
        m.addSource(id, { type: "geojson", data: EMPTY });
      }
      // 순서가 곧 겹침 순서다 — 비교 경로 → 주 경로 → 마커 → 안전센터.
      for (const L of altRouteLayers()) m.addLayer(L);
      for (const L of routeLayers(styleRef.current)) m.addLayer(L);
      for (const L of markerLayers()) m.addLayer(L);
      // ★ 2026-09-24 (§232) 자차 — **실측 크기 상자.** 좌표가 미터라 줌·피치와
      //   무관하게 길과의 비율이 유지된다. 제원이 없으면 비어 있고 납작 마커가 남는다.
      m.addSource("ego", { type: "geojson", data: egoFeature(null) });
      m.addLayer({
        id: "ego-3d", type: "fill-extrusion", source: "ego",
        paint: {
          "fill-extrusion-color": C.egoBody,
          "fill-extrusion-height": ["get", "h"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.95,
          "fill-extrusion-vertical-gradient": true,
        },
      });
      for (const L of stationLayers()) m.addLayer(L);
      // ★ 2026-09-22 (§217-2) 지형을 켠다. `?terrain=0` 이면 평면(느린 기계 · 비교용)
      if (p.view.terrainBounds) {
        applyTerrain(m, p.terrain, new URLSearchParams(location.search).get("terrain") !== "0");
      }
      ready.current = true;
      const q = pending.current; pending.current = [];
      for (const f of q) f(m);
    });

    m.on("click", (e) => click.current?.(e.lngLat.lng, e.lngLat.lat));
    m.on("dragstart", () => { if (follow.current) pan.current?.(); });

    // ★ 2026-09-22 (§214-2). 위에서 본 소방차를 **지도에 눕힌다**(pitchAlignment: map).
    //   피치 60° 에서 원근이 걸려 와이어프레임처럼 뒤에서 내려다본 차가 된다.
    car.current = new maplibregl.Marker({
      element: truckEl(), rotationAlignment: "map", pitchAlignment: "map",
    }).setLngLat(home);

    // ── 카메라 루프 ──────────────────────────────────────────────
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const t = p.live.current;
      // ★ 2026-09-24 (PLAN §13 W13-4). 자차 그리기가 **매 프레임 무조건** 돌았다.
      //   `setData` 는 GeoJSON 소스를 통째로 더럽히므로, 아래 「제자리면 안
      //   그린다」 가드(2026-09-22 · §216-2)가 잡아 둔 비용이 그대로 돌아왔다 —
      //   신호 대기나 도착 뒤에도 지도가 계속 다시 그려졌다. 제원 없는 차는
      //   **빈 FeatureCollection 을 60fps 로** 밀어 넣고 있었다.
      //   자차가 실제로 **움직였을 때만** 그린다.
      const egoMoved = !ego.current.on || t.lon !== ego.current.lon
        || t.lat !== ego.current.lat || t.brg !== ego.current.brg
        || t.on !== ego.current.on;
      if (t.on && egoMoved) {
        ego.current = { lon: t.lon, lat: t.lat, brg: t.brg, on: true };
        // ★ 제원이 있으면 상자, 없으면 납작 마커. **둘을 같이 띄우지 않는다** —
        //   같은 차가 두 크기로 보이면 어느 쪽이 실제인지 화면이 거짓말한다.
        const bx = egoBox(P.current.spec, t.lon, t.lat, t.brg);
        const src = m.getSource("ego") as maplibregl.GeoJSONSource | undefined;
        src?.setData(egoFeature(bx) as never);
        if (bx) {
          if (car.current!.getElement().isConnected) car.current!.remove();
        } else {
          if (!car.current!.getElement().isConnected) car.current!.addTo(m);
          car.current!.setLngLat([t.lon, t.lat]).setRotation(t.brg);
        }
      } else if (!t.on && ego.current.on) {
        // 위치가 꺼지면 한 번만 거둔다.
        ego.current = { ...ego.current, on: false };
        const src = m.getSource("ego") as maplibregl.GeoJSONSource | undefined;
        src?.setData(egoFeature(null) as never);
        if (car.current!.getElement().isConnected) car.current!.remove();
      }
      if (!follow.current || !t.on) { cam.current.init = false; return; }
      const c = cam.current;
      if (!c.init) { c.lon = t.lon; c.lat = t.lat; c.brg = t.brg; c.init = true; c.pzb = NaN; }
      else {
        c.lon += (t.lon - c.lon) * LERP_POS;
        c.lat += (t.lat - c.lat) * LERP_POS;
        c.brg = (c.brg + angleDelta(c.brg, t.brg) * LERP_BRG + 360) % 360;
      }
      // ★ 제자리면 안 그린다. 서 있는 동안에도 매 프레임 jumpTo 가 지도 전체를 다시 그렸다
      const moved = Math.abs(c.lon - c.plon) + Math.abs(c.lat - c.plat) > 1e-8
        || Math.abs(angleDelta(c.pbrg, c.brg)) > 0.02 || c.pzb !== zoomBias.current;
      if (!moved) return;
      c.plon = c.lon; c.plat = c.lat; c.pbrg = c.brg; c.pzb = zoomBias.current;
      const h = m.getContainer().clientHeight;
      m.jumpTo({
        center: [c.lon, c.lat], bearing: c.brg, pitch: 60,
        zoom: DRIVE_ZOOM + zoomBias.current,
        // ★ 2026-09-22 (§214-2). 차를 화면 **아래 3/4** 에 둔다(와이어프레임 03). 위 패딩이
        //   p 면 중심은 p + (h−p)/2 에 선다 — p = h/2 면 3/4 지점. 종전(0.34h + 바)은
        //   차가 가운데 가까이 떠서 앞 길이 반밖에 안 보였다.
        padding: { top: Math.max(S.guideBarH + 40, h * 0.5), bottom: 0, left: 0, right: 0 },
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
    // ★ 2026-09-22 (§214-2). 1인칭에서 앞 건물이 경로를 가렸다 — 주행 중에만 살짝 비친다
    whenReady((mm) => {
      const op = p.mode === "drive" ? 0.86 : 1;
      mm.setPaintProperty("bldg", "fill-extrusion-opacity", op);
    });
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
    if (p.cmd.kind === "focus") {
      if (p.cmd.at) m.easeTo({ center: p.cmd.at, zoom: 17.6, pitch: 55, duration: 700,
                               padding: { top: S.guideBarH, bottom: 0, left: 0, right: 480 } });
      return;
    }
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
      // P 는 문구가 바뀔 수 있어 매번 새로 만든다(대체 접근 지점 ↔ 최종 접근 지점)
      marks.current.approach?.remove(); marks.current.approach = null;
      const ap = P.current.marks.approach;
      if (ap) {
        marks.current.approach = new maplibregl.Marker({
          element: pEl(P.current.marks.approachLabel ?? "최종 차량 접근 지점"), anchor: "top",
          offset: [0, -22],
        }).setLngLat(ap).addTo(m);
      }
    });
  }, [p.marks.origin, p.marks.incident, p.marks.approach, p.marks.approachLabel]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 알약 표지 (02 — 공통 구간 · 확인 필요) ─────────────────────
  useEffect(() => {
    whenReady((m) => {
      for (const mk of Object.values(noteMk.current)) mk.remove();
      noteMk.current = {};
      for (const n of P.current.notes ?? []) {
        noteMk.current[n.id] = new maplibregl.Marker({ element: noteEl(n), anchor: "bottom" })
          .setLngLat(n.at).addTo(m);
      }
    });
  }, [p.notes]); // eslint-disable-line react-hooks/exhaustive-deps

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

/**
 * 위에서 본 소방차. 지도에 눕혀(pitchAlignment: map) 원근을 받는다.
 * ★ 우리가 그린 것이다 — 실제 차종 · 상표를 본뜨지 않았다.
 */
function truckEl(): HTMLElement {
  const el = document.createElement("div");
  el.innerHTML =
    `<svg width="54" height="118" viewBox="0 0 54 118">
       <ellipse cx="27" cy="62" rx="25" ry="56" fill="rgba(0,0,0,.28)"/>
       <rect x="5" y="6" width="44" height="106" rx="9" fill="#d91c1c" stroke="#fff" stroke-width="2.5"/>
       <rect x="8" y="8" width="38" height="24" rx="7" fill="#b91515"/>
       <rect x="11" y="10" width="32" height="11" rx="4" fill="#0f172a"/>
       <rect x="12" y="24" width="12" height="4" rx="2" fill="#3b82f6"/>
       <rect x="30" y="24" width="12" height="4" rx="2" fill="#ef4444"/>
       <rect x="9" y="36" width="36" height="72" rx="4" fill="#e11d1d"/>
       <path d="M17 40 V104 M37 40 V104" stroke="#e5e7eb" stroke-width="3"/>
       <path d="M17 46 H37 M17 54 H37 M17 62 H37 M17 70 H37 M17 78 H37 M17 86 H37 M17 94 H37 M17 102 H37"
             stroke="#cbd5e1" stroke-width="2"/>
       <rect x="7" y="104" width="40" height="6" rx="3" fill="#fbbf24"/>
     </svg>`;
  el.style.cssText = "filter:drop-shadow(0 4px 6px rgba(0,0,0,.35))";
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
/** 사건 지점 — 불 핀 위로 연기가 오른다(와이어프레임 05 · 15 · 23) */
function incidentEl(): HTMLElement {
  const el = document.createElement("div");
  el.style.cssText = "position:relative;filter:drop-shadow(0 3px 6px rgba(0,0,0,.4))";
  el.innerHTML =
    `<div class="fl-smoke"><i></i><i></i><i></i></div>
     <svg width="54" height="66" viewBox="0 0 50 62" style="position:relative">
       <path d="M25 60 C25 60 4 36 4 23 A21 21 0 0 1 46 23 C46 36 25 60 25 60 Z" fill="#ef2d2d" stroke="#fff" stroke-width="3"/>
       <path d="M25 11 C28 17 33 19 33 26 A8 8 0 0 1 17 26 C17 22 20 20 21 16 C22 20 24 21 25 11 Z" fill="#fff"/>
     </svg>`;
  return el;
}
/** 최종 차량 접근 지점 — 파란 P 와 그 아래 흰 알약 */
function pEl(label: string): HTMLElement {
  const el = document.createElement("div");
  el.style.cssText = "display:flex;flex-direction:column;align-items:center;gap:6px;pointer-events:none";
  el.innerHTML =
    `<svg width="46" height="46" viewBox="0 0 44 44" style="filter:drop-shadow(0 3px 6px rgba(0,0,0,.35))">
       <circle cx="22" cy="22" r="19" fill="#1d4ed8" stroke="#fff" stroke-width="3"/>
       <text x="22" y="29" text-anchor="middle" font-size="20" font-weight="800" fill="#fff" font-family="Pretendard,sans-serif">P</text>
     </svg>
     <div style="background:#fff;color:#0f172a;border-radius:999px;padding:5px 12px;font:800 13px Pretendard,sans-serif;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.25)"></div>`;
  (el.lastElementChild as HTMLElement).textContent = label;
  return el;
}
/** 02 표지. 공통 구간은 흰 알약, 확인 필요는 주황 글자의 흰 카드 */
function noteEl(n: MapNote): HTMLElement {
  const el = document.createElement("div");
  const card = n.kind === "check";
  el.style.cssText = `background:#fff;border-radius:${card ? 12 : 999}px;padding:${card ? "8px 14px" : "6px 14px"};`
    + "box-shadow:0 3px 10px rgba(0,0,0,.25);font-family:Pretendard,sans-serif;text-align:center;"
    + "white-space:nowrap;pointer-events:none";
  const [a, b] = n.text.split("\n");
  const top = document.createElement("div");
  top.textContent = a;
  top.style.cssText = `font-weight:800;font-size:${card ? 14 : 13}px;color:${card ? "#d97706" : "#0f172a"}`;
  el.appendChild(top);
  if (b) {
    const bot = document.createElement("div");
    bot.textContent = b;
    bot.style.cssText = "font-weight:800;font-size:16px;color:#0f172a;margin-top:2px";
    el.appendChild(bot);
  }
  return el;
}

const EMPTY = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;
