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

  // ── 2026-09-21 와이어프레임 (지혜님) ─────────────────────────
  // ★ 상단바는 한 벌이다. 상태마다 바뀌는 것은 배지 색 넷뿐이다
  //   (`domain/status.ts::Tone`).
  topBar: "#1552d8",
  topBarSub: "rgba(255,255,255,.82)",
  toneGreen: "#22d35e",
  toneYellow: "#fcd535",
  toneCyan: "#2fd4f0",
  toneWhite: "#ffffff",
  toneInk: "#0b1b3a",
  timeBox: "#0b1220",
  timeGreen: "#38e08a",
  /** 경로 — 기본 파랑, 비교용 주황, CCTV 미검증 보라 */
  route: "#2563eb",
  routeAlt: "#f97316",
  routeUnverified: "#7c3aed",
  routeBottleneck: "#ef4444",
  routePending: "#22d3ee",
  incident: "#ef2d2d",
  station: "#2563eb",
  /** 좌측 패널 */
  sheetBg: "#ffffff",
  sheetLine: "rgba(15,23,42,.12)",
  cta: "#1e7cf2",
  ctaInk: "#ffffff",
  softBlue: "#eef4ff",
} as const;

/**
 * 지도 주간 테마. 와이어프레임 09-21 이 **밝은 낮 도시**다.
 * ★ 판정색은 여기 없다 — 판정 음영은 `layers.ts` 가 정본 색에서 파생한다.
 */
export const MAP = {
  bg: [226, 231, 237] as [number, number, number],
  road: "#ffffff",
  roadCase: "#b9c2cd",
  bldgLow: "#e3e7ec",
  bldgHigh: "#c9d0d8",
  label: "#374151",
  labelHalo: "#ffffff",
} as const;

export const S = {
  gap: 12,
  pad: 16,
  radius: 16,
  radiusSm: 10,
  /** 상단 안내 바 높이. 지도 카메라 padding 이 이 값을 쓴다 */
  guideBarH: 96,
  /** 좌측 패널 폭(00 · 01 · 02). 지도 카메라가 이만큼 비켜 선다 */
  sheetW: 460,
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
