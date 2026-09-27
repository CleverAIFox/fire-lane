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
 * ── 넷을 들고 있었다 (PLAN §1 #129) ─────────────────────────────
 * ★ 2026-09-25. 570줄이었고 한 훅이 넷을 들었다. 셋을 형제로 떼고 **단계 기계와
 *   5Hz 스냅만** 남겼다 — 형제 여섯(`useFleet` · `useHudData` · `useOpsUplink` ·
 *   `useScreens` · `useShare` · `useVoice`)과 같은 규율이다.
 *
 *     `useBundle`          `web/data` 적재 · 스냅기 · `snapAt`
 *     `usePositionSource`  gps · 흉내 · 경로 따라가기 중 하나를 잇는다 · teleport
 *     `useDeadReckoning`   드문 측위 사이를 60fps 로 메운다 (ref 만 고친다)
 *     `domain/routeSolve`  투영 → A* → 대체 접근 지점 → 빠른 경로 (순수)
 *
 *   여기 남은 것은 **상태를 가진 일**뿐이다 — 단계 전이, 5Hz 스냅 결과를 state 로
 *   옮기기, 이탈 재탐색 타이머. 반환 객체의 이름 서른아홉은 한 글자도 안 바뀌었다.
 *
 * ★ 2026-09-22 (DECISIONS §213-2). **주행 거리는 위치 추정기(`domain/progress`)가
 *   낸다.** 종전에는 구간 스냅의 seg_uid 로 `progressAlongRoute` 를 파생했는데
 *   교차로에서 스냅이 망설이면 옛 값을 붙들었고, 순간이동을 몰랐다. 이제
 *
 *     측위 → locate(경로 선형 · 예측) → driven · 이탈 · 순간이동(jumpSeq)
 *                                    ↘ 60fps 추측항법 → 마커 · 카메라
 *
 *   이탈 중에만 구간 스냅을 쓴다 — 재탐색 출발점이 경로 밖이기 때문이다.
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
import { buildAdjacency, type Adjacency } from "../domain/adjacency";
import { buildHazardIndex } from "../domain/pressure";
import { fullProgress } from "../domain/edgeSnap";
import { progressAlongRoute, routeUids } from "../domain/routeDerive";
import { reaches, solveRoute } from "../domain/routeSolve";
import { GPS_WEAK_M } from "../domain/status";
import {
  locate, pointAtM, routeGeom, type ProgressState, type RouteGeom,
} from "../domain/progress";
import { useBundle } from "./useBundle";
import { useDeadReckoning } from "./useDeadReckoning";
import { usePositionSource } from "./usePositionSource";
import type {
  Fix, Phase, RoutePlan, SnapResult, VehicleSpec,
} from "../domain/types";

// ★ 집은 `domain/types.ts` 다(DECISIONS §244). 여기서는 다시 내보낸다.
import type { LiveFix, PosMode } from "../domain/types";
export type { LiveFix, PosMode, Phase };

/**
 * 시연 위치원.  route = 경로를 따라 걷는 정답 점(60fps) · gpsSim = GPS 흉내(1Hz · 잡음 · 음영).
 * ★ 폐루프 검수는 gpsSim 으로 한다. route 는 추정이 틀려도 맞아 보인다(§213-3).
 */

/** 도착으로 보는 남은 거리(m). 시뮬레이션 끝 신호가 없는 실주행에서 쓴다 */
const ARRIVE_M = 15;

/** 이만큼 움직여야 진행방향을 새로 계산한다(m). */
const MOVE_MIN_M = 1.2;

export function useNavigation(spec: VehicleSpec | null) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [notice, setNotice] = useState<string | null>(null);

  const [current, setCurrent] = useState<SnapResult | null>(null);
  const [origin, setOrigin] = useState<SnapResult | null>(null);
  const [dest, setDest] = useState<SnapResult | null>(null);
  const [plan, setPlan] = useState<RoutePlan | null>(null);
  const [fastPlan, setFastPlan] = useState<RoutePlan | null>(null);
  const [offRoute, setOffRoute] = useState(false);
  const [lenient, setLenient] = useState(false);
  const [simSpeed, setSimSpeed] = useState(0);
  /** 이탈을 감지하고 새 경로를 내는 중 (와이어프레임 06) */
  const [rerouting, setRerouting] = useState(false);
  /** 차량 폭 조건으로 닿는 경로가 없다 (와이어프레임 13) */
  const [noRoute, setNoRoute] = useState(false);
  /**
   * 현장에서 통행 불가로 신고한 구간 (와이어프레임 16·17).
   * ★ 그래프에서 **뺀다** — `buildAdjacency` 의 `excluded` 참조.
   */
  const [blocked, setBlocked] = useState<ReadonlySet<string>>(() => new Set());
  /** 경로 시작부터 온 거리(m). 위치 추정기가 낸다. 경로가 없거나 이탈이면 null */
  const [driven, setDriven] = useState<number | null>(null);
  /** 재동기화 횟수. 바뀌면 음성이 말하던 것을 끊고 새 자리 안내를 낸다 */
  const [jumpSeq, setJumpSeq] = useState(0);
  const [lastJumpM, setLastJumpM] = useState(0);
  const [posMode, setPosMode] = useState<PosMode>("gpsSim");
  /**
   * 차량 경로의 끝이 어디인가 (DECISIONS §214-2).
   *   alt=false  사건 지점에 붙은 노드까지 간다
   *   alt=true   거기까지 못 가서 **닿는 가장 가까운 노드**(대체 접근 지점)에 댄다
   * walkM 은 경로 끝 → 사건 지점 **직선** 거리다.
   */
  const [access, setAccess] = useState<{ alt: boolean; walkM: number } | null>(null);

  const live = useRef<LiveFix>({ lon: 0, lat: 0, brg: 0, on: false });
  /**
   * 마지막 측위의 수평 정확도(m). 모르면 `null`.
   *
   * ★ 2026-09-24 (PLAN §13 W13-2). 위치 자체는 `live`(ref)로만 흘러 React 가
   *   모르는데, **정확도는 화면 상태를 가른다**(08 GPS 약함). 그래서 이것만
   *   state 다. 갱신은 `onFix` 에서 **값이 임계를 넘나들 때만** 한다 —
   *   매 측위마다 setState 하면 1Hz 리렌더가 하나 더 붙는다.
   */
  const [gpsAccM, setGpsAccM] = useState<number | null>(null);
  const accRef = useRef<number | null>(null);
  const lastSnapAt = useRef(0);
  const lastPos = useRef<LngLat | null>(null);
  const curUid = useRef<string | null>(null);
  const planRef = useRef<RoutePlan | null>(null);
  planRef.current = plan;
  const phaseRef = useRef<Phase>("loading");
  phaseRef.current = phase;
  const geom: RouteGeom | null = useMemo(() => (plan ? routeGeom(plan) : null), [plan]);
  const geomRef = useRef<RouteGeom | null>(null);
  geomRef.current = geom;
  const prog = useRef<ProgressState | null>(null);
  /** 마지막 추정이 경로 위였나. 추측항법은 경로 위에서만 한다 */
  const onRouteRef = useRef(true);
  /** 측위가 드문 위치원인가(GPS · 흉내). 드물면 측위 사이를 추측항법으로 메운다 */
  const sparse = useRef(false);

  // ── ① 적재 — 한 번 돌고 끝난다(`useBundle`) ────────────────────
  const onLoaded = useCallback(() => setPhase("idle"), []);
  const { data, fatal, tracker, snapAt } = useBundle(onLoaded, setNotice);

  // 판정 기준 차량. `useFleet` 이 만들어 넘긴다.
  // ★ 되먹이지 않는다 — 2026-09-06 에 setState 로 밀어넣었다가
  //   무한 리렌더가 났다. 의존은 useFleet → useNavigation 한 방향이다.
  const active = spec ?? data?.spec ?? null;

  /**
   * 주변 사정을 **구간마다** 센 색인(`domain/pressure.ts`). 그래프 · 주변 사정이
   * 바뀔 때만 다시 센다 — 인접리스트보다 훨씬 덜 바뀐다.
   *
   * ★ 이것이 있어야 과속방지턱 · 보호구역이 **길을 고르기 전에** 비용에 닿는다.
   *   `domain/context.ts` 는 경로가 정해진 **뒤** 안내로만 쓴다 — 그것은 선택이 아니다.
   * ★ 지금은 압력 계수가 전부 0 이라 경로가 안 움직인다(`TUNING` · 근거 없음).
   *   배선만 세워 둔다.
   */
  const hazIdx = useMemo(
    () => (data ? buildHazardIndex(data.graph, data.context ?? null) : null),
    [data]);

  const adj: Adjacency | null = useMemo(
    () => (data && active
      ? buildAdjacency(data.graph, active, lenient, "safe", undefined, blocked, hazIdx)
      : null),
    [data, active, lenient, blocked, hazIdx]);
  const adjFast: Adjacency | null = useMemo(
    () => (data && active
      ? buildAdjacency(data.graph, active, lenient, "fastest", undefined, blocked, hazIdx)
      : null),
    [data, active, lenient, blocked, hazIdx]);

  const onFix = useCallback((f: Fix) => {
    const t = f.t ?? performance.now();
    let brg = live.current.brg;
    const p = lastPos.current;
    if (f.heading != null) { brg = f.heading; lastPos.current = [f.lon, f.lat]; }
    else if (p && distM(p, [f.lon, f.lat]) >= MOVE_MIN_M) {
      brg = bearing(p, [f.lon, f.lat]); lastPos.current = [f.lon, f.lat];
    } else if (!p) lastPos.current = [f.lon, f.lat];
    sparse.current = f.source === "gps" || f.source === "replay";
    // ★ 정확도는 **임계를 넘나들 때만** 올린다. 값 자체는 화면에 안 쓴다.
    const acc = f.accuracy ?? null;
    const was = accRef.current;
    accRef.current = acc;
    const cross = (a: number | null) => (a == null ? null : a > GPS_WEAK_M);
    if (cross(was) !== cross(acc)) setGpsAccM(acc);

    // ── 안내 중: 경로 위 진행을 추정한다 (§213-2) ──────────────
    const g = geomRef.current;
    const pl = planRef.current;
    if (g && pl && phaseRef.current === "guiding") {
      const r = locate(g, { lon: f.lon, lat: f.lat, heading: f.heading, t }, prog.current);
      prog.current = r.state;
      const res = r.result;
      onRouteRef.current = res.onRoute;
      // 마커는 경로 위 추정 자리. 이탈이면 GPS 그대로 — 경로에 억지로 붙이지 않는다
      live.current = res.onRoute
        ? { lon: res.point[0], lat: res.point[1], brg: res.bearing, on: true }
        : { lon: f.lon, lat: f.lat, brg, on: true };

      const now = performance.now();
      if (res.jumped) {
        setJumpSeq((n) => n + 1);
        setLastJumpM(Math.round(res.jumpM));
      } else if (now - lastSnapAt.current < SNAP_INTERVAL_MS) return;
      lastSnapAt.current = now;

      setOffRoute(!res.onRoute);
      if (res.onRoute) {
        setDriven(res.s);
        const e = pl.edges[res.edge];
        if (e) {
          let acc = 0;
          for (let i = 0; i < res.edge; i++) acc += pl.edges[i].length_m ?? 0;
          const L = e.length_m ?? 1;
          const f01 = Math.max(0, Math.min(1, (res.s - acc) / L));
          curUid.current = e.seg_uid;
          setCurrent({
            seg_uid: e.seg_uid, verdict: e.verdict, width_min_m: e.width_min_m,
            // 출발·도착 구간은 자른 사본이다 — 스냅 규약(원본 구간 비율)으로 옮긴다
            seg_label: e.seg_label, progress: fullProgress(e, pl.forward[res.edge] ? f01 : 1 - f01),
            dist_m: Math.round(res.lateralM * 100) / 100, bearing: res.bearing,
            bearingKnown: true, point: res.point, confident: true, onRoute: true,
          });
        }
        if (pl.lengthM - res.s <= ARRIVE_M) setPhase("arrived");
      } else {
        // 이탈 — 재탐색 출발점은 **실제 도로망** 위여야 한다. 구간 스냅으로 돌아간다
        const sn = tracker.current?.update(f.lon, f.lat, brg);
        if (sn && sn.confident && sn.dist_m <= SCOPE_M) { curUid.current = sn.seg_uid; setCurrent(sn); }
      }
      setNotice(null);
      return;
    }

    // ── 안내 전 · 경로 없음: 구간 스냅 ─────────────────────────
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
  }, [tracker]);

  // 경로가 바뀌면(산출 · 재탐색 · 우회) 추정을 새로 시작한다 — 새 경로는 현위치에서 시작한다
  useEffect(() => {
    prog.current = null;
    onRouteRef.current = true;
    setDriven(plan ? 0 : null);
  }, [plan]);

  // ── ③ 추측항법 — 드문 측위 사이를 메운다(`useDeadReckoning`) ────
  useDeadReckoning({ phase, geom, prog, sparse, onRoute: onRouteRef, live });

  // ── ② 위치원 — gps · 흉내 · 경로 따라가기(`usePositionSource`) ──
  const onSimEnd = useCallback(() => { setSimSpeed(0); setPhase("arrived"); }, []);
  const { teleport, forget } = usePositionSource({
    phase, simSpeed, plan, posMode, onFix, onEnd: onSimEnd, onNotice: setNotice,
  });

  const route = useCallback((
    from: SnapResult, to: SnapResult, keepGuiding = false,
    adjOverride?: { safe: Adjacency; fast: Adjacency },
  ) => {
    const A = adjOverride?.safe ?? adj;
    const F = adjOverride?.fast ?? adjFast;
    if (!data || !A) return false;
    // ★ 투영 · 대체 접근 지점 · 빠른 경로는 `domain/routeSolve` 가 순수하게 푼다.
    //   여기서는 그 결과를 상태로 옮기기만 한다.
    const sol = solveRoute(data.graph, A, F, from.point, to.point);
    if (!sol) {
      // ★ 문구를 「연결성 우선으로 바꿔봐라」 에서 상태로 옮겼다. 폭 조건을
      //   푸는 것은 사람이 정할 일이지 화면이 권할 일이 아니다(와이어프레임 13).
      setNoRoute(true);
      setAccess(null);
      return false;
    }
    setNoRoute(false);
    setAccess({ alt: sol.alt, walkM: sol.walkM });
    tracker.current?.setRoute(routeUids(sol.plan));
    setPlan(sol.plan);
    setFastPlan(sol.fast);
    setOffRoute(false); setNotice(null);
    // ★ 여기서 멈춘다. 사용자가 "안내 시작" 을 눌러야 guiding 이 된다.
    //   주행 중 재탐색·우회는 멈추지 않는다.
    if (!keepGuiding) setPhase("preview");
    return true;
  }, [data, adj, adjFast, tracker]);

  // ── 이탈 → 재탐색 (와이어프레임 06) ──────────────────────────
  // ★ 이탈을 알리기만 하고 끝내지 않는다. 짧게 「재탐색 중」 을 보인 뒤
  //   현위치에서 목적지로 다시 낸다. 곧바로 바꾸면 한 번 삐끗한 스냅에
  //   경로가 흔들린다 — 이탈이 1.5초 이어질 때만 바꾼다.
  const REROUTE_MS = 1500;
  useEffect(() => {
    if (phase !== "guiding" || !offRoute || !dest || !current) return;
    setRerouting(true);
    const t = setTimeout(() => {
      route(current, dest, true);
      setRerouting(false);
    }, REROUTE_MS);
    return () => { clearTimeout(t); setRerouting(false); };
  }, [phase, offRoute]); // eslint-disable-line react-hooks/exhaustive-deps

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
  }, [snapAt, origin, phase, route, tracker]);

  /**
   * 출발지를 둔다 — 안전센터 좌표(와이어프레임 00).
   * ★ 출동은 안전센터에서 나간다. 현위치(GPS)는 주행 중 위치에 쓴다.
   */
  const setOriginAt = useCallback((lon: number, lat: number): boolean => {
    const s = snapAt(lon, lat);
    if (!s) { setNotice("출발지가 스코프 밖이다 — 도로에서 60m 안이어야 한다"); return false; }
    setOrigin(s); setCurrent(s); curUid.current = s.seg_uid;
    lastPos.current = null;
    live.current = { lon: s.point[0], lat: s.point[1], brg: s.bearing, on: true };
    setPlan(null); setFastPlan(null); setNoRoute(false);
    tracker.current?.setRoute(null);
    setPhase((p) => (p === "loading" ? p : "picked"));
    return true;
  }, [snapAt, tracker]);

  /** 도착지(사건 위치)를 둔다. **경로는 아직 안 낸다** — 차량을 먼저 고른다. */
  const setDestAt = useCallback((lon: number, lat: number): boolean => {
    const s = snapAt(lon, lat);
    if (!s) { setNotice("사건 위치가 스코프 밖이다 — 동명동과 접근회랑 안이어야 한다"); return false; }
    setDest(s); setPlan(null); setFastPlan(null); setNoRoute(false);
    setNotice(null);
    return true;
  }, [snapAt]);

  /** 출발·도착을 맞바꾼다(와이어프레임 00 「출발·도착 바꾸기」). */
  const swap = useCallback(() => {
    if (!origin || !dest) return;
    const o = origin;
    setOrigin(dest); setDest(o); setCurrent(dest);
    live.current = { lon: dest.point[0], lat: dest.point[1], brg: dest.bearing, on: true };
    setPlan(null); setFastPlan(null);
  }, [origin, dest]);

  /** 두 경로(안전·빠른)를 낸다. 차량을 고른 뒤 부른다(와이어프레임 01 → 02). */
  const computeRoutes = useCallback((): boolean => {
    if (!origin || !dest) {
      setNotice("출발지와 사건 위치를 먼저 정해라");
      return false;
    }
    return route(origin, dest);
  }, [origin, dest, route]);

  /**
   * 통행 불가 신고 → 우회 (와이어프레임 16 → 17).
   * ★ 그 구간을 그래프에서 빼고 **현위치에서** 다시 낸다. 새 인접리스트를
   *   여기서 바로 구워 넘긴다 — `blocked` 상태가 반영된 `adj` 는 다음
   *   렌더에야 생기므로 기다리면 옛 그래프로 한 번 더 막힌 길을 낸다.
   */
  const blockEdge = useCallback((uid: string): boolean => {
    if (!data || !active || !dest) return false;
    const next = new Set(blocked); next.add(uid);
    setBlocked(next);
    const safe = buildAdjacency(data.graph, active, lenient, "safe", undefined, next, hazIdx);
    const fast = buildAdjacency(data.graph, active, lenient, "fastest", undefined, next, hazIdx);
    const from = current ?? origin;
    if (!from) return false;
    return route(from, dest, phase === "guiding", { safe, fast });
  }, [data, active, dest, blocked, lenient, current, origin, phase, route, hazIdx]);

  /**
   * 시연 — 막아도 우회(또는 대체 접근 지점)가 남는 좁은 구간을 고른다(§214-2).
   * 현위치 앞쪽 구간에서 폭 좁은 순. 다 막히면 제일 좁은 것.
   */
  const pickDetourable = useCallback((pl: RoutePlan) => {
    const d = driven ?? 0;
    let acc = 0;
    const ahead: { e: RoutePlan["edges"][number]; i: number }[] = [];
    pl.edges.forEach((e, i) => { if (acc + (e.length_m ?? 0) > d) ahead.push({ e, i }); acc += e.length_m ?? 0; });
    const byWidth = [...ahead].sort((x, y) => (x.e.width_min_m ?? 99) - (y.e.width_min_m ?? 99));
    if (data && active && dest) {
      const from = current ?? origin;
      for (const { e } of byWidth.slice(0, 12)) {
        const A = buildAdjacency(data.graph, active, lenient, "safe", undefined, new Set([...blocked, e.seg_uid]), hazIdx);
        if (!from) break;
        if (reaches(data.graph, A, from.point, dest.point)) return e;
      }
    }
    return (byWidth[0] ?? { e: pl.edges[0] }).e;
  }, [data, active, dest, current, origin, lenient, blocked, driven, hazIdx]);

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
  }, [plan, fastPlan, tracker]);

  /** 안내를 시작한다. `preview` 에서 사용자가 누른다. */
  const start = useCallback(() => {
    const pl = planRef.current;
    if (!pl) return;
    // ★ 2026-09-22. 첫 화면에서 차가 옆으로 누워 있었다 — 출발지 스냅의 방위각은
    //   **구간이 그려진 방향**이지 경로의 진행 방향이 아니다. 경로 첫 방위로 맞춘다.
    const g = routeGeom(pl);
    const q = pointAtM(g, 0);
    live.current = { lon: q.point[0], lat: q.point[1], brg: q.bearing, on: true };
    setPhase("guiding");
  }, []);

  const reset = useCallback(() => {
    setPlan(null); setFastPlan(null); setOrigin(null); setDest(null);
    setCurrent(null); setSimSpeed(0); setOffRoute(false); setNotice(null);
    setNoRoute(false); setRerouting(false); setBlocked(new Set());
    setDriven(null); prog.current = null; setAccess(null);
    forget();
    lastPos.current = null; curUid.current = null;
    live.current.on = false;
    tracker.current?.reset();
    setPhase("idle");
  }, [forget, tracker]);

  /** 경로 끝까지 남은 거리(m). 최종 접근(05) 판단에 쓴다 */
  const remainM = useMemo(() => {
    if (!plan) return null;
    const d = phase === "guiding" || phase === "arrived"
      ? driven : progressAlongRoute(plan, current);
    return Math.max(0, plan.lengthM - (d ?? 0));
  }, [plan, current, driven, phase]);

  return {
    phase, fatal, notice, data, live, gpsAccM,
    current, origin, dest, plan, fastPlan, offRoute,
    lenient, setLenient, simSpeed, setSimSpeed,
    rerouting, noRoute, blocked, remainM,
    driven, jumpSeq, lastJumpM, posMode, setPosMode, teleport, access, pickDetourable,
    pick, snapAt, recompute, choose, start, reset,
    setOriginAt, setDestAt, swap, computeRoutes, blockEdge,
  };
}
