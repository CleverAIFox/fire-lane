/**
 * App.tsx — 훅을 잇는다. **계산도 그림도 여기서 하지 않는다.**
 *
 *   domain/     계산 (순수)    좌표·제원·비용·A*·스냅·회전·속도·검색
 *   infra/      바깥 세계      fetch · geolocation · 음성 · Mapbox
 *   app/        배선           useNavigation · useVoice · useHudData
 *                              useScreens · useFleet
 *   components/ 지도           NaviMap · layers
 *   ui/         화면           Hud · RoutePreview · Legend · DevBar · 화면 넷
 *
 * ── 흐름 ────────────────────────────────────────────────────────
 *   현위치(GPS) ──검색/클릭──▶ 경로 확인 ──안내 시작──▶ 주행
 *                                 ├ 경로 비교
 *                                 └ 차량 변경
 *
 * ★ 목적지를 고르면 **바로 안내를 시작하지 않는다.** 경로와 예상 시간을
 *   보여주고 사용자가 시작을 누른다(2026-09-06 · 와이어프레임).
 *
 * ★ 출발지는 현위치다. 사용자가 고르지 않는다. GPS 가 없을 때만 지도
 *   클릭으로 대체하며, 그것은 개발·시연용이다.
 */
import { useCallback, useMemo, useState } from "react";
import { NaviMap, type Pin } from "./components/NaviMap";
import { useNavigation } from "./app/useNavigation";
import { useVoice } from "./app/useVoice";
import { useHudData } from "./app/useHudData";
import { useScreens } from "./app/useScreens";
import { useFleet } from "./app/useFleet";
import { preparePois, searchPois, type PoiHit } from "./domain/search";
import { requiredWidth } from "./domain/vehicle";
import { progressAlongRoute } from "./domain/graph";
import { travelSeconds } from "./domain/speed";
import { Hud } from "./ui/Hud";
import { Legend } from "./ui/Legend";
import { DevBar } from "./ui/DevBar";
import { SearchPanel } from "./ui/SearchPanel";
import { VehiclePicker } from "./ui/VehiclePicker";
import { RouteCompare, type RouteOption } from "./ui/RouteCompare";
import { RoutePreview } from "./ui/RoutePreview";
import { BottleneckPanel } from "./ui/BottleneckPanel";
import { C, F } from "./ui/tokens";
import type { VehicleSpec } from "./domain/types";

