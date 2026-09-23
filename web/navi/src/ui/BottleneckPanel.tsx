/**
 * ui/BottleneckPanel.tsx — 병목 구간 상세.  (와이어프레임 04 · 04.5 · 2026-09-21)
 *
 *   열림 (04)   우측 시트. 유효폭 · 요구폭 · **여유폭** · 길이 · 사유 · 판정 근거 · 단추 둘
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
 * ★ 하단 두 줄은 **지우지 마라.** 판정이 무엇을 보고 무엇을 안 보는지
 *   화면에 남기는 유일한 장치다(DECISIONS §86-5 가 겪은 자리). 09-05 판에서
 *   주행 화면 우측 패널에 있던 것이 여기로 옮겨 왔다.
 */
import type { CSSProperties, ReactNode } from "react";
import { C, F, S } from "./tokens";
import { CLEARANCE_SCALE, type SegmentReason } from "./clearanceMeaning";
import { clearanceBand, fmtClearance } from "../domain/clearance";

export interface BottleneckData {
  segUid: string;
  segLabel: string;
  aheadM: number | null;
  widthM: number | null;
  requiredM: number;
  lengthM: number | null;
  /** width_cov 0~1. 표본이 구간을 덮은 비율 */
  coverage: number | null;
  /** n_sample. 1이면 표본 하나로 낸 값이다 */
  samples: number | null;
  verdictLabel: string;
  verdictColor: string;
  /** 가장 가까운 CCTV 까지 거리(m). 25m 넘으면 영상판정이 성립 안 한다 */
  cctvDistM: number | null;
  /** 회색이면 왜 회색인가(§215-2). 아니면 null */
  grayReason: string | null;
  /**
   * 왜 그 색인가 · 지금 무엇을 하나(§220). 초록이고 여유가 넉넉하면 null —
   * 취할 조치가 없으면 그 칸을 통째로 뺀다.
   */
  reason: SegmentReason | null;
  /** 그 도로명의 불법주정차 단속 건수(§216-3). 도로 단위 · 위험의 대리값 */
  park: number | null;
}

interface Props extends BottleneckData {
  open: boolean;
  onToggle: () => void;
  onShare: () => void;
  onReport: () => void;
}

export function BottleneckPanel(d: Props) {
  if (!d.open) {
    return (
      <button onClick={d.onToggle} style={tab} aria-label="병목 구간 상세 열기" data-wf="04.5">
        <svg width="30" height="30" viewBox="0 0 24 24"><path d="M12 3 L22 20 H2 Z" fill={C.warn} /><path d="M12 9v5M12 16.5v.5" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" /></svg>
      </button>
    );
  }
  // ★ 2026-09-23 (§220) 여유폭 = 유효폭 − 요구폭. 수와 **같은 4단 색**을 함께 낸다 —
  //   멘토링(§219)이 「색과 수로」 라고 한 자리다. 판정은 안 바뀐다.
  const margin = d.widthM != null ? d.widthM - d.requiredM : null;
  const band = CLEARANCE_SCALE[clearanceBand(margin)];
  const cctvOk = d.cctvDistM != null && d.cctvDistM <= 25;
  return (
    <div style={panel} data-wf="04">
      <button onClick={d.onToggle} style={collapse} aria-label="접기">›</button>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 20, fontWeight: 800 }}>병목 구간 상세</div>
        <button onClick={d.onToggle} style={x} aria-label="닫기">✕</button>
      </div>
      <span style={chip}>현장 확인 필요</span>
      <div style={{ fontSize: 13, color: C.panelSub, marginTop: 8 }}>
        {d.segLabel}{d.aheadM != null ? ` · 전방 ${Math.round(d.aheadM)}m` : ""}
      </div>

      <div style={grid}>
        <Tile k="최소 유효폭" v={d.widthM != null ? `${d.widthM.toFixed(1)}m` : "—"} />
        <Tile k="요구폭 (전폭 + 여유)" v={`${d.requiredM.toFixed(1)}m`} />
        <Tile k="여유폭 = 유효폭 − 요구폭" v={fmtClearance(margin)} sub={band.short} color={band.color} />
        <Tile k="구간 길이" v={d.lengthM != null ? `${Math.round(d.lengthM)}m` : "—"} />
      </div>

      {d.reason && (
        <div style={{ ...why, borderColor: band.color }}>
          <b style={{ color: band.color }}>{d.reason.head}</b>
          <div style={{ marginTop: 2 }}>{d.reason.detail}</div>
          {d.reason.action && <div style={{ color: C.panelSub, marginTop: 2 }}>→ {d.reason.action}</div>}
        </div>
      )}

      <Section title="장애물 · 위험 요소">
        <Line k="주차 차량" v="미반영" note="CCTV 영상 판정 전" />
        <Line k="불법주정차 단속 이력" v={d.park ? `${d.park.toLocaleString()}건` : "없음"}
              note="이 도로명 전체 · 2022-01~2025-02 — 지금 주차가 아니다" />
        <Line k="회전 · 높이" v="미반영" note="회전반경은 참고값 · 판정 안 함" />
      </Section>

      <Section title="판정 근거">
        <Line k="측정 신뢰도" v={d.coverage != null ? `${Math.round(d.coverage * 100)}%` : "—"} blue />
        <Line k="폭 표본" v={d.samples != null ? `${d.samples}개` : "—"}
              note={d.samples === 1 ? "표본 하나 — 통과 확정 보류" : undefined} />
        <Line k="가까운 CCTV" v={d.cctvDistM != null ? `${Math.round(d.cctvDistM)}m` : "—"}
              note={cctvOk ? "영상 판정 가능 거리" : "25m 밖 — 영상 판정 불가"} />
        <Line k="판정" v={d.verdictLabel} color={d.verdictColor} />
        {d.grayReason && (
          <div style={{ fontSize: 11, color: C.panelInk, padding: "6px 0", lineHeight: 1.5 }}>
            <b>회색 사유</b> — {d.grayReason}
          </div>
        )}
      </Section>

      <div style={honest}>
        실시간 주정차 · 공사 · 이동 장애물은 반영되지 않았습니다.<br />
        폭은 도면 기반 미검증 값이며, 회전 및 높이 통과 여부는 판정하지 않습니다.
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button onClick={d.onShare} style={ghost}>관제에 공유</button>
        <button onClick={d.onReport} style={cta}>통행 불가 신고 »</button>
      </div>
    </div>
  );
}

