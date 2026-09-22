/**
 * ui/VehicleArt.tsx — 차종 옆모습 그림.  (와이어프레임 01 · DECISIONS §214-2)
 *
 * 와이어프레임 01 은 차종마다 옆모습 그림을 단다. 여기 것은 **우리가 그린 단순 도형**
 * 이다 — 실제 차량 · 제조사 · 도색을 본뜨지 않았다. 차종을 눈으로 가르는 데만 쓴다.
 *
 * ★ 크기 비례는 **대략**이다(전장 5~13m 를 한 칸에 넣는다). 치수를 그림에서 읽지 않는다 —
 *   숫자는 옆 칸의 제원이 말한다.
 */
import type { ReactElement } from "react";
import type { VehicleClass } from "../domain/fleetName";

const RED = "#dc2626", DARK = "#1f2937", WIN = "#bfdbfe", GRAY = "#cbd5e1";

export function VehicleArt({ kind, w = 76 }: { kind: VehicleClass; w?: number }) {
  const h = Math.round(w * 0.42);
  return (
    <svg width={w} height={h} viewBox="0 0 100 42" aria-hidden>
      {BODY[kind]}
      <circle cx="22" cy="34" r="6" fill={DARK} /><circle cx="22" cy="34" r="2.4" fill={GRAY} />
      <circle cx="78" cy="34" r="6" fill={DARK} /><circle cx="78" cy="34" r="2.4" fill={GRAY} />
    </svg>
  );
}

const cab = (x = 70, color = RED) => (
  <>
    <path d={`M${x} 12 H${x + 18} L${x + 26} 22 V32 H${x} Z`} fill={color} />
    <path d={`M${x + 4} 14 H${x + 17} L${x + 22} 21 H${x + 4} Z`} fill={WIN} />
  </>
);

const BODY: Record<VehicleClass, ReactElement> = {
  pump: (<>{cab()}<rect x="8" y="10" width="62" height="22" rx="2" fill={RED} />
    <rect x="12" y="14" width="16" height="12" rx="1.5" fill="#b91c1c" /><rect x="32" y="14" width="16" height="12" rx="1.5" fill="#b91c1c" />
    <rect x="52" y="14" width="14" height="12" rx="1.5" fill="#b91c1c" /><rect x="10" y="7" width="56" height="3" rx="1.5" fill={GRAY} /></>),
  tanker: (<>{cab()}<rect x="6" y="11" width="64" height="21" rx="10" fill={RED} />
    <rect x="10" y="19" width="56" height="3" fill="#fca5a5" /></>),
  chem: (<>{cab()}<rect x="6" y="10" width="64" height="22" rx="3" fill={RED} />
    <rect x="10" y="14" width="56" height="7" rx="3.5" fill="#fde68a" /><rect x="40" y="5" width="12" height="5" rx="1" fill={DARK} /></>),
  ladder: (<>{cab()}<rect x="6" y="18" width="64" height="14" rx="2" fill={RED} />
    <path d="M2 14 L74 8" stroke={GRAY} strokeWidth="4" /><path d="M2 14 L74 8" stroke={DARK} strokeWidth="1" strokeDasharray="3 3" /></>),
  articulated: (<>{cab()}<rect x="6" y="18" width="64" height="14" rx="2" fill={RED} />
    <path d="M14 16 L40 4 L66 12" stroke={GRAY} strokeWidth="4" fill="none" strokeLinejoin="round" /><circle cx="40" cy="4" r="3" fill={DARK} /></>),
  rescue: (<>{cab()}<rect x="8" y="9" width="62" height="23" rx="3" fill={RED} />
    <rect x="12" y="13" width="54" height="4" fill="#fde68a" /><rect x="12" y="20" width="24" height="9" rx="1.5" fill="#b91c1c" /></>),
  ambulance: (<>{cab(66, "#f8fafc")}<rect x="12" y="8" width="56" height="24" rx="4" fill="#f8fafc" stroke={GRAY} />
    <rect x="12" y="20" width="56" height="3" fill={RED} /><path d="M36 12 h6 v4 h4 v6 h-4 v4 h-6 v-4 h-4 v-6 h4 Z" fill={RED} /></>),
  light: (<>{cab(62)}<rect x="18" y="14" width="46" height="18" rx="3" fill={RED} />
    <rect x="22" y="18" width="18" height="10" rx="1.5" fill="#b91c1c" /></>),
};
