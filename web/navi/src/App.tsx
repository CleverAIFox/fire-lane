/**
 * App.tsx — 훅을 잇는다. **계산도 그림도 여기서 하지 않는다.**
 *
 *   domain/     계산 (순수)    좌표·제원·비용·A*·스냅·회전·속도·검색·**상태표**
 *   infra/      바깥 세계      fetch · geolocation · 음성 · Mapbox
 *   app/        배선           useNavigation · useVoice · useHudData
 *                              useScreens · useFleet · useShare
 *   components/ 지도           NaviMap · layers
 *   ui/         화면           TopBar · Sheet · 패널 · 칩 · DevBar
 *
 * ── 흐름 (지혜님 와이어프레임 2026-09-21) ────────────────────────
 *   00 출동 정보 입력 ─▶ 01 출동 차량 선택 ─▶ 02 경로 비교 ─▶ 03~23 주행
 *
 * ★ 09-05 판은 출발지가 현위치였다. 09-21 판은 **안전센터**다 — 출동은
 *   센터 차고에서 나간다. 현위치(GPS)는 주행 중 위치로만 쓴다.
 *
 * ★ 주행 화면의 상태(재탐색 · 골목 · 최종 접근 · 도착 …)는 여기서 가르지
 *   않는다. 신호를 모아 `domain/status.ts::deriveStatus` 에 넘기고, 나온
 *   한 줄을 `TopBar` 가 그린다. 18장이 그 한 줄로 갈린다.
 *
 * ── 넷을 떼었다 (2026-09-25 · PLAN §1 #130) ─────────────────────
 * ★ 640줄로 길이 상한(600)을 넘었다. **머리말이 「계산도 그림도 여기서 하지 않는다」 고
 *   적어 놓고 둘 다 들고 있었다** — 비교 카드 문장, 바탕색, 연기 keyframes, 시계 훅.
 *   이 파일에는 시험이 없으니 계산을 옮기지 않고 **상태를 안 지는 것**부터 뗀다.
 *
 *     `ui/routeOption.ts`   경로 하나 → 비교 카드 한 벌 (문장 포함)
 *     `ui/appShell.tsx`     바탕 · 토스트 · 차량 칩 · Center · 연기 CSS
 *     `app/useNow.ts`       초 단위 시계
 *     `app/useFading.ts`    값이 바뀌면 보이고 잠시 뒤 사라진다
 *     `ui/tokens.ts`        hhmm · hhmmss — `OpsApp.tsx` 와 **글자까지 같던** 것
 *     `domain/fleetName.ts` 센터 이름 줄이기 — 같은 이유
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NaviMap, type MapMarks, type MapNote } from "./components/NaviMap";
import { useNavigation } from "./app/useNavigation";
import { useVoice } from "./app/useVoice";
import { useHudData } from "./app/useHudData";
import { useScreens } from "./app/useScreens";
import { useFleet } from "./app/useFleet";
import { useShare } from "./app/useShare";
import { useOpsUplink, type UnitSnapshot } from "./app/useOpsUplink";
import { compareKind, compareMarks, sameRoute } from "./domain/compare";
import { cumulative, pointAlong } from "./domain/geo";
import { requiredWidth } from "./domain/vehicle";
import { STATUS, deriveStatus, type StatusKey } from "./domain/status";
import type { LngLat } from "./domain/geo";
import type { GraphEdge, RoutePlan, VehicleSpec } from "./domain/types";
import { useNow } from "./app/useNow";
import { useFading } from "./app/useFading";
import { TopBar } from "./ui/TopBar";
import { MapControls } from "./ui/MapControls";
import { RemainPill } from "./ui/RemainPill";
import { StatusCard } from "./ui/StatusCard";
import { ShareChip } from "./ui/ShareChip";
import { Legend } from "./ui/Legend";
import { DevBar } from "./ui/DevBar";
import { readHandoff, routeOf } from "./domain/handoff";
import { PlanHeader, TimeBox } from "./ui/Sheet";
import { RouteBrief } from "./ui/RouteCompare";
import { WaitPanel } from "./ui/WaitPanel";
import { routeOption } from "./ui/routeOption";
import { Center, SMOKE_CSS, shell, toast, vehChip } from "./ui/appShell";
import { BottleneckPanel } from "./ui/BottleneckPanel";
import { Truck } from "./ui/icons";
import { C, hhmm, hhmmss } from "./ui/tokens";
import { routeHazards } from "./domain/context";
import { shortStation } from "./domain/fleetName";
import { grayReason } from "./ui/verdictMeaning";
import { segmentReason } from "./ui/clearanceMeaning";

/** 병목 탭을 띄우는 앞 거리(m). 와이어프레임 04 가 「전방 300m」 다 */
const BOTTLENECK_AHEAD_M = 400;
/** 「우회 경로 적용 완료」 를 띄워 두는 시간(ms) */
const DETOUR_SHOW_MS = 8000;
/** 통행 불가 신고 → 우회 계산까지 「전방 통행 불가」 를 보이는 시간(ms) */
const BLOCKED_SHOW_MS = 1800;