export default function App() {
  const s = useScreens();
  const [firstPerson, setFirstPerson] = useState(true);
  const [legend, setLegend] = useState(false);
  const [voice, setVoice] = useState(true);
  const [choice, setChoice] = useState<"safe" | "fast">("safe");
  const [destName, setDestName] = useState<string | null>(null);

  // ★ 순서가 곧 의존 방향이다. 차종이 먼저, 그 제원으로 경로가 난다.
  const fleet = useFleet();
  const n = useNavigation(fleet.spec);
  const spec = fleet.spec ?? n.data?.spec ?? EMPTY_SPEC;
  const style = n.data?.graph.style ?? {};

  const v = useVoice({
    graph: n.data?.graph ?? null, spec,
    plan: n.phase === "guiding" ? n.plan : null,
    current: n.current, offRoute: n.offRoute,
    style, enabled: voice,
  });

  const hud = useHudData({
    spec, style, plan: n.plan, fastPlan: n.fastPlan,
    current: n.current, lenient: n.lenient, offRoute: n.offRoute,
    maneuver: v.maneuver, maneuverDistM: v.distM, maneuverText: v.banner,
  });

  // ── 목적지 검색 ───────────────────────────────────────────────
  const pois = useMemo(() => (n.data ? preparePois(n.data.poi) : []), [n.data]);
  const query = useCallback((q: string) => searchPois(pois, q), [pois]);

  // ★ POI 좌표를 그대로 목적지로 쓰지 않는다. 상가→도로 거리가 p90
  //   70.9m 라 엉뚱한 골목에 붙는다. 반드시 도로에 스냅한다.
  //   목적지의 49% 가 회색 구간에 접하므로 **고르기 전에** 보여준다.
  const verdictOf = useCallback((h: PoiHit) => {
    const r = n.snapAt(h.point[0], h.point[1]);
    if (!r) return null;
    const st = style[r.verdict];
    return st ? { color: st.color, label: st.label } : null;
  }, [n, style]);

  // ── 경로 확인 ─────────────────────────────────────────────────
  const preview = useMemo(() => {
    if (!n.plan || !n.dest) return null;
    const unc = n.plan.edges.filter(
      (e) => e.verdict === "needs_cv" || e.verdict === "unknown");
    const w = n.plan.edges.map((e) => e.width_min_m)
      .filter((x): x is number => x != null);
    const sec = travelSeconds(n.plan);
    const eta = new Date(Date.now() + sec * 1000);
    const st = style[n.dest.verdict];
    return {
      destLabel: destName ?? n.dest.seg_label ?? "지정한 지점",
      destVerdictLabel: st?.label,
      destVerdictColor: st?.color,
      vehicleKind: fleet.current?.label ?? spec.kind ?? "소방차",
      lengthM: n.plan.lengthM, sec,
      etaText: `${String(eta.getHours()).padStart(2, "0")}:`
        + `${String(eta.getMinutes()).padStart(2, "0")}`,
      uncertainCount: unc.length,
      uncertainM: unc.reduce((a, e) => a + (e.length_m ?? 0), 0),
      minWidthM: w.length ? Math.min(...w) : null,
      requiredM: requiredWidth(spec),
    };
  }, [n.plan, n.dest, destName, style, spec, fleet.current]);

  // ── 병목 상세 ─────────────────────────────────────────────────
  const bottleneck = useMemo(() => {
    if (!s.bottleneckUid || !n.plan) return null;
    const e = n.plan.edges.find((x) => x.seg_uid === s.bottleneckUid);
    if (!e) return null;
    const driven = progressAlongRoute(n.plan, n.current) ?? 0;
    let acc = 0;
    for (const x of n.plan.edges) {
      if (x.seg_uid === e.seg_uid) break;
      acc += x.length_m ?? 0;
    }
    return {
      segLabel: e.seg_label ?? e.seg_uid,
      aheadM: Math.max(0, acc - driven),
      widthM: e.width_min_m, requiredM: requiredWidth(spec),
      lengthM: e.length_m,
      coverage: e.width_cov ?? null, samples: e.n_sample ?? null,
      cctvDistM: e.cctv_dist_m ?? null,
      verdictLabel: style[e.verdict]?.label ?? e.verdict,
      verdictColor: style[e.verdict]?.color ?? C.panelInk,
    };
  }, [s.bottleneckUid, n.plan, n.current, spec, style]);

  // ── 경로 비교 ─────────────────────────────────────────────────
  const compare = useMemo(() => {
    const a = n.plan;
    const b = n.fastPlan;
    if (!a || !b) return null;
    const need = requiredWidth(spec);
    const mk = (
      p: typeof a, title: string, rec: boolean, other: typeof a,
    ): RouteOption => {
      const unc = p.edges.filter(
        (e) => e.verdict === "needs_cv" || e.verdict === "unknown");
      const w = p.edges.map((e) => e.width_min_m)
        .filter((x): x is number => x != null);
      const sec = travelSeconds(p);
      return {
        title, recommended: rec, sec, lengthM: p.lengthM,
        uncertainCount: unc.length,
        uncertainM: unc.reduce((acc, e) => acc + (e.length_m ?? 0), 0),
        minWidthM: w.length ? Math.min(...w) : null,
        requiredM: need,
        deltaSec: sec - travelSeconds(other),
        note: rec
          ? (unc.length
            ? `확인 필요 구간 ${unc.length}개를 지납니다.`
            : "확인 필요 구간을 우회합니다.")
          : "도착은 빠르지만 폭 측정 신뢰도가 낮은 구간이 포함됩니다.",
      };
    };
    return { safe: mk(a, "안전 경로", true, b), fast: mk(b, "빠른 경로", false, a) };
  }, [n.plan, n.fastPlan, spec]);

  const pins: Pin[] = useMemo(() => {
    const out: Pin[] = [];
    if (n.origin) out.push({ point: n.origin.point, label: "출발", color: "#4ad1ff" });
    if (n.dest) out.push({ point: n.dest.point, label: "목적지", color: "#ff4d3d" });
    return out;
  }, [n.origin, n.dest]);

  if (n.fatal) return <Center>★ {n.fatal}</Center>;
  if (n.phase === "loading" || !n.data) return <Center>불러오는 중…</Center>;

  const colors = Object.fromEntries(
    Object.entries(style).map(([k, x]) => [k, x.color]));
  const guiding = n.phase === "guiding";

  return (
    <div style={shell}>
      <NaviMap view={n.data.view} live={n.live} plan={n.plan} colors={colors}
               style={style}
               pins={pins} firstPerson={firstPerson && guiding}
               onMapClick={(lon, lat) => { setDestName(null); n.pick(lon, lat); }}
               onUserPan={() => setFirstPerson(false)} />

      {/* 주행 중에만 HUD */}
      {s.isMap && guiding && hud && (
        <Hud {...hud}
             voiceOn={v.available ? voice : null}
             onToggleVoice={() => setVoice((x) => !x)}
             onCompare={() => { setChoice("safe"); s.open("compare"); }} />
      )}

      {s.isMap && guiding && bottleneck && (
        <BottleneckPanel {...bottleneck}
                         onClose={() => s.setBottleneckUid(null)}
                         onReroute={() => s.open("compare")} />
      )}

      {s.isMap && n.notice && <div style={toast}>{n.notice}</div>}

      {/* 대기 상태에서만 검색 버튼 */}
      {s.isMap && !guiding && (
        <button onClick={() => s.open("search")} style={searchFab}>
          목적지 검색
        </button>
      )}

      {/* 목적지를 고르면 확인 화면이 뜬다 */}
      {n.phase === "preview" && s.isMap && preview && (
        <RoutePreview {...preview}
          onStart={() => { n.start(); setFirstPerson(true); }}
          onCompare={n.fastPlan ? () => { setChoice("safe"); s.open("compare"); } : undefined}
          onChangeVehicle={fleet.fleet ? () => s.open("vehicle") : undefined}
          onCancel={() => { setDestName(null); n.reset(); }} />
      )}

      {s.screen === "search" && (
        <SearchPanel open onOpen={() => {}} onClose={s.close}
                     onQuery={query} verdictOf={verdictOf}
                     onPick={(h) => {
                       setDestName(h.name);
                       n.pick(h.point[0], h.point[1]);
                       s.close();
                     }} />
      )}

      {s.screen === "vehicle" && fleet.fleet && (
        <VehiclePicker vehicles={fleet.fleet.vehicles}
                       selected={fleet.vehicleId ?? fleet.fleet.default}
                       onSelect={fleet.select}
                       onConfirm={() => { n.recompute(); s.close(); }}
                       onClose={s.close} />
      )}

      {s.screen === "compare" && compare && (
        <RouteCompare safe={compare.safe} fast={compare.fast}
                      selected={choice} onSelect={setChoice}
                      vehicleKind={fleet.current?.label ?? spec.kind ?? "소방차"}
                      onChangeVehicle={fleet.fleet
                        ? () => s.open("vehicle") : undefined}
                      onConfirm={() => { n.choose(choice); s.close(); }}
                      onClose={s.close} />
      )}

      {s.isMap && (
        <>
          <Legend style={style} open={legend} onToggle={() => setLegend(!legend)} />
          <DevBar
            hint={!n.origin ? "현위치 대기 · 지도를 눌러 대체"
                  : n.phase === "preview" ? "경로 확인"
                  : n.phase === "arrived" ? "도착"
                  : guiding ? "주행" : "목적지를 골라라"}
            guiding={guiding}
            simSpeed={n.simSpeed} setSimSpeed={n.setSimSpeed}
            lenient={n.lenient} setLenient={n.setLenient}
            firstPerson={firstPerson} setFirstPerson={setFirstPerson}
            onVehicle={fleet.fleet ? () => s.open("vehicle") : undefined}
            onBottleneck={guiding && n.plan ? () => {
              // 경로에서 제일 좁은 구간을 연다. 그것이 곧 병목이다.
              const worst = n.plan!.edges.reduce((a, b) =>
                (b.width_min_m ?? 99) < (a.width_min_m ?? 99) ? b : a);
              s.setBottleneckUid(worst.seg_uid);
            } : undefined}
            onReset={() => { s.close(); setDestName(null); n.reset(); }}
          />
        </>
      )}
    </div>
  );
}

const EMPTY_SPEC: VehicleSpec = {
  width_m: 0, wheelbase_m: null, turn_radius_m: null, clearance_m: 0,
};

const shell: React.CSSProperties = {
  position: "fixed", inset: 0, background: C.mapBg, color: C.darkInk,
  fontFamily: F.family,
};
const toast: React.CSSProperties = {
  position: "absolute", zIndex: 6, top: 118, left: "50%",
  transform: "translateX(-50%)", maxWidth: "70vw",
  background: "rgba(9,12,18,.94)", color: C.darkInk,
  border: `1px solid ${C.warn}66`, borderRadius: 12,
  padding: "10px 16px", fontSize: F.base,
};
const searchFab: React.CSSProperties = {
  position: "absolute", zIndex: 5, top: 20, left: 14,
  background: C.panel, color: C.panelInk,
  border: `1px solid ${C.panelLine}`, borderRadius: 999,
  padding: "12px 20px", fontSize: F.mid, fontWeight: 700,
  cursor: "pointer", fontFamily: F.family,
  boxShadow: "0 6px 20px rgba(0,0,0,.3)",
};
function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ ...shell, display: "grid", placeItems: "center",
                       padding: 24, textAlign: "center" }}>{children}</div>;
}
