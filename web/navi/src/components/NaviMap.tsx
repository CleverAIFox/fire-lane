/**
 * components/NaviMap.tsx — 지도 인스턴스와 **차 고정 카메라**.
 *
 * 레이어 선언은 `layers.ts` 가 든다. 이 파일은 셋만 한다 —
 * 지도 생성 · 카메라 루프 · 데이터 갱신.
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
 * ── ★ 1인칭을 풀면 지도를 만질 수 있어야 한다 ──────────────────
 * 2026-09-06. `dragRotate` 를 항상 끄고 카메라 루프가 매 프레임
 * `jumpTo` 를 불러서, 1인칭을 풀어도 **사용자가 움직인 지도가 즉시
 * 되돌아왔다.** 탐색이 불가능했다.
 *
 * 이제 모드가 둘이다 —
 *
 *     1인칭   카메라가 주행을 따른다. 조작 잠금
 *     탐색    카메라 루프 정지. 드래그·회전·틸트 전부 허용
 *
 * 1인칭으로 돌아오면 현위치로 복귀한다. 상용 내비의 "현위치" 버튼과
 * 같은 동작이다.
 *
 * ── 왜 항공정사영상을 안 쓰나 ───────────────────────────────────
 * 위에서 찍은 평면 사진을 눕히면 건물이 벽이 아니라 바닥의 얼룩이 된다.
 * 내비에 필요한 것은 건물 **형상**이고 `buildings.geojson` 의 h·z·flo 다.
 */
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { angleDelta, type LngLat } from "../domain/geo";
import type { RoutePlan, VerdictStyle, View } from "../domain/types";
import type { LiveFix } from "../app/useNavigation";
import { S } from "../ui/tokens";
import {
  GLYPHS, sources, baseLayers, markerLayers, routeLayers,
  stationLayers, pinLayers,
} from "./layers";

export interface Pin {
  point: LngLat;
  label: string;
  color: string;
}

interface Props {
  view: View;
  /** 60fps 위치 스트림. React state 가 아니다 — 매 프레임 읽는다 */
  live: React.MutableRefObject<LiveFix>;
  plan: RoutePlan | null;
  /** verdict → css color. navi_graph.json.style 에서 온 것 */
  colors: Record<string, string>;
  /**
   * 판정 표현 정본. **배경 도로선 음영을 여기서 파생한다.**
   * 2026-09-06 까지 어두운 색을 layers.ts 에 박아뒀는데, 판정색은
   * 상속받으면서 배경선만 사본을 만든 꼴이었다.
   */
  style: Record<string, VerdictStyle>;
  pins: Pin[];
  /** true 면 주행 추종. false 면 자유 탐색 */
  firstPerson: boolean;
  onMapClick?: (lon: number, lat: number) => void;
  /** 사용자가 지도를 만졌다. App 이 1인칭을 풀 수 있게 알린다 */
  onUserPan?: () => void;
}

/** 보간 계수. 1에 가까울수록 즉시 따라가고 떨린다. */
const LERP_POS = 0.20;
const LERP_BRG = 0.08;

