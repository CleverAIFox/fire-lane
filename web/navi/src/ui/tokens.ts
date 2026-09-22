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
  /** 범례용. 경로 위 병목 색은 정본(`style.needs_cv`)에서 온다 — layers.ts */
  routeBottleneck: "#ffab2e",
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
/**
 * 바탕 지도 색. `components/layers.ts` 가 읽는다.
 *
 * ★ 2026-09-22 (DECISIONS §213-4) 대비를 올렸다. 종전 판은 흰 도로 선 · 밝은 회색
 *   건물 · 밝은 회청 바탕이라 **명도 차가 거의 없었다**(바탕 226 · 도로 255 · 건물 227).
 *   와이어프레임 09-21 의 순서로 바꾼다 —
 *
 *       바탕(블록)    밝은 모래색     L≈90
 *       보도          한 단 어둡게     L≈83
 *       도로면        짙은 아스팔트    L≈50     ← 경로 파랑이 여기 위에서 뜬다
 *       건물 벽       중간 회색        L≈72~66
 *       건물 지붕     밝은 회백        L≈94     ← 위에서 보면 블록 윤곽이 선다
 */
export const MAP = {
  bg: [232, 228, 218] as [number, number, number],
  sidewalk: "#d6d0c3",
  asphalt: "#6f7680",
  asphaltEdge: "#5b616a",
  marking: "#f4f1e8",
  /** 옛 이름 — 판정 음영 파생(`shade`)과 범례가 아직 읽는다 */
  road: "#6f7680",
  roadCase: "#5b616a",
  bldgLow: "#aab0b9",
  bldgHigh: "#8f96a1",
  roof: "#e2e5e9",
  label: "#1f2937",
  labelHalo: "#ffffff",
  roadLabel: "#ffffff",
  roadLabelHalo: "#3f454d",
} as const;

export const S = {
  gap: 12,
  pad: 16,
  radius: 16,
  radiusSm: 10,
  /**
   * 상단 안내 바 높이. 지도 카메라 padding 이 이 값을 쓴다.
   * ★ 2026-09-22 (§214-2) 96 → 124. 와이어프레임은 화면 높이의 15%(992 에서 153)다.
   *   주행 중 한눈에 읽어야 하는 유일한 글자라 크게 둔다 — 지도를 덜 가리는 선에서.
   */
  guideBarH: 124,
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
