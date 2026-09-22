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
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { NaviMap, type MapMarks, type MapNote } from "./components/NaviMap";
import { useNavigation } from "./app/useNavigation";
import { useVoice } from "./app/useVoice";
import { useHudData } from "./app/useHudData";
import { useScreens } from "./app/useScreens";
import { useFleet } from "./app/useFleet";
import { useShare } from "./app/useShare";
import { useOpsUplink, type UnitSnapshot } from "./app/useOpsUplink";
import { compareMarks } from "./domain/compare";
import { cumulative, pointAlong } from "./domain/geo";
import { preparePois, searchPois, type PoiHit } from "./domain/search";
import { requiredWidth } from "./domain/vehicle";
import { travelSeconds } from "./domain/speed";
import { STATUS, deriveStatus, type StatusKey } from "./domain/status";
import type { LngLat } from "./domain/geo";
import type { GraphEdge, RoutePlan, VehicleSpec } from "./domain/types";
import { TopBar } from "./ui/TopBar";
import { MapControls } from "./ui/MapControls";
import { RemainPill } from "./ui/RemainPill";
import { StatusCard } from "./ui/StatusCard";
import { ShareChip } from "./ui/ShareChip";
import { Legend } from "./ui/Legend";
import { DevBar } from "./ui/DevBar";
import { SearchPanel } from "./ui/SearchPanel";
import { PlanHeader, TimeBox } from "./ui/Sheet";
import { DispatchPanel, type StationOpt } from "./ui/DispatchPanel";
import { VehiclePicker } from "./ui/VehiclePicker";
import { RouteCompare, type RouteOption } from "./ui/RouteCompare";
import { BottleneckPanel } from "./ui/BottleneckPanel";
import { Truck } from "./ui/icons";
import { C, F, fmtDur } from "./ui/tokens";
import { ruleSummary } from "./domain/rules";
import { hazardSummary, routeHazards } from "./domain/context";
import { grayReason } from "./ui/verdictMeaning";

/** 병목 탭을 띄우는 앞 거리(m). 와이어프레임 04 가 「전방 300m」 다 */
const BOTTLENECK_AHEAD_M = 400;
/** 「우회 경로 적용 완료」 를 띄워 두는 시간(ms) */
const DETOUR_SHOW_MS = 8000;
/** 통행 불가 신고 → 우회 계산까지 「전방 통행 불가」 를 보이는 시간(ms) */
const BLOCKED_SHOW_MS = 1800;

interface Incident { point: LngLat; label: string; sub: string | null; at: Date }

