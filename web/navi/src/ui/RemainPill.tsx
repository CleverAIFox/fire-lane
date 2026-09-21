/**
 * ui/RemainPill.tsx — 하단 중앙 「N분 남음 | x.xkm」.  (와이어프레임 09-21)
 *
 * ★ 재탐색 · 서버 오류 · 경로 없음처럼 경로가 서지 않은 상태에서는 숫자를
 *   비운다(「— | —」). 옛 경로의 남은 시간을 띄우면 그것이 거짓 숫자다.
 */
import type { CSSProperties } from "react";
import { C } from "./tokens";

export function RemainPill({ sec, m, blank }: { sec: number; m: number; blank?: boolean }) {
  const min = Math.max(0, Math.round(sec / 60));
  return (
    <div style={pill}>
      <span style={{ fontSize: 26, fontWeight: 800, color: C.cta }}>
        {blank ? "—" : <>{min}<span style={unit}>분 남음</span></>}
      </span>
      <span style={{ width: 1, height: 30, background: C.sheetLine }} />
      <span style={{ fontSize: 26, fontWeight: 800, color: C.cta }}>
        {blank ? "—" : <>{(m / 1000).toFixed(1)}<span style={unit}>km</span></>}
      </span>
    </div>
  );
}

const pill: CSSProperties = {
  position: "absolute", zIndex: 5, bottom: 0, left: "50%", transform: "translateX(-50%)",
  background: "#fff", borderRadius: "18px 18px 0 0", padding: "12px 34px",
  display: "flex", alignItems: "center", gap: 28, minWidth: 260, justifyContent: "center",
  boxShadow: "0 -4px 16px rgba(0,0,0,.18)",
};
const unit: CSSProperties = { fontSize: 15, fontWeight: 700, marginLeft: 3, color: "#334155" };
