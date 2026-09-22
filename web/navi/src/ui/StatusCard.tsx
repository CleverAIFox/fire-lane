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
      <div style={spinWrap}>
        <div style={spin} />
        {/* 와이어프레임 06 — 도는 고리 안에 내비 화살표 */}
        <svg width="30" height="30" viewBox="0 0 24 24" style={{ position: "absolute" }} aria-hidden>
          <path d="M12 3 L19 20 L12 16 L5 20 Z" fill={C.cta} />
        </svg>
      </div>
      {foot && foot.split(" 잠시만").map((t, i) => (
        <div key={t} style={{ textAlign: "center", fontSize: i ? 13 : 16, fontWeight: i ? 600 : 800,
                              color: i ? C.panelSub : C.cta, marginTop: i ? 4 : 0 }}>
          {i ? `잠시만${t}` : t}
        </div>
      ))}
    </div>
  );
}

// ★ 2026-09-22 (§214-2) 와이어프레임 06 모양 — 떠 있는 카드 · 파란 테두리 · 큰 고리.
const card: CSSProperties = {
  position: "absolute", zIndex: 5, right: 14, top: S.guideBarH + 14, width: 340,
  background: "#fff", borderRadius: 20, padding: "20px 22px 24px", border: `3px solid ${C.cta}`,
  boxShadow: "0 10px 28px rgba(0,0,0,.22)", boxSizing: "border-box",
};
const chipS: CSSProperties = {
  display: "inline-block", background: C.cta, color: "#fff", borderRadius: 999,
  padding: "3px 10px", fontSize: 12, fontWeight: 800,
};
const spinWrap: CSSProperties = {
  display: "grid", placeItems: "center", margin: "22px 0 14px", position: "relative",
};
const spin: CSSProperties = {
  width: 76, height: 76, borderRadius: 999, border: `6px solid ${C.softBlue}`,
  borderTopColor: C.cta, borderRightColor: C.cta, animation: "flspin 1.2s linear infinite",
};
