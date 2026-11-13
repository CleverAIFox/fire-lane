/**
 * ui/BottleneckPanel.tsx — 병목 구간 상세.  (와이어프레임 04 · 04.5 · 2026-09-21)
 *
 *   열림 (04)   우측 카드. **다음 구간 하나** — 거리 · 도로명 · 위험 종류 · 여유 · 외 N곳 · 단추 셋(공유 · 신고 · 자세히)
 *   접힘 (04.5) 우측 가장자리 주황 ⚠ 탭. 누르면 연다
 *
 * ★ "측정 신뢰도" 는 `width_cov` 다 — 그 구간에서 폭 표본이 실제로 덮은
 *   비율이며, 우리가 만든 값이 아니라 파이프라인이 낸 값이다.
 *
 * ★ 와이어프레임은 「장애물 · 위험 요소 — 주차 차량 45m · 급회전 전방」 을
 *   띄운다. **그 데이터가 없다.** 실시간 주정차는 CCTV 영상 판정(CV)이
 *   서야 나오고, 회전은 판정하지 않는다(`turn_radius_verified: false`).
 *   없는 것을 있는 것처럼 채우지 않고 「미반영」 으로 적는다.
 *
 * ★ 2026-09-22 (§214-2) 와이어프레임 모양으로 — 오른쪽에 **떠 있는 둥근 카드**(가장자리
 *   시트가 아니다), 카드 왼쪽 가장자리에 파란 **반원 접기 탭**, 「현장 확인 필요」 는 꽉 찬
 *   주황. 접힘(04.5)은 흰 바탕 · 주황 테두리 · 주황 삼각형 탭을 오른쪽 가장자리 **가운데**에.
 *
 * ★ 2026-09-23 (§220) 멘토링(§219) 둘 — 「여유폭을 색과 수로」 와 「빨간 도로는 색만이
 *   아니라 사유를 적는다」. 여유폭 칸이 `ui/clearanceMeaning` 의 4단 색을 입고, 그 밑에
 *   사유 한 줄(무엇이 얼마나 모자란가 · 지금 무엇을 하나)이 붙는다. 사유는 빨강 전용이
 *   아니라 판정마다 있고, **취할 조치가 없으면 통째로 빠진다**(`segmentReason` 이 null).
 *
 * ★ 2026-11-12 (DECISIONS §703). **기본 화면은 「다음 구간 하나 · 네 줄」이다.** 종전에는 열면 54줄(유효폭 · 요구폭 · 여유폭 · 길이 · 사유 ·
 *   판정 근거 …)이었고 그 45줄이 24px 미만이었다(DECISIONS §702) — 운전자가 한 시선 2초로 읽을 양이 아니다. 자리(안내 중 앞 400m)는 맞았고
 *   **양이 틀렸다.** 지금은 거리 · 도로명 · 무엇이 위험한가 · 여유 — 그리고 「외 N곳」(아직 몇 개 남았나)만 수로 남긴다. 나머지 구간은 **차례로** 뜬다
 *   (지나가면 다음 것 — 목록이 아니라 흐름이다 · 턴바이턴의 방식). 옛 몸통은 `BottleneckDetail`(자세히)로 옮겼고 **지우지 않았다** — 「판정이 무엇을
 *   보고 무엇을 안 보는가」 를 화면에 남기는 장치(§86-5)가 거기 산다.
 * ★ 누르는 곳은 전부 **76dp 이상**이다(Android Auto 의 터치 타깃 기준). 보이는 모양은 그대로이고 **누르는 범위**만 키웠다.
 */
import { useEffect, useState, type CSSProperties } from "react";
import { C, F, S } from "./tokens";
import { CLEARANCE_SCALE } from "./clearanceMeaning";
import { clearanceBand, fmtClearance } from "../domain/clearance";
import { BottleneckDetail, type BottleneckData } from "./BottleneckDetail";
import { RISK_KIND_TEXT } from "./routeOption";

export type { BottleneckData };

/** 누르는 범위의 최소 — Android Auto 터치 타깃 76×76dp(DECISIONS §702). 보이는 모양이 아니라 **누르는 범위**가 이 크기다. */
export const TARGET = 76;

interface Props extends BottleneckData {
  open: boolean;
  onToggle: () => void;
  onShare: () => void;
  onReport: () => void;
  /**
   * **달리는 중이다 — 「자세히」 를 못 연다.** 정차 중에 읽는 상세를 움직이는 차에서 열면 한 시선 2초 규범(DECISIONS §702)을 깬다.
   * 열려 있던 것도 닫힌다. 속도는 `domain/motion.ts`(§704)가 안다.
   */
  locked: boolean;
}