export function NaviMap({
  view, live, plan, colors, style, pins, firstPerson, onMapClick, onUserPan,
}: Props) {
  const styleRef = useRef(style);
  styleRef.current = style;
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const car = useRef<maplibregl.Marker | null>(null);
  const ready = useRef(false);
  const click = useRef(onMapClick);
  click.current = onMapClick;
  const pan = useRef(onUserPan);
  pan.current = onUserPan;
  const cam = useRef({ lon: 0, lat: 0, brg: 0, init: false });
  const fp = useRef(firstPerson);

  useEffect(() => {
    if (!box.current || map.current) return;
    const D = new URL("../data/", document.baseURI).href;
    const home = view.center ?? ([126.9266, 35.1512] as LngLat);

    const m = new maplibregl.Map({
      container: box.current,
      center: home, zoom: 16.5, pitch: 0, maxPitch: 75,
      minZoom: view.minZoom ?? 13, maxZoom: view.maxZoom ?? 20,
      maxBounds: view.maxBounds,
      // ★ `antialias` 는 MapOptions 가 아니라 캔버스 컨텍스트 속성이다.
      //   maplibre-gl 타입에 없어서 tsc 가 죽는다(2026-09-06). 3D 건물은
      //   이것 없이도 충분히 매끄럽다 — 필요해지면 canvasContextAttributes.
      attributionControl: { compact: true },
      style: {
        version: 8,
        glyphs: GLYPHS,
        sources: sources(D),
        layers: baseLayers(styleRef.current),
      },
    });
    map.current = m;
    m.on("error", (e) => console.warn("[map]", e.error?.message ?? e));

    m.on("load", () => {
      // 순서가 곧 겹침 순서다 — 경로 → 마커 → 안전센터 → 핀.
      m.addSource("route", { type: "geojson", data: EMPTY });
      m.addSource("pins", { type: "geojson", data: EMPTY });
      for (const L of routeLayers()) m.addLayer(L);
      for (const L of markerLayers()) m.addLayer(L);
      for (const L of stationLayers()) m.addLayer(L);
      for (const L of pinLayers()) m.addLayer(L);
      ready.current = true;
    });

    m.on("click", (e) => click.current?.(e.lngLat.lng, e.lngLat.lat));
    // ★ 1인칭 중에 사용자가 지도를 끌면 탐색 모드로 넘긴다.
    //   카메라와 손가락이 싸우는 것을 막는다.
    m.on("dragstart", () => { if (fp.current) pan.current?.(); });

    const el = document.createElement("div");
    el.innerHTML =
      `<svg width="36" height="36" viewBox="0 0 36 36">
         <circle cx="18" cy="18" r="16" fill="#4ad1ff" opacity=".16"/>
         <path d="M18 5 L28 30 L18 24 L8 30 Z" fill="#4ad1ff"
               stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>
       </svg>`;
    el.style.cssText = "filter:drop-shadow(0 0 10px rgba(74,209,255,.85))";
    car.current = new maplibregl.Marker({ element: el }).setLngLat(home).addTo(m);

    // ── 카메라 루프 ──────────────────────────────────────────────
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const t = live.current;
      // 차 위치는 모드와 무관하게 갱신한다. 탐색 중에도 차가 어디 있는지
      // 보여야 한다.
      if (t.on) car.current?.setLngLat([t.lon, t.lat]);

      // ★ 탐색 모드에서는 카메라를 건드리지 않는다. 건드리면 사용자가
      //   움직인 지도가 즉시 되돌아온다.
      if (!fp.current || !t.on) { cam.current.init = false; return; }

      const c = cam.current;
      if (!c.init) {                    // 첫 프레임은 순간이동
        c.lon = t.lon; c.lat = t.lat; c.brg = t.brg; c.init = true;
      } else {
        c.lon += (t.lon - c.lon) * LERP_POS;
        c.lat += (t.lat - c.lat) * LERP_POS;
        // 359°→1° 을 358도 회전으로 돌지 않게 최단 방향으로.
        c.brg = (c.brg + angleDelta(c.brg, t.brg) * LERP_BRG + 360) % 360;
      }

      const h = m.getContainer().clientHeight;
      m.jumpTo({
        center: [c.lon, c.lat], bearing: c.brg, pitch: 60, zoom: 18.2,
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

  // ── 모드 전환 ─────────────────────────────────────────────────
  useEffect(() => {
    const m = map.current;
    fp.current = firstPerson;
    if (!m) return;
    if (firstPerson) {
      // 주행 추종. 조작을 잠근다 — 카메라와 손가락이 싸우면 안 된다.
      m.dragRotate.disable();
      m.touchZoomRotate.disableRotation();
      m.dragPan.disable();
      cam.current.init = false;   // 다음 프레임에 현위치로 순간복귀
      m.getCanvas().style.cursor = "crosshair";
    } else {
      // 자유 탐색. 전부 푼다.
      m.dragPan.enable();
      m.dragRotate.enable();
      m.touchZoomRotate.enableRotation();
      m.getCanvas().style.cursor = "grab";
      // 위에서 내려다보는 시점으로 한 번만 정리한다.
      m.easeTo({ pitch: 0, bearing: 0, zoom: 16.5, duration: 500 });
    }
  }, [firstPerson]);

  // ── 경로 ──────────────────────────────────────────────────────
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const draw = () => {
      const src = m.getSource("route") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      src.setData(plan ? {
        type: "FeatureCollection",
        features: plan.edges.map((e) => ({
          type: "Feature" as const,
          geometry: { type: "LineString" as const, coordinates: e.coords },
          properties: {
            color: colors[e.verdict] ?? "#888",
            seg_uid: e.seg_uid, verdict: e.verdict, width_min_m: e.width_min_m,
          },
        })),
      } : EMPTY);
    };
    if (ready.current) draw(); else m.once("load", draw);
  }, [plan, colors]);

  // ── 출발·목적지 핀 ────────────────────────────────────────────
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const draw = () => {
      const src = m.getSource("pins") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      src.setData({
        type: "FeatureCollection",
        features: pins.map((p) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: p.point },
          properties: { label: p.label, color: p.color },
        })),
      });
    };
    if (ready.current) draw(); else m.once("load", draw);
  }, [pins]);

  return <div ref={box} style={{ position: "absolute", inset: 0 }} />;
}

const EMPTY = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;