export default function App() {
  const s = useScreens("dispatch");
  const fleet = useFleet();
  const n = useNavigation(fleet.spec);
  const now = useNow();
  // ★ 2026-09-22 (§214-3). 관제 화면(`?view=ops`)과 잇는다. 상태 스냅숏은 아래에서 채운다
  const [snap, setSnap] = useState<UnitSnapshot | null>(null);
  const up = useOpsUplink(snap);
  const share = useShare(up);

  const [choice, setChoice] = useState<"safe" | "fast">("safe");
  const [voice, setVoice] = useState(true);
  const [firstPerson, setFirstPerson] = useState(true);
  const [tint, setTint] = useState(false);
  const [cmd, setCmd] = useState<{ n: number; kind: "in" | "out" | "north" | "focus"; at?: LngLat } | null>(null);
  const [injected, setInjected] = useState<StatusKey | null>(null);
  const [armed, setArmed] = useState<"origin" | "dest" | null>(null);
  const [stationId, setStationId] = useState<string | null>(null);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [bnOpen, setBnOpen] = useState(false);
  const [bnForced, setBnForced] = useState<string | null>(null);
  const [blockedPending, setBlockedPending] = useState(false);
  const [detourAt, setDetourAt] = useState<number | null>(null);
  const [arrivedAt, setArrivedAt] = useState<string | null>(null);
  const [wantRoute, setWantRoute] = useState(0);
  const dev = useMemo(() => new URLSearchParams(location.search).get("dev") !== "0", []);

  const spec = fleet.spec ?? n.data?.spec ?? EMPTY_SPEC;
  const style = n.data?.graph.style ?? {};
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

  // ── 사건 위치 — URL 로 받을 수 있다 (접수 시스템이 붙을 자리) ─────
  useEffect(() => {
    if (!n.data || incident) return;
    const q = new URLSearchParams(location.search);
    const at = q.get("incident");
    if (!at) return;
    const [lon, lat] = at.split(",").map(Number);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
    if (n.setDestAt(lon, lat)) {
      setIncident({ point: [lon, lat], label: q.get("label") ?? "접수 위치",
                    sub: q.get("sub"), at: new Date() });
    }
  }, [n.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 관제의 출동 지령 — 차종 · 센터도 URL 로 온다 (§214-3) ─────────
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const v = q.get("vehicle");
    if (v && fleet.fleet?.vehicles.some((x) => x.id === v)) fleet.select(v);
  }, [fleet.fleet]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const st = new URLSearchParams(location.search).get("station");
    if (!st || !stations.length) return;
    const hit = stations.find((x) => x.name === st || x.name.includes(st));
    if (hit) { setStationId(hit.id); n.setOriginAt(hit.point[0], hit.point[1]); }
  }, [stations.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const pois = useMemo(() => (n.data ? preparePois(n.data.dest) : []), [n.data]);
  const query = useCallback((q: string) => searchPois(pois, q), [pois]);
  const verdictOf = useCallback((h: PoiHit) => {
    const r = n.snapAt(h.point[0], h.point[1]);
    if (!r) return null;
    const st = style[r.verdict];
    return st ? { color: st.color, label: st.label } : null;
  }, [n, style]);

  const onMapClick = useCallback((lon: number, lat: number) => {
    if (s.screen !== "dispatch" || armed !== "dest") return;
    const r = n.snapAt(lon, lat);
    if (!r) { n.setDestAt(lon, lat); return; }   // 스코프 밖 안내는 훅이 낸다
    if (n.setDestAt(lon, lat)) {
      setIncident({ point: [lon, lat], label: r.seg_label ?? "지도에서 고른 지점",
                    sub: "지도 선택", at: new Date() });
      setArmed(null);
    }
  }, [s.screen, armed, n]);

  // ── 01 → 02: 차량을 고른 **뒤** 렌더에서 경로를 낸다 ──────────────
  // ★ 고른 차의 제원이 인접리스트에 반영되는 것은 다음 렌더다. 같은 클릭
  //   안에서 부르면 옛 차의 경로가 난다.
  useEffect(() => {
    if (!wantRoute) return;
    if (n.computeRoutes()) { setChoice("safe"); s.open("compare"); }
  }, [wantRoute]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 경로 비교 카드 ────────────────────────────────────────────
  const compare = useMemo(() => {
    const a = n.plan;
    if (!a) return null;
    const b = n.fastPlan && !samePlan(a, n.fastPlan) ? n.fastPlan : null;
    return {
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
      park: e.park ?? null,
      verdictLabel: style[e.verdict]?.label ?? e.verdict,
      verdictColor: style[e.verdict]?.color ?? C.panelInk,
    };
  }, [bottleneckEdge, n.plan, n.driven, need, style]);

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

  const reportBlocked = useCallback(() => {
    if (!bottleneck) return;
    const uid = bottleneck.segUid;
    setBlockedPending(true);
    setBnOpen(false);
    share.share("blocked", `${bottleneck.segLabel} 통행 불가 신고 · ${vehicleKind}`, bottleneckAt);
    setTimeout(() => {
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
    if (s.screen !== "compare" || !n.plan || !n.fastPlan || samePlan(n.plan, n.fastPlan)) return [];
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
  }, [vehicleKind, station?.name, incident, n.current, n.origin, statusKey, snapTitle,
      n.remainM, hud?.etaText, n.plan, guiding, arrived]); // eslint-disable-line react-hooks/exhaustive-deps

  // ★ 알림은 6초 뒤 내린다. 「위치 없음」 처럼 한 번 알면 되는 것이 주행 내내
  //   남아 남은 시간 알약 위를 가렸다(검수 스크린샷).
  const notice = useFading(n.notice, 6000);

  const reset = () => {
    n.reset(); share.reset();
    setIncident(null); setInjected(null); setBnOpen(false); setBnForced(null);
    setDetourAt(null); setBlockedPending(false); setChoice("safe");
    s.open("dispatch");
  };

  if (n.fatal) return <Center>★ {n.fatal}</Center>;
  if (n.phase === "loading" || !n.data) return <Center>불러오는 중…</Center>;

  const nowText = hhmm(now);
  const incidentText = incident ? hhmm(incident.at) : null;

  return (
    <div style={shell}>
      <style>{"@keyframes flspin{to{transform:rotate(360deg)}}" + SMOKE_CSS}</style>
      <NaviMap view={n.data.view} terrain={n.data.graph.terrain} live={n.live}
               plan={n.plan} altPlan={s.screen === "compare" ? (compare?.fast ? otherPlan(n, choice) : null) : null}
               style={style} look={st.route && !s.planning ? st.route : "solid"}
               blockedEdges={blockedEdges} marks={marks} finalLeg={finalLeg}
               mode={s.planning ? "plan" : "drive"} firstPerson={firstPerson}
               tint={tint} cmd={cmd} notes={notes}
               onMapClick={onMapClick}
               onUserPan={() => setFirstPerson(false)} />

      {/* ══ 00 · 01 · 02 — 출동 전 ══════════════════════════════ */}
      {s.planning && (
        <PlanHeader
          title={s.screen === "vehicle" ? "출동 차량 선택"
            : s.screen === "compare" ? "경로 비교" : "출동 정보 입력"}
          right={s.screen === "compare"
            ? <span style={vehChip}><Truck /> {vehicleKind}</span>
            : <TimeBox now={nowText} incident={incidentText} />} />
      )}

      {(s.screen === "dispatch" || s.screen === "search") && (
        <DispatchPanel station={station} stations={stations}
          onStation={(id) => {
            setStationId(id);
            const x = stations.find((y) => y.id === id);
            if (x) n.setOriginAt(x.point[0], x.point[1]);
          }}
          incidentLabel={incident?.label ?? null} incidentSub={incident?.sub ?? null}
          incidentAt={incidentText}
          armed={armed} onArm={setArmed}
          onSearch={() => s.open("search")}
          onSwap={() => n.swap()}
          canNext={!!incident && !!n.origin}
          onNext={() => s.open("vehicle")} />
      )}

      {s.screen === "search" && (
        <SearchPanel open onOpen={() => {}} onClose={() => s.open("dispatch")}
                     onQuery={query} verdictOf={verdictOf}
                     onPick={(h) => {
                       if (n.setDestAt(h.point[0], h.point[1])) {
                         setIncident({ point: h.point, label: h.name, sub: h.addr || null, at: new Date() });
                       }
                       s.open("dispatch");
                     }} />
      )}

      {s.screen === "vehicle" && fleet.fleet && (
        <VehiclePicker vehicles={fleet.fleet.vehicles}
                       selected={fleet.vehicleId ?? fleet.fleet.default}
                       onSelect={fleet.select}
                       onConfirm={() => setWantRoute((x) => x + 1)} />
      )}

      {s.screen === "compare" && compare && (
        <RouteCompare safe={compare.safe} fast={compare.fast}
                      selected={choice} onSelect={setChoice}
                      onChangeVehicle={fleet.fleet ? () => s.open("vehicle") : undefined}
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
                  voiceOn={v.available ? voice : null}
                  onToggleVoice={() => setVoice((x) => !x)}
                  onSwitchRoute={n.fastPlan ? () => {
                    n.choose("fast");   // plan ↔ fastPlan 을 맞바꾼다
                    setChoice((c) => (c === "safe" ? "fast" : "safe"));
                  } : undefined} />
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
      {s.screen === "vehicle" && n.noRoute && (
        <div style={toast}>{vehicleKind} · 요구 폭 {need.toFixed(1)}m 를 만족하는 경로가 없다 — 다른 접근 지점이 필요하다</div>
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

function routeOption(
  p: RoutePlan, need: number, other: RoutePlan | null, rec: boolean,
  access: { alt: boolean; walkM: number } | null,
  ctx: GeoJSON.FeatureCollection | null,
): RouteOption {
  const isUnc = (e: GraphEdge) => e.verdict === "needs_cv" || e.verdict === "unknown";
  const unc = p.edges.filter(isUnc);
  const w = p.edges.map((e) => e.width_min_m).filter((x): x is number => x != null);
  const sec = travelSeconds(p);
  const deltaSec = other ? sec - travelSeconds(other) : 0;
  const otherUnc = other ? other.edges.filter(isUnc).length : unc.length;
  // ★ 2026-09-22 (§214-2). 문구를 **실제 수로** 쓴다. 종전 「확인 필요 구간 11개를
  //   지납니다」 는 비교 상대를 안 말해서 추천 이유가 안 보였다.
  const slower = deltaSec > 1 ? `${fmtDur(deltaSec)} 느리지만 ` : "";
  const recNote = !unc.length ? `${slower}확인 필요 구간을 우회합니다.`
    : unc.length < otherUnc ? `${slower}확인 필요 구간이 ${otherUnc - unc.length}개 적습니다.`
    : `확인 필요 구간 ${unc.length}개를 지납니다 — 피할 수 있는 경로가 없습니다.`;
  const tail = access?.alt
    ? ` 차량은 사건 지점 약 ${Math.round(access.walkM)}m(직선) 앞 대체 접근 지점까지 갑니다.` : "";
  return {
    title: rec ? "폭 기준 추천" : "빠른 경로", recommended: rec, sec, lengthM: p.lengthM,
    uncertainCount: unc.length,
    uncertainM: unc.reduce((a, e) => a + (e.length_m ?? 0), 0),
    minWidthM: w.length ? Math.min(...w) : null,
    requiredM: need,
    deltaSec,
    note: (rec ? recNote : "도착은 빠르지만 폭 측정 신뢰도가 낮은 구간이 포함됩니다.") + tail,
    rules: ruleSummary(p.rules),
    around: hazardSummary(routeHazards(p, ctx)),
  };
}

function samePlan(a: RoutePlan, b: RoutePlan): boolean {
  return a.edges.length === b.edges.length && a.edges.every((e, i) => e.seg_uid === b.edges[i].seg_uid);
}

/** 비교 화면에서 선택 안 된 쪽 경로. `choose` 전이라 plan 이 안전 경로다 */
function otherPlan(n: { plan: RoutePlan | null; fastPlan: RoutePlan | null }, choice: "safe" | "fast") {
  return choice === "safe" ? n.fastPlan : n.plan;
}

/** `동부소방서_광주-지산-119 안전센터` → `지산119안전센터` */
function shortStation(raw: string): string {
  const m = raw.match(/광주-(.+)$/);
  return (m ? m[1] : raw).replace(/[-\s]/g, "");
}

function hhmm(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function hhmmss(d: Date): string {
  return `${hhmm(d)}:${String(d.getSeconds()).padStart(2, "0")}`;
}

/** 값이 바뀌면 보이고 `ms` 뒤 사라진다. 같은 값이 다시 와도 새로 보이지 않는다 */
function useFading(v: string | null, ms: number): string | null {
  const [shown, setShown] = useState<string | null>(null);
  useEffect(() => {
    setShown(v);
    if (!v) return;
    const t = setTimeout(() => setShown(null), ms);
    return () => clearTimeout(t);
  }, [v, ms]);
  return shown;
}

/** 초 단위 시계. 상단 「현재 시간」 이 이것을 읽는다 */
function useNow(): Date {
  const [t, setT] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setT(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return t;
}

/** 사건 지점 연기 — 와이어프레임 05 · 15 · 23. 순수 CSS 라 지도 위 DOM 마커에 붙는다 */
const SMOKE_CSS = `
.fl-smoke{position:absolute;left:50%;top:-6px;width:0;height:0;pointer-events:none}
.fl-smoke i{position:absolute;left:-14px;top:-10px;width:28px;height:28px;border-radius:50%;
  background:radial-gradient(circle,rgba(90,90,96,.55),rgba(120,120,128,0) 70%);
  animation:flsmoke 3.2s linear infinite}
.fl-smoke i:nth-child(2){animation-delay:1.05s}
.fl-smoke i:nth-child(3){animation-delay:2.1s}
@keyframes flsmoke{0%{transform:translate(0,0) scale(.5);opacity:0}
  15%{opacity:.9}100%{transform:translate(10px,-70px) scale(2.2);opacity:0}}`;

const EMPTY_SPEC: VehicleSpec = {
  width_m: 0, wheelbase_m: null, turn_radius_m: null, clearance_m: 0,
};

const shell: React.CSSProperties = {
  position: "fixed", inset: 0, background: "#e2e7ed", color: C.panelInk,
  fontFamily: F.family,
};
const toast: React.CSSProperties = {
  position: "absolute", zIndex: 8, bottom: 90, left: "50%",
  transform: "translateX(-50%)", maxWidth: "70vw",
  background: "rgba(9,12,18,.94)", color: C.darkInk,
  border: `1px solid ${C.warn}66`, borderRadius: 12,
  padding: "10px 16px", fontSize: F.base,
};
const vehChip: React.CSSProperties = {
  background: "#1f2937", color: "#fff", borderRadius: 8, padding: "6px 12px",
  fontSize: 14, fontWeight: 800,
};
function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ ...shell, display: "grid", placeItems: "center",
                       padding: 24, textAlign: "center" }}>{children}</div>;
}