interface Incident { point: LngLat; label: string; sub: string | null; at: Date }

/**
 * 출발 센터 한 줄. ★ 2026-10-05 (§400) `ui/DispatchPanel` 에 있던 것을 옮겼다 —
 * 그 판이 지워졌고 쓰는 곳은 여기 하나다.
 */
interface StationOpt { id: string; name: string; addr: string }

export default function App() {
  const s = useScreens("wait");
  const fleet = useFleet();
  const n = useNavigation(fleet.spec);
  const now = useNow();
  // ★ 2026-09-22 (§214-3). 관제 화면(`?view=ops`)과 잇는다. 상태 스냅숏은 아래에서 채운다
  const [snap, setSnap] = useState<UnitSnapshot | null>(null);
  const up = useOpsUplink(snap);
  const share = useShare(up);

  const [voice, setVoice] = useState(true);
  const [firstPerson, setFirstPerson] = useState(true);
  const [tint, setTint] = useState(false);
  const [cmd, setCmd] = useState<{ n: number; kind: "in" | "out" | "north" | "focus"; at?: LngLat } | null>(null);
  const [injected, setInjected] = useState<StatusKey | null>(null);
  const [stationId, setStationId] = useState<string | null>(null);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [bnOpen, setBnOpen] = useState(false);
  const [bnForced, setBnForced] = useState<string | null>(null);
  const [blockedPending, setBlockedPending] = useState(false);
  const [detourAt, setDetourAt] = useState<number | null>(null);
  const [arrivedAt, setArrivedAt] = useState<string | null>(null);
  const [wantRoute, setWantRoute] = useState(0);
  // ★ 2026-09-24 (PLAN §13 W13-1). 종전 `!== "0"` — **`?dev=0` 을 명시하지 않으면
  //   항상 켜짐**이었다. `web/index.html` 의 내비 링크에 그 인자가 없으므로 배포본이
  //   시연 막대를 달고 나갔다. 운전석에서 손이 스치면 ▶ 가 눌리고 **모의 주행이 실제
  //   GPS 를 대체한다**(useNavigation 이 replay 소스로 갈아탄다). 화면의 차가
  //   운전자가 아니게 된다. 켜는 쪽을 명시하게 뒤집는다.
  // ★ 2026-10-04 (§386). 종전에는 `new URLSearchParams(location.search)` 가 이
  //   파일 안에서만 **네 번** 따로 불렸다(사건 · 차종 · 센터 · dev). 「지령이
  //   왔는가」를 물으려면 그 넷을 다 봐야 했고, 그래서 아무도 안 물었다.
  const hand = useMemo(() => readHandoff(location.search), []);
  const dev = hand.dev;
  // ★ 경로는 **관제가 정한다.** 기사 손이 없으므로 상태도 없다(§400).
  const order = routeOf(hand);
  const choice = order.mode;

  // ★ `?demo=1` — 발표용. 경로 주행으로 바꾼다. 폐루프 검수는 `gpsSim` 이
  //   정본이고(§213-3) 이것은 **보여주기 전용**이라 기본값을 안 바꾼다.
  // ★ 의존에 `n` 전체가 아니라 **그 설정자 하나**를 넣는다. `useState` 의
  //   설정자는 안정적이라 이 효과가 한 번만 돌고, 억제를 안 써도 된다 —
  //   억제는 검사를 끄는 것이고 끈 이유는 영영 안 지워진다(§suppress).
  const setPosMode = n.setPosMode;
  useEffect(() => {
    if (hand.demo) setPosMode("route");
  }, [hand.demo, setPosMode]);

  const spec = fleet.spec ?? n.data?.spec ?? EMPTY_SPEC;
  // ★ 2026-09-28 (§279-4). `?? {}` 가 매 렌더 **새 객체**를 만들어 아래 두
  //   memo(175 · 269)의 의존이 매번 바뀌었다 — 캐시가 한 번도 안 맞았다.
  //   eslint 가 없던 동안 아무도 몰랐다.
  const style = useMemo(() => n.data?.graph.style ?? {}, [n.data?.graph.style]);
  const need = requiredWidth(spec);
  const vehicleKind = fleet.current?.label ?? spec.kind ?? "소방차";
  const guiding = n.phase === "guiding";
  const arrived = n.phase === "arrived";

  // ── 출발지 — 안전센터 ─────────────────────────────────────────
  const stations: (StationOpt & { point: LngLat })[] = useMemo(() => {
    const fc = n.data?.stations;
    if (!fc) return [];
    return fc.features
      .filter((f) => f.properties?.kind === "center" && f.geometry.type === "Point")
      .map((f, i) => ({
        id: String(i),
        name: shortStation(String(f.properties?.["소방서 및 안전센터명"] ?? "안전센터")),
        addr: String(f.properties?.["주소"] ?? ""),
        point: (f.geometry as GeoJSON.Point).coordinates as LngLat,
      }));
  }, [n.data]);
  const station = stations.find((x) => x.id === stationId) ?? stations[0] ?? null;

  useEffect(() => {
    if (!station || n.origin || n.phase === "loading") return;
    n.setOriginAt(station.point[0], station.point[1]);
  }, [station, n.origin, n.phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 사건 위치 — **지령으로만 온다** (§400) ────────────────────
  // ★ 2026-10-05. 종전 주석은 「URL 로 **받을 수 있다**」였고 검색·지도
  //   선택이라는 다른 길이 둘 더 있었다. 그 둘을 지웠으므로 이것이
  //   유일한 길이다 — `n.setDestAt` 을 부르는 자리가 파일에 하나뿐이고,
  //   시험이 그 수를 센다.
  useEffect(() => {
    if (!n.data || incident || !hand.incident) return;
    const [lon, lat] = hand.incident;
    if (n.setDestAt(lon, lat)) {
      setIncident({ point: [lon, lat], label: hand.label ?? "접수 위치",
                    sub: hand.sub, at: new Date() });
    }
  }, [n.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 관제의 출동 지령 — 차종 · 센터도 URL 로 온다 (§214-3) ─────────
  useEffect(() => {
    const v = hand.vehicle;
    if (v && fleet.fleet?.vehicles.some((x) => x.id === v)) fleet.select(v);
  }, [fleet.fleet]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const st = hand.station;
    if (!st || !stations.length) return;
    const hit = stations.find((x) => x.name === st || x.name.includes(st));
    if (hit) { setStationId(hit.id); n.setOriginAt(hit.point[0], hit.point[1]); }
  }, [stations.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // ★ 2026-10-05 (§400). **운전석에서 지도를 찍어도 아무 일도 안 난다.**
  //   종전에는 `armed === "dest"` 일 때 목적지가 바뀌었다. 목적지는 관제가
  //   정하므로 그 손을 들어냈다 — 핸들러를 묶는 대신 **없앴다.**
  const onMapClick = useCallback(() => {}, []);

  // ── 01 → 02: 차량을 고른 **뒤** 렌더에서 경로를 낸다 ──────────────
  // ★ 고른 차의 제원이 인접리스트에 반영되는 것은 다음 렌더다. 같은 클릭
  //   안에서 부르면 옛 차의 경로가 난다.
  useEffect(() => {
    if (!wantRoute) return;
    if (n.computeRoutes()) s.open("brief");
  }, [wantRoute]); // eslint-disable-line react-hooks/exhaustive-deps

  // ★ 2026-10-05 (§400). 종전에는 **차량 화면의 확인 버튼**이 이 수를 올렸다.
  //   그 화면이 없어졌으므로 **지령이 다 차면 기계가 올린다** — 사건 · 출발 ·
  //   차량 셋이 서면 경로를 내고 설명 화면으로 간다. 기사가 누를 것은 없다.
  useEffect(() => {
    if (s.screen !== "wait" || !incident || !n.origin || !fleet.spec) return;
    setWantRoute((x) => x + 1);
  }, [s.screen, incident, n.origin, fleet.spec]);

  // ── 경로 비교 카드 ────────────────────────────────────────────
  // ★ 2026-09-23 (§220). 「같다」 를 여기서 판단해 **화면에 그대로 넘긴다.** 종전엔
  //   같으면 둘째 경로를 null 로 지워 화면이 「둘째 경로가 없다」 로 읽었다 — 없는 것과
  //   같은 것은 다른 말이다(멘토링 §219: 겹치면 「안전하면서 빠른 추천 경로」).
  const compare = useMemo(() => {
    const a = n.plan;
    if (!a) return null;
    const same = compareKind(a, n.fastPlan) === "same";
    const b = n.fastPlan && !same ? n.fastPlan : null;
    return {
      same,
      safe: routeOption(a, need, b, true, n.access, n.data?.context ?? null),
      fast: b ? routeOption(b, need, a, false, n.access, n.data?.context ?? null) : null,
    };
  }, [n.plan, n.fastPlan, need, n.access, n.data]);

  // ── 주행 ──────────────────────────────────────────────────────
  // ★ §216-3 경로 위 주변 사정 — 경로가 바뀔 때만 다시 센다
  const hazards = useMemo(() => (n.plan ? routeHazards(n.plan, n.data?.context ?? null) : []),
    [n.plan, n.data]);
  const v = useVoice({
    graph: n.data?.graph ?? null, spec,
    plan: guiding ? n.plan : null,
    driven: n.driven, jumpSeq: n.jumpSeq, offRoute: n.offRoute,
    style, enabled: voice, hazards,
    // ★ 2026-10-03 (DECISIONS §366-3). 영상 소견을 음성까지 잇는다. 지금
    //   `cvNow` 는 **늘 null** 이다 — 측정을 넣는 자리가 `useNavigation` 의
    //   둘째 인자 하나이고 아직 아무도 안 넣는다(CV 쪽 산출물이 없다).
    //   그 한 자리를 비워 두는 것이 이 배선의 뜻이다: **생기는 날 한 줄이다.**
    cv: n.cvNow,
  });
  const hud = useHudData({
    spec, style, plan: n.plan, fastPlan: n.fastPlan,
    current: n.current, driven: guiding || arrived ? n.driven : null,
    lenient: n.lenient, offRoute: n.offRoute,
    maneuver: v.maneuver, maneuverDistM: v.distM, maneuverText: v.banner,
  });

  // 병목 — 앞 400m 안의 확인 필요 구간(또는 여유 0.5m 미만)
  const bottleneckEdge: GraphEdge | null = useMemo(() => {
    if (!n.plan) return null;
    if (bnForced) return n.plan.edges.find((e) => e.seg_uid === bnForced) ?? null;
    const driven = n.driven ?? 0;
    let acc = 0;
    for (const e of n.plan.edges) {
      const L = e.length_m ?? 0;
      if (acc + L >= driven && acc - driven <= BOTTLENECK_AHEAD_M) {
        const tight = e.width_min_m != null && e.width_min_m - need < 0.5;
        if (e.verdict === "needs_cv" || tight) return e;
      }
      acc += L;
      if (acc - driven > BOTTLENECK_AHEAD_M) break;
    }
    return null;
  }, [n.plan, n.driven, need, bnForced]);

  const bottleneck = useMemo(() => {
    const e = bottleneckEdge;
    if (!e || !n.plan) return null;
    const driven = n.driven ?? 0;
    let acc = 0;
    for (const x of n.plan.edges) { if (x.seg_uid === e.seg_uid) break; acc += x.length_m ?? 0; }
    return {
      segUid: e.seg_uid,
      segLabel: e.seg_label ?? e.road_name ?? e.seg_uid,
      aheadM: Math.max(0, acc - driven),
      widthM: e.width_min_m, requiredM: need, lengthM: e.length_m,
      coverage: e.width_cov ?? null, samples: e.n_sample ?? null,
      cctvDistM: e.cctv_dist_m ?? null,
      grayReason: grayReason(e)?.long ?? null,
      // ★ 2026-09-23 (§220) 색만이 아니라 사유를. 판정마다 한 줄 — 없으면 null 이고 패널이 뺀다
      reason: segmentReason(e, spec),
      // ★ `?? null` — 옛 발행물의 `undefined` 를 0 이 아니라 **모름**으로 옮긴다
      park: e.park ?? null,
      ecam: e.ecam ?? null,
      verdictLabel: style[e.verdict]?.label ?? e.verdict,
      verdictColor: style[e.verdict]?.color ?? C.panelInk,
    };
  }, [bottleneckEdge, n.plan, n.driven, need, spec, style]);

  /** 병목 구간의 가운데 — 관제 공유 좌표 · 카메라 초점 */
  const bottleneckAt: LngLat | null = useMemo(() => {
    const e = bottleneckEdge;
    if (!e || e.coords.length < 2) return null;
    const cum = cumulative(e.coords);
    return pointAlong(e.coords, cum, cum[cum.length - 1] / 2).point;
  }, [bottleneckEdge]);

  // ★ 2026-09-22 (§214-2). 병목 상세를 열면 카메라가 그 구간으로 간다(와이어프레임 04 —
  //   병목이 화면 가운데). 1인칭을 풀어야 카메라 루프가 덮어쓰지 않는다. 닫으면 돌아온다.
  useEffect(() => {
    if (!guiding) return;
    if (bnOpen && bottleneckAt) {
      setFirstPerson(false);
      setCmd((c) => ({ n: (c?.n ?? 0) + 1, kind: "focus", at: bottleneckAt }));
    } else if (!bnOpen) setFirstPerson(true);
  }, [bnOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // 우회 표시는 몇 초 뒤 내린다
  useEffect(() => {
    if (!detourAt) return;
    const t = setTimeout(() => setDetourAt(null), DETOUR_SHOW_MS);
    return () => clearTimeout(t);
  }, [detourAt]);

  // 도착 → 도착 보고를 관제에 보낸다(23)
  useEffect(() => {
    if (!arrived) { setArrivedAt(null); return; }
    setArrivedAt(hhmm(new Date()));
    setBnOpen(false);
    const t = setTimeout(() => share.share("arrival",
      `${incident?.label ?? "사건 지점"} 접근 지점 도착 · ${vehicleKind}`,
      n.plan?.coords[n.plan.coords.length - 1] ?? null), 1500);
    return () => clearTimeout(t);
  }, [arrived]); // eslint-disable-line react-hooks/exhaustive-deps

  // ★ 2026-09-24 (PLAN §13 W13-6). 아래 1.8초 타이머에 **정리가 없었다.**
  //   신고 직후 「처음부터」를 누르면 초기화된 그래프 위에서 늦게 터져
  //   새 출동이 엉뚱한 구간을 막은 채 시작한다. `useShare` 는 같은 일을
  //   ref + clear 로 제대로 거두는데 여기만 맨손이었다.
  const blockTimer = useRef(0);
  useEffect(() => () => { if (blockTimer.current) clearTimeout(blockTimer.current); }, []);

  const reportBlocked = useCallback(() => {
    if (!bottleneck) return;
    const uid = bottleneck.segUid;
    setBlockedPending(true);
    setBnOpen(false);
    share.share("blocked", `${bottleneck.segLabel} 통행 불가 신고 · ${vehicleKind}`, bottleneckAt);
    if (blockTimer.current) clearTimeout(blockTimer.current);
    blockTimer.current = window.setTimeout(() => {
      blockTimer.current = 0;
      const ok = n.blockEdge(uid);
      setBlockedPending(false);
      setBnForced(null);
      if (ok) setDetourAt(Date.now());
    }, BLOCKED_SHOW_MS);
  }, [bottleneck, n, share, bottleneckAt, vehicleKind]);

  const statusKey = deriveStatus({
    phase: guiding ? "guiding" : arrived ? "arrived" : "other",
    choice, rerouting: n.rerouting, noRoute: n.noRoute && (guiding || arrived),
    blockedPending, detourFresh: detourAt != null, accessAlt: !!n.access?.alt,
    blockedAny: n.blocked.size > 0,
    arrivalAcked: share.info.kind === "arrival" && share.info.state === "acked",
    remainM: n.remainM,
    onUnverified: n.current?.verdict === "unknown" && !!n.current.onRoute,
    injected,
    gpsAccM: n.gpsAccM,
  });
  const st = STATUS[statusKey];
  const blockedEdges = useMemo(
    () => (n.data ? n.data.graph.edges.filter((e) => n.blocked.has(e.seg_uid)) : []),
    [n.data, n.blocked]);

  const endPoint: LngLat | null = n.plan?.coords.length
    ? n.plan.coords[n.plan.coords.length - 1] : null;
  const marks: MapMarks = {
    origin: s.planning ? (n.origin?.point ?? station?.point ?? null) : null,
    incident: incident?.point ?? null,
    approach: !s.planning ? endPoint : null,
    approachLabel: n.access?.alt ? "대체 접근 지점" : "최종 차량 접근 지점",
  };
  // 02 — 공통 구간 · 확인 필요 표지
  const notes: MapNote[] = useMemo(() => {
    if (s.screen !== "brief" || !n.plan || !n.fastPlan || sameRoute(n.plan, n.fastPlan)) return [];
    const base = choice === "safe" ? n.plan : n.fastPlan;
    const other = choice === "safe" ? n.fastPlan : n.plan;
    const m = compareMarks(base, other);
    const out: MapNote[] = [];
    if (m.commonAt) out.push({ id: "common", at: m.commonAt, kind: "common", text: "공통 구간" });
    if (m.checkAt) out.push({ id: "check", at: m.checkAt, kind: "check", text: `확인 필요\n${m.checkM}m` });
    return out;
  }, [s.screen, n.plan, n.fastPlan, choice]);
  const finalLeg = !s.planning && endPoint && incident ? [endPoint, incident.point] : null;

  // ── 관제로 보낼 상태 (§214-3). 경로 참조는 경로가 바뀔 때만 바뀐다 ──
  const snapTitle = guiding || arrived ? (st.title ?? hud?.turnText ?? st.label) : "출동 준비";
  useEffect(() => {
    setSnap({
      vehicle: vehicleKind, station: station?.name ?? null,
      incident: incident ? { point: incident.point, label: incident.label } : null,
      pos: n.current?.point ?? n.origin?.point ?? null, brg: n.live.current.brg,
      status: guiding || arrived ? statusKey : "planning", title: snapTitle,
      remainM: n.remainM, etaText: hud?.etaText ?? null, route: n.plan?.coords ?? null,
    });
    // ★ `n.live.current` 는 ref 다. 의존에 넣으면 매 프레임 재실행되고, 안 넣어도
    //   읽는 시점 값은 최신이다. 필요한 필드는 아래에 개별로 걸었다.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- n.live 는 ref 다
  }, [vehicleKind, station?.name, incident, n.current, n.origin, statusKey, snapTitle,
      n.remainM, hud?.etaText, n.plan, guiding, arrived]);  

  // ★ 알림은 6초 뒤 내린다. 「위치 없음」 처럼 한 번 알면 되는 것이 주행 내내
  //   남아 남은 시간 알약 위를 가렸다(검수 스크린샷).
  const notice = useFading(n.notice, 6000);

  const reset = () => {
    // 늦게 터질 신고 타이머를 먼저 거둔다 — 새 출동의 그래프를 오염시킨다.
    if (blockTimer.current) { clearTimeout(blockTimer.current); blockTimer.current = 0; }
    n.reset(); share.reset();
    setIncident(null); setInjected(null); setBnOpen(false); setBnForced(null);
    setDetourAt(null); setBlockedPending(false);
    s.open("wait");
  };

  if (n.fatal) return <Center>★ {n.fatal}</Center>;
  if (n.phase === "loading" || !n.data) return <Center>불러오는 중…</Center>;

  const nowText = hhmm(now);
  const incidentText = incident ? hhmm(incident.at) : null;

  return (
    <div style={shell}>
      <style>{"@keyframes flspin{to{transform:rotate(360deg)}}" + SMOKE_CSS}</style>
      <NaviMap view={n.data.view} terrain={n.data.graph.terrain} live={n.live}
               plan={n.plan} altPlan={s.screen === "brief" ? (compare?.fast ? otherPlan(n, choice) : null) : null}
               style={style} look={st.route && !s.planning ? st.route : "solid"}
               blockedEdges={blockedEdges} marks={marks} finalLeg={finalLeg}
               mode={s.planning ? "plan" : "drive"} firstPerson={firstPerson}
               tint={tint} cmd={cmd} notes={notes} spec={spec}
               onMapClick={onMapClick}
               onUserPan={() => setFirstPerson(false)} />

      {/* ══ 대기 · 설명 — 출동 전 ═══════════════════════════════ */}
      {s.planning && (
        <PlanHeader
          title={s.screen === "brief" ? "출동 경로" : "출동 대기"}
          right={s.screen === "brief"
            ? <span style={vehChip}><Truck /> {vehicleKind}</span>
            : <TimeBox now={nowText} incident={incidentText} />} />
      )}

      {s.screen === "wait" && (
        <WaitPanel station={station?.name ?? null}
                   vehicle={fleet.fleet ? vehicleKind : null}
                   incident={incident?.label ?? null} />
      )}

      {s.screen === "brief" && compare && (
        <RouteBrief safe={compare.safe} fast={compare.fast} same={compare.same}
                    chosen={choice} fromOrder={order.fromOrder}
                    onConfirm={() => {
                      n.choose(choice);
                      n.start(); setFirstPerson(true);
                      s.open("drive");
                    }} />
      )}


      {/* ══ 03 ~ 23 — 주행 ══════════════════════════════════════ */}
      {!s.planning && hud && (
        <>
          <TopBar spec={st}
                  vars={{
                    last: hhmmss(new Date(now.getTime() - 12000)),
                    vehicle: vehicleKind, need: need.toFixed(1),
                    road: bottleneck?.segLabel ?? hud.currentLabel ?? "전방 구간",
                    len: String(Math.round(bottleneck?.lengthM ?? 45)),
                    walk: String(Math.round(n.access?.walkM ?? 0)),
                  }}
                  vehicleKind={vehicleKind}
                  turnKind={hud.turnKind} nextDistM={hud.nextDistM} roadName={hud.nextLabel}
                  nowText={nowText} etaText={hud.etaText} incidentText={incidentText}
                  arrivedText={arrivedAt}
                  injected={injected != null}
                  voiceOn={v.available ? voice : null}
                  onToggleVoice={() => setVoice((x) => !x)}
                  /* ★ 2026-10-05 (§400). 「경로 전환」을 **지웠다.** 주행 중에
                     기사가 경로를 바꾸면 그 순간 수동이 아니다 — 바꾸는 것은
                     관제가 새 지령을 보내는 것이다. */
                  onSwitchRoute={undefined} />
          <MapControls onCompass={() => setCmd((c) => ({ n: (c?.n ?? 0) + 1, kind: "north" }))}
                       onLocate={() => setFirstPerson(true)}
                       onZoomIn={() => setCmd((c) => ({ n: (c?.n ?? 0) + 1, kind: "in" }))}
                       onZoomOut={() => setCmd((c) => ({ n: (c?.n ?? 0) + 1, kind: "out" }))}
                       onLayers={() => setTint((x) => !x)} layersOn={tint} />
          <Legend style={style} open={tint} onToggle={() => setTint(!tint)} />
          {!st.noRemain && <RemainPill sec={hud.remainSec} m={hud.remainM} blank={!!st.blankRemain} />}
          {statusKey === "reroute" && (
            <StatusCard chip="경로 이탈 감지" title="새 경로를 찾는 중"
                        lines={["현재 위치를 기준으로", "자동 재탐색합니다."]}
                        foot="경로 계산 중… 잠시만 기다려 주세요" />
          )}
          {/* ★ 경로가 서지 않은 상태(재탐색 · 서버 오류 · 경로 없음 · 데이터 부족 ·
              통행 불가)와 도착 쪽 상태에서는 병목을 안 띄운다. 없는 경로의 병목이다. */}
          {bottleneck && st.route !== "pending" && !st.icon && statusKey !== "blocked" && (
            <BottleneckPanel {...bottleneck} open={bnOpen}
                             onToggle={() => setBnOpen((x) => !x)}
                             onShare={() => {
                               // 와이어프레임 18 — 공유하면 카드를 닫고 주행을 이어 간다
                               share.share("bottleneck",
                                 `${bottleneck.segLabel} 병목 · 폭 ${bottleneck.widthM?.toFixed(1) ?? "—"}m / 요구 ${need.toFixed(1)}m`,
                                 bottleneckAt);
                               setBnOpen(false);
                             }}
                             onReport={reportBlocked} />
          )}
          <ShareChip info={share.info} onRetry={() => share.share(share.info.kind ?? "bottleneck")} />
        </>
      )}

      {notice && <div style={toast}>{notice}</div>}
      {s.screen === "wait" && n.noRoute && (
        <div style={toast}>{vehicleKind} · 요구 폭 {need.toFixed(1)}m 를 만족하는 경로가 없다 — 관제가 다른 접근 지점을 정해야 한다</div>
      )}

      {dev && (
        <DevBar
          hint={`${s.planning ? `화면 ${s.screen}` : `상태 ${st.wf.join("·")}`} · 관제 ${up.present ? "●" : "○"}`}
          guiding={!s.planning}
          simSpeed={n.simSpeed} setSimSpeed={n.setSimSpeed}
          posMode={n.posMode} setPosMode={n.setPosMode}
          onTeleport={guiding && n.simSpeed > 0 ? () => n.teleport(200) : undefined}
          jumps={n.jumpSeq} lastJumpM={n.lastJumpM}
          lenient={n.lenient} setLenient={n.setLenient}
          firstPerson={firstPerson} setFirstPerson={setFirstPerson}
          onBottleneck={guiding && n.plan ? () => {
            // ★ 2026-09-22 (§214-2). 「제일 좁은 구간」 을 열었더니 그것이 **센터의 유일한
            //   출구**(다리 구간)라 신고하면 늘 우회 없음으로 끝났다 — 16 → 17 을 못 본다.
            //   앞쪽에서 좁은 순으로, **막아도 닿는 곳이 남는** 구간을 연다.
            const pick = n.pickDetourable(n.plan!);
            setBnForced(pick.seg_uid); setBnOpen(true);
          } : undefined}
          onReset={reset}
          injected={injected} setInjected={setInjected}
          failNext={share.failNext} setFailNext={share.setFailNext}
        />
      )}
    </div>
  );
}

// ── 도움 ────────────────────────────────────────────────────────

/** 비교 화면에서 선택 안 된 쪽 경로. `choose` 전이라 plan 이 안전 경로다 */
function otherPlan(n: { plan: RoutePlan | null; fastPlan: RoutePlan | null }, choice: "safe" | "fast") {
  return choice === "safe" ? n.fastPlan : n.plan;
}

const EMPTY_SPEC: VehicleSpec = {
  width_m: 0, wheelbase_m: null, turn_radius_m: null, clearance_m: 0,
};
