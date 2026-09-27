/**
 * ui/opsTheme.ts — 관제실 톤과 틀.  (DECISIONS §216-4)
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `OpsApp.tsx` 가 744줄로 길이 상한(600)을 넘었고 그 중 백 줄이 **모양
 *   상수**였다. 배선(적재 · 링크 · 미리보기 경로)을 고치러 온 사람이 `borderRadius` 를
 *   백 줄 넘겨 지나가야 했다. 값만 있는 것은 값만 있는 파일에 둔다 — `ui/tokens.ts` 가
 *   내비 쪽에서 이미 그 자리다.
 *
 * ★ **판정 4색은 여기 없다.** 정본은 `web/config.js` 이고 `navi_graph.json.style` 로
 *   흘러온다(MASTER §10-2). 여기 있는 것은 틀 · 글자 · 상태 색뿐이다 — 다섯 번째
 *   판정색을 여기서 만들면 `test_contract` 가 문다.
 *
 * ★ 관제는 내비와 **다른 톤**이다(§216-4). 상황실 벽 화면이라 어둡고, 내비는 운전석이라
 *   밝다. 그래서 `ui/tokens.ts` 의 `C` 를 쓰지 않고 따로 둔다 — 한 자리에 합치면 한쪽을
 *   고칠 때 다른 쪽이 따라 바뀐다.
 *
 * IN    (없음 — 상수뿐이다)
 * OUT   D(색) · 화면 틀 · 패널 · 단추 · 줄의 CSSProperties
 * 밖    무엇을 그릴지는 여기서 안 정한다. 조각은 `OpsBits.tsx` · `OpsSegCard.tsx` 다.
 */
import { F } from "./tokens";

