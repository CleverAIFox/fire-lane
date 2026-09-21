/**
 * ui/MapControls.tsx — 좌측 세로 지도 조작.  (와이어프레임 09-21 전 화면)
 *
 *   나침반 · 현위치 · 확대 · 축소 · 레이어
 *
 * ★ 지도 인스턴스를 모른다. 누르면 콜백만 부른다 — 1인칭 카메라가
 *   매 프레임 줌을 덮어쓰므로, 확대·축소는 지도에 직접 걸지 않고
 *   `NaviMap` 의 줌 오프셋을 바꾸는 쪽으로 간다.
 */
import type { CSSProperties, ReactNode } from "react";
import { C, S } from "./tokens";

interface Props {
  top?: number;
  onCompass: () => void;
  onLocate: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onLayers: () => void;
  layersOn: boolean;
}

export function MapControls(p: Props) {
  return (
    <div style={{ ...col, top: p.top ?? S.guideBarH + 90 }}>
      <Btn onClick={p.onCompass} label="나침반">
        <svg width="22" height="22" viewBox="0 0 24 24"><path d="M12 2 L16 12 L12 10 L8 12 Z" fill={C.danger} /><path d="M12 22 L8 12 L12 14 L16 12 Z" fill="#94a3b8" /></svg>
      </Btn>
      <Btn onClick={p.onLocate} label="현위치">
        <svg width="22" height="22" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" fill="none" stroke="#111827" strokeWidth="2" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" stroke="#111827" strokeWidth="2" strokeLinecap="round" /></svg>
      </Btn>
      <Btn onClick={p.onZoomIn} label="확대"><b style={{ fontSize: 24, lineHeight: 1 }}>+</b></Btn>
      <Btn onClick={p.onZoomOut} label="축소"><b style={{ fontSize: 26, lineHeight: 1 }}>−</b></Btn>
      <Btn onClick={p.onLayers} label="레이어 · 판정색" on={p.layersOn}>
        <svg width="22" height="22" viewBox="0 0 24 24"><path d="M12 3 L21 8 L12 13 L3 8 Z" fill="none" stroke="#111827" strokeWidth="2" strokeLinejoin="round" /><path d="M3 12 L12 17 L21 12M3 16 L12 21 L21 16" fill="none" stroke="#111827" strokeWidth="2" strokeLinejoin="round" /></svg>
      </Btn>
    </div>
  );
}

function Btn({ onClick, label, on, children }: {
  onClick: () => void; label: string; on?: boolean; children: ReactNode;
}) {
  return (
    <button onClick={onClick} aria-label={label} title={label}
            style={{ ...btn, outline: on ? `3px solid ${C.cta}` : "none" }}>
      {children}
    </button>
  );
}

const col: CSSProperties = {
  position: "absolute", left: 18, zIndex: 5,
  display: "flex", flexDirection: "column", gap: 14,
};
const btn: CSSProperties = {
  width: 52, height: 52, borderRadius: 999, border: "none", background: "#fff",
  display: "grid", placeItems: "center", cursor: "pointer", color: "#111827",
  boxShadow: "0 3px 10px rgba(0,0,0,.22)",
};
