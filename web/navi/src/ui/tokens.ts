/**
 * ui/tokens.ts — 화면 상수 한 자리.
 *
 * ── 왜 모으나 ───────────────────────────────────────────────────
 * 색·간격·글자 크기를 컴포넌트마다 적으면 톤을 바꿀 때 스무 군데를
 * 찾아다녀야 한다. **여기만 고치면 전부 따라온다.**
 *
 * ★ 판정 4색은 여기 없다. 정본은 `web/config.js` 이고
 *   `navi_graph.json.style` 로 흘러온다(MASTER §10-2). 다섯 번째 색을
 *   만들면 `test_contract` 가 문다.
 *
 * ★ 판정 임계값(3.0 / 7.0)을 여기 적지 마라. 정본은 `seg/params.py` 다.
 *   여기 있는 것은 **표현**뿐이다.
 */

/** 와이어프레임(지혜님, 2026-09-05)의 색. */
export const C = {
  guideBar: "#1d4ed8",
  guideBarText: "#ffffff",
  safe: "#22c55e",
  safeInk: "#15803d",
  warn: "#f59e0b",
  warnInk: "#b45309",
  danger: "#ef4444",
  panel: "#ffffff",
  panelInk: "#0f172a",
  panelSub: "#64748b",
  panelLine: "rgba(15,23,42,.10)",
  dark: "rgba(9,12,18,.92)",
  darkInk: "#e8ecf4",
  mapBg: "#0b0e14",
  link: "#2563eb",
} as const;

export const S = {
  gap: 12,
  pad: 16,
  radius: 16,
  radiusSm: 10,
  /** 상단 안내 바 높이. 지도 카메라 padding 이 이 값을 쓴다 */
  guideBarH: 96,
} as const;

export const F = {
  family: "Pretendard, system-ui, sans-serif",
  huge: 34,
  big: 22,
  mid: 16,
  base: 14,
  small: 12,
  tiny: 11,
} as const;

export function fmtDist(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)}km` : `${Math.round(m)}m`;
}
export function fmtDur(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  return s < 60 ? `${s}초` : `${Math.floor(s / 60)}분${s % 60 ? ` ${s % 60}초` : ""}`;
}
