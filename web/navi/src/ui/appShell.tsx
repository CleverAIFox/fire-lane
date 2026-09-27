/**
 * ui/appShell.tsx — 내비 화면의 바탕 · 알림 토스트 · 사건 지점 연기.
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `App.tsx` 가 640줄로 상한(600)을 넘었고 그 끝 예순 줄이 **모양**이었다.
 *   훅을 잇는 파일에 색과 keyframes 가 섞여 있으면, 배선을 고치러 온 사람이 그것을
 *   넘겨 읽어야 한다. `App.tsx` 머리말이 「계산도 그림도 여기서 하지 않는다」 고 적어
 *   놓고 그림을 들고 있었다.
 *
 * ★ 연기는 **순수 CSS** 다. 지도 위 DOM 마커에 붙으므로 MapLibre 레이어가 아니고,
 *   그래서 `components/layers.ts` 가 아니라 여기 산다(와이어프레임 05 · 15 · 23).
 *
 * IN    (없음 — 상수와 조각 하나)
 * OUT   shell · toast · vehChip · Center · SMOKE_CSS
 * 밖    무엇을 알릴지, 언제 연기를 띄울지 안 고른다. 고르는 것은 `App.tsx` 다.
 */
import { C, F } from "./tokens";

export const shell: React.CSSProperties = {
  position: "fixed", inset: 0, background: "#e2e7ed", color: C.panelInk,
  fontFamily: F.family,
};
export const toast: React.CSSProperties = {
  position: "absolute", zIndex: 8, bottom: 90, left: "50%",
  transform: "translateX(-50%)", maxWidth: "70vw",
  background: "rgba(9,12,18,.94)", color: C.darkInk,
  border: `1px solid ${C.warn}66`, borderRadius: 12,
  padding: "10px 16px", fontSize: F.base,
};
export const vehChip: React.CSSProperties = {
  background: "#1f2937", color: "#fff", borderRadius: 8, padding: "6px 12px",
  fontSize: 14, fontWeight: 800,
};

export function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ ...shell, display: "grid", placeItems: "center",
                       padding: 24, textAlign: "center" }}>{children}</div>;
}

/** 사건 지점 연기 — 와이어프레임 05 · 15 · 23. 순수 CSS 라 지도 위 DOM 마커에 붙는다 */
export const SMOKE_CSS = `
.fl-smoke{position:absolute;left:50%;top:-6px;width:0;height:0;pointer-events:none}
.fl-smoke i{position:absolute;left:-14px;top:-10px;width:28px;height:28px;border-radius:50%;
  background:radial-gradient(circle,rgba(90,90,96,.55),rgba(120,120,128,0) 70%);
  animation:flsmoke 3.2s linear infinite}
.fl-smoke i:nth-child(2){animation-delay:1.05s}
.fl-smoke i:nth-child(3){animation-delay:2.1s}
@keyframes flsmoke{0%{transform:translate(0,0) scale(.5);opacity:0}
  15%{opacity:.9}100%{transform:translate(10px,-70px) scale(2.2);opacity:0}}`;
