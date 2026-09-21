/**
 * ui/DispatchPanel.tsx — 출동 정보 입력.  (와이어프레임 00)
 *
 * ★ 출발지는 **안전센터**다. 출동은 센터에서 나간다(`seg/params.py::STATIONS`).
 *   09-05 판은 출발지를 현위치(GPS)로 두었는데, 관제·출동 흐름에서 차량은
 *   센터 차고에 서 있다. 현위치는 주행 중 위치에 쓴다.
 *
 * ★ 사건 위치는 원래 **119 접수 시스템**이 넘긴다. 그 연동이 아직 없어서
 *   검색·지도 선택·URL(`?incident=경도,위도&label=…`)로 받는다. URL 은 접수
 *   시스템이 붙을 자리다.
 */
import type { CSSProperties } from "react";
import { C, F } from "./tokens";
import { Cta, Sheet, SmallBtn } from "./Sheet";
import { Flame } from "./icons";

export interface StationOpt { id: string; name: string; addr: string }

interface Props {
  station: StationOpt | null;
  stations: StationOpt[];
  onStation: (id: string) => void;
  incidentLabel: string | null;
  incidentSub: string | null;
  incidentAt: string | null;
  armed: "origin" | "dest" | null;
  onArm: (w: "origin" | "dest" | null) => void;
  onSearch: () => void;
  onSwap: () => void;
  onNext: () => void;
  canNext: boolean;
}

export function DispatchPanel(p: Props) {
  const nextStation = () => {
    if (!p.stations.length) return;
    const i = p.stations.findIndex((s) => s.id === p.station?.id);
    p.onStation(p.stations[(i + 1) % p.stations.length].id);
  };
  return (
    <Sheet wf="00" footer={<Cta onClick={p.onNext} disabled={!p.canNext}>출동 차량 선택</Cta>}>
      <div style={{ fontSize: 22, fontWeight: 800 }}>출발지와 도착지를 입력하세요</div>
      <div style={{ fontSize: 13, color: C.panelSub, marginTop: 4 }}>
        위치를 확인한 뒤 출동 차량을 선택합니다.
      </div>

      <div style={box}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <b style={{ fontSize: 14 }}>경로 지점</b>
          <SmallBtn onClick={p.onSwap}>⇅ 출발·도착 바꾸기</SmallBtn>
        </div>

        <Row kind="출발" color={C.station} title="출발지"
             name={p.station?.name ?? "안전센터를 고르세요"}
             sub={p.station?.addr ?? ""}
             onChange={nextStation} armed={p.armed === "origin"} />
        <Row kind="도착" color={C.station} title="도착지" outline
             name={p.incidentLabel ?? "사건 위치를 입력하세요"}
             sub={p.incidentLabel ? "사건 접수 위치" : "검색하거나 지도에서 고릅니다"}
             onChange={p.onSearch} armed={p.armed === "dest"} />

        <button onClick={() => p.onArm(p.armed === "dest" ? null : "dest")}
                style={{ ...mapPick, background: p.armed ? C.softBlue : "#fff" }}>
          ⌖ {p.armed ? "지도를 눌러 사건 위치를 찍으세요" : "지도에서 직접 선택"}
        </button>
      </div>

      {p.incidentLabel && (
        <div style={incident}>
          <div style={flame}><Flame size={22} /></div>
          <div>
            <div style={{ fontSize: 12, color: C.danger, fontWeight: 800 }}>사건 접수 위치</div>
            <div style={{ fontSize: 17, fontWeight: 800, marginTop: 2 }}>{p.incidentLabel}</div>
            <div style={{ fontSize: 12, color: C.panelSub, marginTop: 2 }}>
              화재 출동{p.incidentAt ? ` · 사건 입력 ${p.incidentAt}` : ""}
              {p.incidentSub ? ` · ${p.incidentSub}` : ""}
            </div>
          </div>
        </div>
      )}

      <div style={note}>
        출발지와 도착지를 확인하면 다음 단계에서 차량별 통행 가능 경로를 계산합니다.
      </div>
    </Sheet>
  );
}

function Row({ kind, color, title, name, sub, onChange, outline, armed }: {
  kind: string; color: string; title: string; name: string; sub: string;
  onChange: () => void; outline?: boolean; armed?: boolean;
}) {
  return (
    <div style={{ ...row, borderColor: armed ? C.cta : C.sheetLine }}>
      <div style={{ ...dot, background: outline ? "#fff" : color, color: outline ? color : "#fff",
                    border: `2px solid ${color}` }}>{kind}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: C.panelSub }}>{title}</div>
        <div style={{ fontSize: 16, fontWeight: 800, whiteSpace: "nowrap", overflow: "hidden",
                      textOverflow: "ellipsis" }}>{name}</div>
        {sub && <div style={{ fontSize: 11, color: C.panelSub }}>{sub}</div>}
      </div>
      <SmallBtn onClick={onChange}>위치 변경</SmallBtn>
    </div>
  );
}

const box: CSSProperties = {
  marginTop: 18, border: `1px solid ${C.sheetLine}`, borderRadius: 14, padding: 14,
  display: "flex", flexDirection: "column", gap: 10,
};
const row: CSSProperties = {
  display: "flex", alignItems: "center", gap: 12, border: "1.5px solid",
  borderRadius: 12, padding: "10px 12px",
};
const dot: CSSProperties = {
  width: 40, height: 40, borderRadius: 999, display: "grid", placeItems: "center",
  fontSize: 11, fontWeight: 800, flex: "0 0 auto",
};
const mapPick: CSSProperties = {
  border: `1.5px solid ${C.cta}`, borderRadius: 10, padding: "10px 0", color: C.cta,
  fontWeight: 800, fontSize: 14, cursor: "pointer", fontFamily: F.family,
};
const incident: CSSProperties = {
  marginTop: 14, border: `1px solid ${C.sheetLine}`, borderRadius: 14, padding: 14,
  display: "flex", gap: 12, alignItems: "center",
};
const flame: CSSProperties = {
  width: 40, height: 40, borderRadius: 999, background: "#fdecec", display: "grid",
  placeItems: "center", fontSize: 20,
};
const note: CSSProperties = {
  marginTop: 14, background: C.softBlue, borderRadius: 10, padding: "10px 12px",
  fontSize: 12, color: "#334155", lineHeight: 1.5,
};
