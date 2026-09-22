/**
 * ui/Sheet.tsx — 출동 전 화면(00 · 01 · 02)의 틀.  (와이어프레임 09-21)
 *
 *   ┌ FireLane ───────── 화면 제목 ───────────── [오른쪽 칸] ┐
 *   │ 좌측 패널 │                지도                        │
 *   └───────────┴────────────────────────────────────────────┘
 *
 * ★ 주행 전 화면은 **어두운 머리띠 + 흰 좌측 패널**이고, 주행 화면은 파란
 *   상단바다. 와이어프레임이 두 틀을 가른 것은 「계획하는 중」 과 「가는 중」
 *   을 한눈에 가르려는 것이다 — 섞지 않는다.
 */
import type { CSSProperties, ReactNode } from "react";
import { C, F, S } from "./tokens";
import { Doc } from "./icons";

export const HEADER_H = 76;

export function PlanHeader({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <div style={header}>
      <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: -.3 }}>FireLane</div>
      <div style={{ position: "absolute", left: "50%", transform: "translateX(-50%)",
                    fontSize: 22, fontWeight: 800 }}>{title}</div>
      <div style={{ marginLeft: "auto" }}>{right}</div>
    </div>
  );
}

/** `wf` 는 와이어프레임 번호다 — `tests/test_navi_wireframe.py` 가 이것으로 화면을 센다 */
export function Sheet({ children, footer, wf }: { children: ReactNode; footer?: ReactNode; wf: string }) {
  return (
    <div style={sheet} data-wf={wf}>
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 18px 12px" }}>{children}</div>
      {footer && <div style={{ padding: "12px 18px 18px" }}>{footer}</div>}
    </div>
  );
}

export function Cta({ children, onClick, disabled }: {
  children: ReactNode; onClick: () => void; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
            style={{ ...cta, opacity: disabled ? .45 : 1, cursor: disabled ? "not-allowed" : "pointer" }}>
      {children} <span style={{ marginLeft: 10, fontSize: 22 }}>»</span>
    </button>
  );
}

export function Ghost({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button onClick={onClick} style={ghost}>{children}</button>;
}

export function SmallBtn({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button onClick={onClick} style={small}>{children}</button>;
}

export function TimeBox({ now, incident }: { now: string; incident: string | null }) {
  return (
    <div style={{ background: C.timeBox, border: "1px solid rgba(255,255,255,.14)",
                  borderRadius: 10, padding: "6px 16px", textAlign: "center" }}>
      <div style={{ color: C.timeGreen, fontSize: 18, fontWeight: 800 }}>현재 시간 : {now}</div>
      {incident && <div style={{ color: "#cfd8e6", fontSize: 12, marginTop: 2 }}><Doc /> 사건 접수 {incident}</div>}
    </div>
  );
}

const header: CSSProperties = {
  position: "absolute", top: 0, left: 0, right: 0, height: HEADER_H, zIndex: 6,
  background: "#0b1220", color: "#fff", display: "flex", alignItems: "center",
  padding: "0 22px", boxSizing: "border-box", fontFamily: F.family,
};
const sheet: CSSProperties = {
  position: "absolute", zIndex: 5, top: HEADER_H, left: 0, bottom: 0, width: S.sheetW,
  background: C.sheetBg, color: C.panelInk, display: "flex", flexDirection: "column",
  boxShadow: "6px 0 24px rgba(0,0,0,.18)", fontFamily: F.family,
};
const cta: CSSProperties = {
  width: "100%", border: "none", borderRadius: 12, padding: "16px 0",
  background: `linear-gradient(90deg, ${C.cta}, #3aa0ff)`, color: C.ctaInk,
  fontSize: 19, fontWeight: 800, fontFamily: F.family,
  boxShadow: "0 6px 16px rgba(30,124,242,.35)",
};
const ghost: CSSProperties = {
  border: `1.5px solid ${C.cta}`, background: "#fff", color: C.cta, borderRadius: 12,
  padding: "14px 18px", fontSize: 15, fontWeight: 800, cursor: "pointer", fontFamily: F.family,
};
const small: CSSProperties = {
  border: `1.5px solid ${C.cta}`, background: "#fff", color: C.cta, borderRadius: 8,
  padding: "6px 10px", fontSize: 12, fontWeight: 800, cursor: "pointer", fontFamily: F.family,
  whiteSpace: "nowrap",
};
