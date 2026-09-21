/**
 * ui/StatusCard.tsx — 우측 상태 카드.  (와이어프레임 06 「새 경로를 찾는 중」)
 *
 * ★ 상단바만으로는 「지금 무엇을 기다리나」 가 안 보인다. 재탐색처럼 시간이
 *   걸리는 상태만 이 카드를 띄운다 — 나머지 상태까지 띄우면 골목에서 지도를
 *   가린다(`useScreens` 머리말: 지도를 가리는 것이 이 앱에서 제일 나쁘다).
 */
import type { CSSProperties } from "react";
import { C, S } from "./tokens";

export function StatusCard({ chip, title, lines, foot }: {
  chip: string; title: string; lines: string[]; foot?: string;
}) {
  return (
    <div style={card}>
      <span style={chipS}>{chip}</span>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.panelInk, margin: "10px 0 6px" }}>{title}</div>
      {lines.map((l) => (
        <div key={l} style={{ fontSize: 14, color: C.panelSub, lineHeight: 1.5 }}>{l}</div>
      ))}
      <div style={spinWrap}><div style={spin} /></div>
      {foot && <div style={{ textAlign: "center", fontSize: 15, fontWeight: 800, color: C.cta }}>{foot}</div>}
    </div>
  );
}

const card: CSSProperties = {
  position: "absolute", zIndex: 5, right: 0, top: S.guideBarH, width: 300,
  background: "#fff", borderRadius: "0 0 0 14px", padding: "16px 18px 20px",
  boxShadow: "-4px 6px 18px rgba(0,0,0,.18)",
};
const chipS: CSSProperties = {
  display: "inline-block", background: C.cta, color: "#fff", borderRadius: 999,
  padding: "3px 10px", fontSize: 12, fontWeight: 800,
};
const spinWrap: CSSProperties = { display: "grid", placeItems: "center", margin: "18px 0 10px" };
const spin: CSSProperties = {
  width: 44, height: 44, borderRadius: 999, border: `4px dotted ${C.cta}`,
  animation: "flspin 1.6s linear infinite",
};
