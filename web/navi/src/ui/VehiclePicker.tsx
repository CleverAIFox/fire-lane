/**
 * ui/VehiclePicker.tsx — 출동 차량 선택. (와이어프레임 7)
 *
 * ★ **회전반경 숫자를 띄우지 않는다.** `turn_radius_verified` 가 false 인
 *   동안 등급("여유 · 주의 · 미판정")만 낸다. 숫자를 띄우면 관제사가
 *   시스템이 회전을 반영한다고 읽는데 반영하지 않는다(DECISIONS §86-5).
 *
 * ★ 하단 고지도 같은 이유다 — "현재 경로 판정에는 전폭만 반영됩니다."
 *
 * ★ 선두차 논리. 출동은 편성으로 나가고 선두가 가장 큰 차다. 가장 큰
 *   차가 지나가면 나머지는 전부 지나간다 — 도로폭을 구간 **최소**로
 *   판정하는 것의 뒤집음이다.
 */
import type { CSSProperties } from "react";
import { C, F, S } from "./tokens";

export interface FleetVehicle {
  id: string;
  label: string;
  station?: string | null;
  count: number;
  width_m: number;
  required_width_m: number;
  turn_grade?: string | null;
  turn_unknown: boolean;
  length_m?: number | null;
  match?: string | null;
  note?: string | null;
}

interface Props {
  vehicles: FleetVehicle[];
  selected: string;
  onSelect: (id: string) => void;
  onConfirm: () => void;
  onClose: () => void;
}

export function VehiclePicker(p: Props) {
  // 안전센터별로 묶는다. 출동은 센터 단위다.
  const groups = new Map<string, FleetVehicle[]>();
  for (const v of p.vehicles) {
    const g = v.station ?? "기타";
    let l = groups.get(g);
    if (!l) groups.set(g, (l = []));
    l.push(v);
  }

  return (
    <div style={sheet}>
      <div style={bar}>
        <span style={{ fontWeight: 800, fontSize: F.mid }}>출동 차량 선택</span>
        <span style={{ flex: 1 }} />
        <button onClick={p.onClose} style={x} aria-label="닫기">✕</button>
      </div>

      <div style={{ padding: S.pad }}>
        <div style={{ fontSize: F.base, lineHeight: 1.6 }}>
          선택한 차량 제원으로 통행 가능 경로를 계산합니다.
        </div>

        {[...groups].map(([station, list]) => (
          <div key={station} style={{ marginTop: 16 }}>
            <div style={groupHead}>{station}</div>
            {list.map((v) => (
              <Item key={v.id} v={v} on={p.selected === v.id}
                    onClick={() => p.onSelect(v.id)} />
            ))}
          </div>
        ))}

        {/* ★ 이 두 줄을 지우지 마라. 판정의 경계다. */}
        <div style={note}>
          현재 경로 판정에는 <b>전폭만</b> 반영됩니다.<br />
          회전반경과 전장은 참고 정보이며 판정하지 않습니다.
        </div>

        <button onClick={p.onConfirm} style={primary}>
          이 차량으로 경로 계산 →
        </button>
      </div>
    </div>
  );
}

function Item({ v, on, onClick }: {
  v: FleetVehicle; on: boolean; onClick: () => void;
}) {
  return (
    <div onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 12, cursor: "pointer",
      padding: "12px 14px", marginTop: 6,
      border: `2px solid ${on ? C.link : C.panelLine}`,
      borderRadius: S.radiusSm,
      background: on ? "rgba(37,99,235,.07)" : "transparent",
    }}>
      <i style={{
        width: 16, height: 16, borderRadius: 8, flexShrink: 0,
        border: `2px solid ${on ? C.link : C.panelLine}`,
        boxShadow: on ? `inset 0 0 0 3px ${C.link}` : "none",
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: F.base, fontWeight: 700 }}>
          {v.label}
          {v.count > 1 && (
            <span style={{ color: C.panelSub, fontWeight: 600 }}> ×{v.count}</span>
          )}
          {v.match === "추정" && (
            <span style={tag}>추정</span>
          )}
        </div>
        {v.note && (
          <div style={{ fontSize: F.tiny, color: C.panelSub, marginTop: 2 }}>
            {v.note}
          </div>
        )}
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontSize: F.small, fontWeight: 700 }}>
          폭 {v.width_m.toFixed(v.width_m % 1 ? 3 : 1)}m
        </div>
        {/* ★ 숫자가 아니라 등급이다. 미검증 값을 확정처럼 띄우지 않는다. */}
        <div style={{ fontSize: F.tiny,
                      color: v.turn_grade === "여유" ? C.safeInk
                           : v.turn_grade === "주의" ? C.warnInk : C.panelSub }}>
          회전 {v.turn_grade ?? "미판정"}
        </div>
      </div>
    </div>
  );
}

const sheet: CSSProperties = {
  position: "absolute", zIndex: 7, top: 0, left: 0, bottom: 0, width: 400,
  background: C.panel, color: C.panelInk, overflowY: "auto",
  boxShadow: "8px 0 34px rgba(0,0,0,.45)",
};
const bar: CSSProperties = {
  display: "flex", alignItems: "center", gap: 10,
  background: C.panelInk, color: "#fff", padding: "14px 16px",
};
const groupHead: CSSProperties = {
  fontSize: F.small, fontWeight: 700, color: C.panelSub,
  borderBottom: `1px solid ${C.panelLine}`, paddingBottom: 5,
};
const tag: CSSProperties = {
  marginLeft: 6, fontSize: F.tiny, fontWeight: 700, color: C.warnInk,
  background: "rgba(245,158,11,.16)", borderRadius: 999, padding: "2px 8px",
};
const note: CSSProperties = {
  marginTop: 16, padding: "10px 12px", borderRadius: S.radiusSm,
  background: "rgba(15,23,42,.05)",
  fontSize: F.small, color: C.panelSub, lineHeight: 1.6,
};
const primary: CSSProperties = {
  marginTop: 12, width: "100%", background: C.link, color: "#fff",
  border: "none", borderRadius: S.radiusSm, padding: "14px 0",
  fontSize: F.base, fontWeight: 800, cursor: "pointer", fontFamily: F.family,
};
const x: CSSProperties = {
  background: "none", border: "none", color: "#fff",
  fontSize: 18, cursor: "pointer", padding: 0, lineHeight: 1,
};
