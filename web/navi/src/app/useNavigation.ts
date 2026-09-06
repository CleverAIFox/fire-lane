/**
 * app/useNavigation.ts — 상태 머신과 소스 배선.  (PLAN #63 ①)
 *
 * 대기 → 목적지 → 산출 → 안내 → (이탈·재탐색) → 도착
 *
 * ── 세 속도로 가른다 ────────────────────────────────────────────
 *   위치  60fps      `live` (ref). 카메라만 읽는다. React 가 모른다
 *   스냅  5Hz        2.2ms 브루트포스라 매 프레임은 낭비다
 *   UI    구간 변경   setState
 *
 * ★ 주행 거리를 상태로 들지 않는다. `progressAlongRoute` 가 스냅에서
 *   파생한다. 상태로 들었을 때 GPS 주행에서 0 에 머물렀다.
 *
 * ── 스코프 ──────────────────────────────────────────────────────
 * 경로가 스코프를 벗어나는 것은 **구조적으로 막힌다** — A* 가
 * `navi_graph.json` 위에서만 돌고 그 그래프가 곧 스코프다.
 * ★ 동명동만으로 자르면 안 된다. 성분이 20개로 쪼개지고 안전센터 둘이
 *   **둘 다 동명동 밖**이다.
 *
 * ── ★ 차종이 바뀌면 경로를 다시 낸다 ───────────────────────────
 * 필요폭이 바뀌기 때문이다 — 펌프차 3.0m 대 구급차 2.5m. 폭 2.7m 골목이
 * 한쪽엔 막히고 한쪽엔 뚫린다. `spec` 을 인자로 받아 그것이 바뀌면
 * 인접리스트가 다시 구워진다.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SCOPE_M, SNAP_INTERVAL_MS } from "../config";
import { bearing, distM, type LngLat } from "../domain/geo";
import {
  buildAdjacency, findRoute, nearestNode, routeUids, type Adjacency,
} from "../domain/graph";
import {
  createTracker, prepare, snap as snapOnce, type Tracker,
} from "../domain/snap";
import { verifyAgainstPrecomputed } from "../domain/vehicle";
import { loadAll, type Bundle } from "../infra/dataSource";
import { createGpsSource } from "../infra/position/gps";
import { createSimulationSource } from "../infra/position/simulation";
import type {
  Fix, RoutePlan, SnapResult, VehicleSpec,
} from "../domain/types";

/**
 * 대기 → 목적지 선택 → **경로 확인** → 안내 → 도착
 *
 * ★ `preview` 가 2026-09-06 에 생겼다. 그 전에는 목적지를 고르면 즉시
 *   안내가 시작됐는데, 상용 내비는 경로와 예상 시간을 보여주고 사용자가
 *   시작을 누른다.
 */
export type Phase =
  | "loading" | "idle" | "picked" | "preview" | "guiding" | "arrived";

/** 카메라가 프레임마다 읽는 위치. React 가 모른다. */
export interface LiveFix { lon: number; lat: number; brg: number; on: boolean }

/** 이만큼 움직여야 진행방향을 새로 계산한다(m). */
const MOVE_MIN_M = 1.2;