export const D = {
  bg: "#0b1220", panel: "#0f172a", card: "#111c2f", line: "#23324a", ink: "#e5e7eb", sub: "#94a3b8",
  accent: "#38bdf8", ok: "#22c55e", warn: "#f59e0b", danger: "#ef4444",
};
export const shell: React.CSSProperties = {
  position: "fixed", inset: 0, background: D.bg, fontFamily: F.family, color: D.ink,
  display: "flex", flexDirection: "column",
};
export const top: React.CSSProperties = {
  height: 58, flex: "0 0 auto", display: "flex", alignItems: "center", gap: 10, padding: "0 14px",
  borderBottom: `1px solid ${D.line}`, background: "#070d18",
};
export const tile: React.CSSProperties = {
  border: `1px solid ${D.line}`, borderRadius: 8, padding: "4px 10px", background: D.panel, minWidth: 74,
};
export const clock: React.CSSProperties = {
  fontSize: 22, fontWeight: 800, fontVariantNumeric: "tabular-nums", marginLeft: 6, color: D.accent,
};
export const body: React.CSSProperties = {
  flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "340px 1fr 360px",
};
export const colL: React.CSSProperties = {
  borderRight: `1px solid ${D.line}`, overflowY: "auto", padding: 10, display: "flex", flexDirection: "column", gap: 10,
  background: D.panel,
};
export const colR: React.CSSProperties = { ...colL, borderRight: "none", borderLeft: `1px solid ${D.line}` };
export const mapBox: React.CSSProperties = { position: "relative", minWidth: 0 };
export const secBox: React.CSSProperties = {
  background: D.card, border: `1px solid ${D.line}`, borderRadius: 10, padding: "10px 12px",
};
export const whyBox: React.CSSProperties = {
  fontSize: 11.5, background: "#0f172a", border: "1.5px solid", borderRadius: 8,
  padding: "7px 9px", margin: "8px 0 2px", lineHeight: 1.5,
};
export const legendBox: React.CSSProperties = {
  position: "absolute", left: 10, bottom: 10, width: 270, zIndex: 3, background: "rgba(11,18,32,.9)",
  border: `1px solid ${D.line}`, borderRadius: 10, padding: "8px 10px", fontSize: 12,
};
// ★ 접기 손잡이. 접었을 때도 **무엇이 접혀 있는지** 보여야 한다 —
//   빈 막대만 남으면 다음 사람이 그것을 지우려고 한다.
export const legendHead: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 6, width: "100%", padding: 0, marginBottom: 6,
  background: "transparent", border: "none", color: D.sub, cursor: "pointer",
  fontFamily: F.family, fontSize: 11, fontWeight: 800,
};
export const input: React.CSSProperties = {
  flex: 1, width: "100%", boxSizing: "border-box", border: `1px solid ${D.line}`, borderRadius: 8,
  padding: "8px 10px", fontSize: 13, fontFamily: F.family, background: D.panel, color: D.ink,
};
export const btnSm: React.CSSProperties = {
  border: `1px solid ${D.accent}`, borderRadius: 8, padding: "0 10px", fontWeight: 800, fontSize: 12,
  cursor: "pointer", fontFamily: F.family, whiteSpace: "nowrap",
};
export const linkBtn: React.CSSProperties = {
  border: "none", background: "none", color: D.sub, fontSize: 11, cursor: "pointer", padding: 0,
  fontFamily: F.family, textDecoration: "underline",
};
export const list: React.CSSProperties = { border: `1px solid ${D.line}`, borderRadius: 8, marginTop: 6, overflow: "hidden" };
export const listItem: React.CSSProperties = {
  display: "block", width: "100%", textAlign: "left", border: "none", borderBottom: `1px solid ${D.line}`,
  background: D.panel, color: D.ink, padding: "7px 10px", cursor: "pointer", fontFamily: F.family, fontSize: 13,
};
export const card: React.CSSProperties = {
  marginTop: 8, border: `1.5px solid ${D.line}`, borderRadius: 10, padding: "9px 11px", background: D.panel,
};
export const lab: React.CSSProperties = { display: "block", fontSize: 11, color: D.sub, margin: "8px 0 4px" };
export const vehRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, border: "1px solid", borderRadius: 8, padding: "4px 8px",
  cursor: "pointer", fontFamily: F.family, color: D.ink,
};
export const cta: React.CSSProperties = {
  width: "100%", marginTop: 10, border: "none", borderRadius: 10, padding: "12px 0",
  background: "linear-gradient(90deg,#dc2626,#ef4444)", color: "#fff", fontWeight: 800, fontSize: 15,
  cursor: "pointer", fontFamily: F.family, letterSpacing: .3,
};
export const modeBtn: React.CSSProperties = {
  flex: 1, border: "1px solid", borderRadius: 7, padding: "4px 0", fontSize: 11.5, fontWeight: 800,
  cursor: "pointer", fontFamily: F.family,
};
export const legendRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, width: "100%", border: "none", background: "none",
  padding: "3px 0", cursor: "pointer", fontFamily: F.family, color: D.ink, fontSize: 12,
};
export const dot: React.CSSProperties = { width: 12, height: 12, borderRadius: 6, flex: "0 0 auto", border: "2px solid rgba(255,255,255,.25)" };
export const toggleRow: React.CSSProperties = { display: "flex", alignItems: "center", gap: 7, fontSize: 12, padding: "2px 0" };
export const chip: React.CSSProperties = { border: "1px solid", borderRadius: 999, padding: "1px 8px", fontSize: 11, fontWeight: 800 };
export const unitRow: React.CSSProperties = {
  display: "flex", flexDirection: "column", alignItems: "flex-start", width: "100%", gap: 2, marginTop: 6,
  border: `1px solid ${D.line}`, borderRadius: 8, padding: "7px 9px", background: D.panel,
  cursor: "pointer", fontFamily: F.family, color: D.ink, textAlign: "left",
};
export const feedRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, padding: "7px 0", borderBottom: `1px solid ${D.line}`,
};
export const ackBtn: React.CSSProperties = {
  border: "none", background: D.accent, color: "#0b1220", borderRadius: 7, padding: "6px 11px",
  fontWeight: 800, cursor: "pointer", fontFamily: F.family,
};
