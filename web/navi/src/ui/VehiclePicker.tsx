/**
 * ui/VehiclePicker.tsx — 출동 차량 선택.  (와이어프레임 01 · 2026-09-21)
 *
 * ★ **회전반경 숫자를 띄우지 않는다.** 09-21 와이어프레임은 「회전 7.3m」 를
 *   띄우지만, `turn_radius_verified` 가 false 인 동안 등급(여유 · 주의 · 미판정)
 *   만 낸다. 숫자를 띄우면 관제사가 시스템이 회전을 반영한다고 읽는데 반영하지
 *   않는다(DECISIONS §86-5). 지혜님께 드릴 확인 사항이다.
 *
 * ★ 차종 목록은 와이어프레임의 일곱 종이 아니라 **`fleet.json` 의 실제 편성**
 *   이다(지산 · 대인 센터별). 없는 차를 고르게 하면 그 제원이 어디서 왔는지
 *   아무도 모른다.
 *
 * ★ 하단 고지 — 「현재 경로 판정에는 전폭만 반영됩니다」 — 를 지우지 마라.
 */
import type { CSSProperties } from "react";
import { C, F } from "./tokens";
import { Cta, Sheet } from "./Sheet";
import { Truck } from "./icons";

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
}

export function VehiclePicker(p: Props) {
  return (
    <Sheet wf="01" footer={<Cta onClick={p.onConfirm}>선택한 차량으로 경로 계산</Cta>}>
      <div style={{ fontSize: 14, color: "#334155", lineHeight: 1.6 }}>
        선택한 차량 제원으로 통행 가능한 경로를 계산합니다.<br />
        <span style={{ fontSize: 12, color: C.panelSub }}>
          차량 이름만 선택하면 판정 그룹은 자동 적용됩니다.
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 14 }}>
        {p.vehicles.map((v) => {
          const on = v.id === p.selected;
          return (
            <button key={v.id} onClick={() => p.onSelect(v.id)}
                    style={{ ...row, borderColor: on ? C.cta : C.sheetLine,
                             background: on ? C.softBlue : "#fff" }}>
              <span style={{ ...radio, borderColor: on ? C.cta : "#cbd5e1" }}>
                {on && <span style={radioDot} />}
              </span>
              <span style={truck}><Truck size={20} color="#dc2626" /></span>
              <span style={{ flex: 1, textAlign: "left" }}>
                <span style={{ fontSize: 15, fontWeight: 800 }}>{v.label}</span>
                {v.station && (
                  <span style={{ display: "block", fontSize: 11, color: C.panelSub }}>
                    {v.station.replace(/^동부소방서_?/, "")}
                  </span>
                )}
              </span>
              <span style={{ fontSize: 11, color: C.panelSub, textAlign: "right", lineHeight: 1.5 }}>
                폭 {v.width_m.toFixed(1)}m · 요구 {v.required_width_m.toFixed(1)}m<br />
                회전 {v.turn_grade ?? "미판정"}
              </span>
            </button>
          );
        })}
      </div>

      <div style={note}>
        현재 경로 판정에는 전폭만 반영됩니다. 회전 반경은 미검증이라 등급으로만
        표시합니다.
      </div>
    </Sheet>
  );
}

const row: CSSProperties = {
  display: "flex", alignItems: "center", gap: 12, border: "1.5px solid", borderRadius: 12,
  padding: "10px 12px", cursor: "pointer", fontFamily: F.family, color: C.panelInk,
};
const radio: CSSProperties = {
  width: 18, height: 18, borderRadius: 999, border: "2px solid", display: "grid",
  placeItems: "center", flex: "0 0 auto",
};
const radioDot: CSSProperties = { width: 8, height: 8, borderRadius: 999, background: C.cta };
const truck: CSSProperties = {
  width: 44, height: 30, borderRadius: 8, background: "#fef2f2", display: "grid", placeItems: "center",
};
const note: CSSProperties = {
  marginTop: 14, background: "#f8fafc", borderRadius: 10, padding: "10px 12px",
  fontSize: 12, color: C.panelSub, lineHeight: 1.5,
};
