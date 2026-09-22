/**
 * ui/VehiclePicker.tsx — 출동 차량 선택.  (와이어프레임 01 · 2026-09-21)
 *
 * ★ **회전반경은 제원표에 그 차의 값이 있을 때만 숫자로 띄운다**(DECISIONS §212,
 *   2026-09-22). 숫자는 `fleet.json` 의 `turn_radius_ref_m` 에서만 온다 — 이 파일에
 *   숫자를 적지 않는다. null 이면 등급(여유 · 주의 · 미판정)을 낸다. 사다리차
 *   둘은 제원표 값이 있어도 그 차의 값이 아니라 null 이다(§84-3).
 *   숫자 옆에 「참고」 를 붙이고 하단 고지가 「판정에 반영하지 않는다」 를
 *   말한다 — 숫자만 두면 관제사가 시스템이 회전을 반영한다고 읽는다(§86-5).
 *
 * ★ 차종 목록은 와이어프레임의 일곱 종이 아니라 **`fleet.json` 의 실제 편성**
 *   이다(지산 · 대인 센터별). 없는 차를 고르게 하면 그 제원이 어디서 왔는지
 *   아무도 모른다.
 *
 * ★ 2026-09-22 (§214-2). 이름을 와이어프레임처럼 크기 먼저(「중형 펌프차」), 차종 옆모습
 *   그림을 단다(`VehicleArt` — 우리가 그린 단순 도형). 편성 정본의 이름은 안 고친다.
 *
 * ★ 하단 고지 — 「현재 경로 판정에는 전폭만 반영됩니다」 — 를 지우지 마라.
 */
import type { CSSProperties } from "react";
import { C, F } from "./tokens";
import { Cta, Sheet } from "./Sheet";
import { VehicleArt } from "./VehicleArt";
import { displayName, vehicleClass } from "../domain/fleetName";

// ★ 사본을 두지 않는다. 종전 로컬 사본은 `turn_radius_verified` 가 빠진 채 갈라져 있었다.
export type { FleetVehicle } from "../domain/types";
import type { FleetVehicle } from "../domain/types";

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
              <span style={truck}><VehicleArt kind={vehicleClass(v.label, v.id)} /></span>
              <span style={{ flex: 1, textAlign: "left" }}>
                <span style={{ fontSize: 16, fontWeight: 800 }}>{displayName(v.label)}</span>
                {v.station && (
                  <span style={{ display: "block", fontSize: 11, color: C.panelSub }}>
                    {v.station.replace(/^동부소방서_?/, "")}
                  </span>
                )}
              </span>
              <span style={{ fontSize: 11, color: C.panelSub, textAlign: "right", lineHeight: 1.5 }}>
                폭 {v.width_m.toFixed(1)}m · 요구 {v.required_width_m.toFixed(1)}m<br />
                {v.turn_radius_ref_m != null
                  ? <>회전 {v.turn_radius_ref_m.toFixed(1)}m <span style={ref}>{v.spec_complete ? "코너 점검" : "참고"}</span></>
                  : <>회전 {v.turn_grade ?? "미판정"}</>}
              </span>
            </button>
          );
        })}
      </div>

      <div style={note}>
        현재 경로 판정에는 전폭만 반영됩니다. 회전 반경은 제원표 참고값(미검증)으로
        판정에 반영하지 않으며, 제원표에 해당 차량 값이 없으면 등급으로 표시합니다.
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
  width: 88, height: 42, borderRadius: 8, background: "#f8fafc", display: "grid", placeItems: "center",
};
const ref: CSSProperties = {
  fontSize: 10, color: C.panelSub, border: `1px solid ${C.sheetLine}`, borderRadius: 4,
  padding: "0 3px", marginLeft: 2,
};
const note: CSSProperties = {
  marginTop: 14, background: "#f8fafc", borderRadius: 10, padding: "10px 12px",
  fontSize: 12, color: C.panelSub, lineHeight: 1.5,
};