function Tile({ k, v, sub, color }: { k: string; v: string; sub?: string; color?: string }) {
  return (
    <div style={tile}>
      <div style={{ fontSize: 11, color: C.panelSub }}>{k}</div>
      <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4, color: color ?? C.panelInk }}>
        {v}{sub && <span style={{ fontSize: 11, fontWeight: 700, color: C.panelSub }}> {sub}</span>}
      </div>
    </div>
  );
}
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 6 }}>{title}</div>
      <div style={{ background: "#f8fafc", borderRadius: 10, padding: "4px 10px" }}>{children}</div>
    </div>
  );
}
function Line({ k, v, note, blue, color }: {
  k: string; v: string; note?: string; blue?: boolean; color?: string;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
                  padding: "6px 0", borderBottom: `1px solid ${C.sheetLine}`, fontSize: 13 }}>
      <span>
        {k}
        {note && <span style={{ display: "block", fontSize: 10, color: C.panelSub }}>{note}</span>}
      </span>
      <b style={{ color: color ?? (blue ? C.cta : C.panelInk) }}>{v}</b>
    </div>
  );
}

const PANEL_W = 380;
const panel: CSSProperties = {
  position: "absolute", zIndex: 5, top: S.guideBarH + 14, right: 14, bottom: 60, width: PANEL_W,
  background: "#fff", color: C.panelInk, padding: "18px 20px", boxSizing: "border-box",
  overflowY: "auto", borderRadius: 20, boxShadow: "0 10px 30px rgba(0,0,0,.28)",
  fontFamily: F.family,
};
const collapse: CSSProperties = {
  position: "fixed", right: 14 + PANEL_W - 2, top: `calc(50% + ${S.guideBarH / 2 - 36}px)`,
  width: 40, height: 76, border: "none", borderRadius: "76px 0 0 76px", background: C.cta,
  color: "#fff", fontSize: 28, fontWeight: 800, cursor: "pointer", paddingLeft: 8,
  boxShadow: "-3px 3px 10px rgba(0,0,0,.2)",
};
const tab: CSSProperties = {
  position: "absolute", zIndex: 5, right: 0, top: `calc(50% + ${S.guideBarH / 2 - 38}px)`,
  width: 52, height: 76, border: `3px solid ${C.warn}`, borderRight: "none",
  borderRadius: "16px 0 0 16px", background: "#fff", cursor: "pointer",
  display: "grid", placeItems: "center", boxShadow: "-3px 3px 12px rgba(0,0,0,.25)",
};
const chip: CSSProperties = {
  display: "inline-block", marginTop: 10, borderRadius: 999, background: C.warn,
  color: "#fff", padding: "5px 14px", fontSize: 13, fontWeight: 800,
};
const grid: CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12,
};
const tile: CSSProperties = { background: "#f8fafc", borderRadius: 10, padding: "10px 12px" };
const why: CSSProperties = {
  marginTop: 10, border: "1.5px solid", borderRadius: 10, padding: "9px 11px",
  fontSize: 12, lineHeight: 1.5, background: "#f8fafc",
};
const honest: CSSProperties = {
  marginTop: 12, fontSize: 11, color: C.panelSub, lineHeight: 1.5,
};
const x: CSSProperties = {
  background: "none", border: "none", fontSize: 20, cursor: "pointer", color: C.panelSub,
};
const ghost: CSSProperties = {
  flex: 1, border: `1.5px solid ${C.cta}`, background: "#fff", color: C.cta, borderRadius: 10,
  padding: "12px 0", fontWeight: 800, fontSize: 14, cursor: "pointer", fontFamily: F.family,
};
const cta: CSSProperties = {
  flex: 1.3, border: "none", background: C.cta, color: "#fff", borderRadius: 10,
  padding: "12px 0", fontWeight: 800, fontSize: 14, cursor: "pointer", fontFamily: F.family,
};