export function useNavigation(spec: VehicleSpec | null) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [fatal, setFatal] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [data, setData] = useState<Bundle | null>(null);

  const [current, setCurrent] = useState<SnapResult | null>(null);
  const [origin, setOrigin] = useState<SnapResult | null>(null);
  const [dest, setDest] = useState<SnapResult | null>(null);
  const [plan, setPlan] = useState<RoutePlan | null>(null);
  const [fastPlan, setFastPlan] = useState<RoutePlan | null>(null);
  const [offRoute, setOffRoute] = useState(false);
  const [lenient, setLenient] = useState(false);
  const [simSpeed, setSimSpeed] = useState(0);

  const live = useRef<LiveFix>({ lon: 0, lat: 0, brg: 0, on: false });
  const tracker = useRef<Tracker | null>(null);
  const prepared = useRef<ReturnType<typeof prepare> | null>(null);
  const lastSnapAt = useRef(0);
  const lastPos = useRef<LngLat | null>(null);
  const curUid = useRef<string | null>(null);
  const planRef = useRef<RoutePlan | null>(null);
  planRef.current = plan;

  // 판정 기준 차량. `useFleet` 이 만들어 넘긴다.
  // ★ 되먹이지 않는다 — 2026-09-06 에 setState 로 밀어넣었다가
  //   무한 리렌더가 났다. 의존은 useFleet → useNavigation 한 방향이다.
  const active = spec ?? data?.spec ?? null;

  useEffect(() => {
    (async () => {
      try {
        const d = await loadAll();
        // ★ 파이썬과 같은 답을 내는지 즉시 대조한다.
        const v = verifyAgainstPrecomputed(d.graph.edges, d.spec, d.routeVehicle);
        if (v.mismatch.length) {
          console.error("★ edgeCost 이식이 파이썬과 갈렸다", v.mismatch.slice(0, 10));
          setNotice(`edgeCost 대조 실패 — ${v.mismatch.length}건 (콘솔 확인)`);
        } else {
          console.info(`edgeCost 대조 OK — ${v.checked}구간 전량 일치`);
        }
        prepared.current = prepare(d.graph.edges.map((e) => ({
          seg_uid: e.seg_uid, verdict: e.verdict,
          width_min_m: e.width_min_m, seg_label: e.seg_label, coords: e.coords,
        })));
        tracker.current = createTracker(prepared.current);
        setData(d);
        setPhase("idle");
      } catch (e) { setFatal(String(e)); }
    })();
  }, []);

  const adj: Adjacency | null = useMemo(
    () => (data && active ? buildAdjacency(data.graph, active, lenient) : null),
    [data, active, lenient]);
  const adjFast: Adjacency | null = useMemo(
    () => (data && active
      ? buildAdjacency(data.graph, active, lenient, "fastest") : null),
    [data, active, lenient]);

  const onFix = useCallback((f: Fix) => {
    let brg = live.current.brg;
    const p = lastPos.current;
    if (f.heading != null) { brg = f.heading; lastPos.current = [f.lon, f.lat]; }
    else if (p && distM(p, [f.lon, f.lat]) >= MOVE_MIN_M) {
      brg = bearing(p, [f.lon, f.lat]); lastPos.current = [f.lon, f.lat];
    } else if (!p) lastPos.current = [f.lon, f.lat];
    live.current = { lon: f.lon, lat: f.lat, brg, on: true };

    const now = performance.now();
    if (now - lastSnapAt.current < SNAP_INTERVAL_MS) return;
    lastSnapAt.current = now;

    const r = tracker.current?.update(f.lon, f.lat, brg);
    if (!r) return;
    if (r.dist_m > SCOPE_M) {
      setNotice(`스코프 밖이다 (도로에서 ${Math.round(r.dist_m)}m)`);
      return;
    }
    if (!r.confident) return;
    setOffRoute(!!planRef.current && !r.onRoute);
    curUid.current = r.seg_uid;
    setNotice(null);
    setCurrent(r);
  }, []);

  useEffect(() => {
    if (phase === "loading") return;
    if (simSpeed > 0 && plan && phase === "guiding") {
      // 속도는 구간에서 읽는다. simSpeed 는 **재생 배속**이다.
      const src = createSimulationSource(plan, simSpeed, () => {
        setSimSpeed(0); setPhase("arrived");
      });
      return src.start(onFix);
    }
    return createGpsSource().start(onFix, setNotice);
  }, [phase, simSpeed, plan, onFix]);

  /** 좌표를 도로에 붙여본다. 목적지 후보의 판정을 미리 보는 데 쓴다. */
  const snapAt = useCallback((lon: number, lat: number): SnapResult | null => {
    if (!prepared.current) return null;
    const r = snapOnce(lon, lat, prepared.current, {});
    return r && r.dist_m <= SCOPE_M ? r : null;
  }, []);

  const route = useCallback((from: SnapResult, to: SnapResult) => {
    if (!data || !adj) return false;
    const a = nearestNode(data.graph, adj, from.point);
    const b = nearestNode(data.graph, adj, to.point);
    const r = findRoute(data.graph, adj, a, b);
    if (!r) { setNotice("경로가 없다. '연결성 우선'으로 바꿔봐라"); return false; }
    tracker.current?.setRoute(routeUids(r));
    setPlan(r);
    setFastPlan(adjFast ? findRoute(data.graph, adjFast, a, b) : null);
    setOffRoute(false); setNotice(null);
    // ★ 여기서 멈춘다. 사용자가 "안내 시작" 을 눌러야 guiding 이 된다.
    setPhase("preview");
    return true;
  }, [data, adj, adjFast]);

  /**
   * 지도 클릭 · 검색 선택.
   * ★ 클릭 좌표를 그대로 쓰지 않는다. **반드시 도로에 스냅한다** —
   *   내비는 차도만 다닌다.
   */
  const pick = useCallback((lon: number, lat: number) => {
    const s = snapAt(lon, lat);
    if (!s) {
      setNotice("스코프 밖이다 — 동명동과 접근회랑 안에서 찍어라");
      return;
    }
    setNotice(null);
    if (!origin || phase === "arrived") {
      setOrigin(s); setCurrent(s); curUid.current = s.seg_uid;
      setPlan(null); setFastPlan(null); setDest(null); setOffRoute(false);
      lastPos.current = null;
      live.current = { lon: s.point[0], lat: s.point[1], brg: s.bearing, on: true };
      tracker.current?.setRoute(null);
      setPhase("picked");
      return;
    }
    setDest(s);
    route(origin, s);
  }, [snapAt, origin, phase, route]);

  /** 차종·모드가 바뀌었을 때 같은 목적지로 다시 낸다. */
  const recompute = useCallback(() => {
    if (origin && dest) route(origin, dest);
  }, [origin, dest, route]);

  /** 경로 비교에서 고른 쪽을 채택한다. */
  const choose = useCallback((k: "safe" | "fast") => {
    if (k === "fast" && fastPlan) {
      tracker.current?.setRoute(routeUids(fastPlan));
      setPlan(fastPlan);
      setFastPlan(plan);
    }
  }, [plan, fastPlan]);

  /** 안내를 시작한다. `preview` 에서 사용자가 누른다. */
  const start = useCallback(() => {
    if (planRef.current) setPhase("guiding");
  }, []);

  const reset = useCallback(() => {
    setPlan(null); setFastPlan(null); setOrigin(null); setDest(null);
    setCurrent(null); setSimSpeed(0); setOffRoute(false); setNotice(null);
    lastPos.current = null; curUid.current = null;
    live.current.on = false;
    tracker.current?.reset();
    setPhase("idle");
  }, []);

  return {
    phase, fatal, notice, data, live,
    current, origin, dest, plan, fastPlan, offRoute,
    lenient, setLenient, simSpeed, setSimSpeed,
    pick, snapAt, recompute, choose, start, reset,
  };
}