export function BottleneckPanel(d: Props) {
  const [more, setMore] = useState(false);
  // 달리기 시작하면 열려 있던 상세를 닫는다(다시 서도 저절로 열리지 않는다). 렌더에서도 막는다 — 효과는 한 박자 늦다.
  useEffect(() => { if (d.locked) setMore(false); }, [d.locked]);
  const showMore = more && !d.locked;
  if (!d.open) {
    return (
      <button onClick={d.onToggle} style={tab} aria-label="병목 구간 상세 열기" data-wf="04.5">
        <svg width="30" height="30" viewBox="0 0 24 24"><path d="M12 3 L22 20 H2 Z" fill={C.warn} /><path d="M12 9v5M12 16.5v.5" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" /></svg>
      </button>
    );
  }
  // ★ 폭 모름이면 여유도 모른다 — 여유 줄을 아예 안 쓴다(모르는 수를 쓰면 보는 사람이 믿는다).
  const margin = d.widthM != null && d.kind !== "unknown" ? d.widthM - d.requiredM : null;
  const band = CLEARANCE_SCALE[clearanceBand(margin)];
  return (
    <div style={panel} data-wf="04">
      <button onClick={d.onToggle} style={collapse} aria-label="접기">›</button>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 32, fontWeight: 800 }}>{d.aheadM != null ? `${Math.round(d.aheadM)}m 앞` : "전방"}</span>
        {d.more > 0 && <span style={{ fontSize: 24, fontWeight: 800, color: C.panelSub }}>외 {d.more}곳</span>}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, marginTop: 2 }}>{d.segLabel}</div>
      <div style={{ fontSize: 24, fontWeight: 800, marginTop: 6, color: d.kind === "blocked" ? C.danger : C.warn }}>{RISK_KIND_TEXT[d.kind]}</div>
      {margin != null && <div style={{ fontSize: 24, fontWeight: 800, color: band.color }}>여유 {fmtClearance(margin)}</div>}

      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button onClick={d.onShare} style={ghost}>관제에 공유</button>
        <button onClick={d.onReport} style={cta}>통행 불가 신고</button>
        <button onClick={() => setMore((x) => !x)} aria-expanded={showMore} disabled={d.locked}
                style={d.locked ? { ...ghost, opacity: 0.35, cursor: "not-allowed" } : ghost}>{showMore ? "접기" : "자세히"}</button>
      </div>
      {showMore && <div style={{ marginTop: 12 }}><BottleneckDetail {...d} /></div>}
    </div>
  );
}

const PANEL_W = 380;
const panel: CSSProperties = {
  position: "absolute", zIndex: 5, top: S.guideBarH + 14, right: 14, width: PANEL_W,
  maxHeight: `calc(100% - ${S.guideBarH + 14 + 60}px)`,
  background: "#fff", color: C.panelInk, padding: "16px 18px", boxSizing: "border-box",
  overflowY: "auto", borderRadius: 20, boxShadow: "0 10px 30px rgba(0,0,0,.28)",
  fontFamily: F.family,
};
const collapse: CSSProperties = {
  position: "fixed", right: 14 + PANEL_W - 2, top: S.guideBarH + 14 + 24,
  width: TARGET, height: TARGET, border: "none", borderRadius: `${TARGET}px 0 0 ${TARGET}px`, background: C.cta,
  color: "#fff", fontSize: 28, fontWeight: 800, cursor: "pointer", paddingRight: 24,
  boxShadow: "-3px 3px 10px rgba(0,0,0,.2)",
};
const tab: CSSProperties = {
  position: "absolute", zIndex: 5, right: 0, top: `calc(50% + ${S.guideBarH / 2 - TARGET / 2}px)`,
  width: TARGET, height: TARGET, border: `3px solid ${C.warn}`, borderRight: "none", boxSizing: "border-box",
  borderRadius: "16px 0 0 16px", background: "#fff", cursor: "pointer",
  display: "grid", placeItems: "center", boxShadow: "-3px 3px 12px rgba(0,0,0,.25)",
};
const btn: CSSProperties = {
  minHeight: TARGET, minWidth: TARGET, borderRadius: 10, padding: "0 6px", fontWeight: 800, fontSize: 24, cursor: "pointer",
  fontFamily: F.family,
};
const ghost: CSSProperties = { ...btn, flex: 1, border: `1.5px solid ${C.cta}`, background: "#fff", color: C.cta };
const cta: CSSProperties = { ...btn, flex: 1.3, border: "none", background: C.cta, color: "#fff" };
