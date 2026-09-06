/**
 * ui/BottleneckPanel.tsx — 병목 구간 상세. (와이어프레임 3)
 *
 * ★ "측정 신뢰도" 는 `width_cov` 다 — 그 구간에서 폭 표본이 실제로 덮은
 *   비율이며, 우리가 만든 값이 아니라 파이프라인이 낸 값이다.
 *
 * ★ `n_sample` 이 1 이면 표본 하나로 낸 폭이다. `verdict()` 가 그 경우
 *   통과 확정을 보류한다 — 화면도 그것을 드러내야 한다.
 *
 * ★ 하단 세 줄은 **지우지 마라.** 판정이 무엇을 보고 무엇을 안 보는지
 *   화면에 남기는 유일한 장치다(DECISIONS §86-5 가 겪은 자리).
 */
import type { CSSProperties, ReactNode } from "react";
import { C, F, S } from "./tokens";

export interface BottleneckData {
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
  onClose: () => void;
  onReroute?: () => void;
}

export function BottleneckPanel(d: BottleneckData) {
  const margin = d.widthM != null ? d.widthM - d.requiredM : null;
  return (
    <div style={panel}>
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center" }}>
        <div style={{ fontSize: F.mid, fontWeight: 800 }}>병목 구간 상세</div>
        <button onClick={d.onClose} style={x} aria-label="닫기">✕</button>
      </div>

      <div style={{ display: "inline-block", marginTop: 10, borderRadius: 999,
                    background: "rgba(245,158,11,.16)", color: C.warnInk,
                    padding: "4px 12px", fontSize: F.small, fontWeight: 700 }}>
        현장 확인 필요
      </div>

      <div style={{ marginTop: 8, fontSize: F.base, color: C.panelSub }}>
        {d.segLabel}
        {d.aheadM != null && ` · 전방 ${Math.round(d.aheadM)}m`}
      </div>
      <div style={{ fontSize: F.base, fontWeight: 800, marginTop: 2,
                    color: d.verdictColor }}>{d.verdictLabel}</div>

      <div style={grid}>
        <Cell k="유효 도로 폭"
              v={d.widthM != null ? `${d.widthM.toFixed(2)}m` : "—"} />
        <Cell k="차량 요구 폭" v={`${d.requiredM.toFixed(1)}m`} />
        <Cell k="계산상 여유"
              v={margin != null ? `${margin.toFixed(2)}m` : "—"}
              warn={margin != null && margin < 0.5} />
        <Cell k="구간 길이"
              v={d.lengthM != null ? `${Math.round(d.lengthM)}m` : "—"} />
      </div>

      <div style={head}>판정 근거</div>
      <Row k="측정 신뢰도"
           v={d.coverage != null ? `${Math.round(d.coverage * 100)}%` : "—"}
           warn={d.coverage != null && d.coverage < 0.5} />
      <Row k="폭 표본 수"
           v={d.samples != null ? `${d.samples}개` : "—"}
           warn={d.samples === 1} />
      <Row k="영상판정"
           v={d.cctvDistM == null ? "—"
              : d.cctvDistM <= 25 ? `가능 (CCTV ${Math.round(d.cctvDistM)}m)`
              : `불가 (CCTV ${Math.round(d.cctvDistM)}m)`}
           warn={d.cctvDistM != null && d.cctvDistM > 25} />
      <Row k="도면 기반 1차 판정" v="✓" />

      {/* ★ 이 세 줄이 판정의 경계다. 지우지 마라. */}
      <div style={note}>
        실시간 주정차 미반영<br />
        회전 및 높이 통과 여부는 판정하지 않습니다<br />
        폭은 도면 기반 미검증 값입니다
      </div>

      {d.onReroute && (
        <button onClick={d.onReroute} style={btn}>우회 경로 찾기</button>
      )}
    </div>
  );
}

function Cell({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ padding: "10px 12px", background: C.panel }}>
      <div style={{ fontSize: F.tiny, color: C.panelSub }}>{k}</div>
      <div style={{ fontSize: F.big, fontWeight: 800,
                    color: warn ? C.danger : C.panelInk }}>{v}</div>
    </div>
  );
}
function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between",
                  fontSize: F.base, padding: "3px 0" }}>
      <span style={{ color: C.panelSub }}>{k}</span>
      <span style={{ fontWeight: 700, color: warn ? C.danger : C.panelInk }}>{v}</span>
    </div>
  );
}

const panel: CSSProperties = {
  position: "absolute", zIndex: 5, top: S.guideBarH + 14, right: 14, width: 320,
  background: C.panel, color: C.panelInk,
  border: `1px solid ${C.panelLine}`, borderRadius: S.radius,
  padding: `${S.pad - 2}px ${S.pad}px`,
  boxShadow: "0 10px 34px rgba(0,0,0,.4)",
};
const grid: CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, margin: "12px 0 14px",
  background: C.panelLine, border: `1px solid ${C.panelLine}`,
  borderRadius: S.radiusSm, overflow: "hidden",
};
const head: CSSProperties = {
  fontSize: F.small, fontWeight: 700, color: C.panelSub, marginBottom: 4,
};
const note: CSSProperties = {
  marginTop: 12, paddingTop: 10, borderTop: `1px solid ${C.panelLine}`,
  fontSize: F.small, color: C.panelSub, lineHeight: 1.6,
};
const btn: CSSProperties = {
  marginTop: 12, width: "100%", background: C.link, color: "#fff",
  border: "none", borderRadius: S.radiusSm, padding: "11px 0",
  fontSize: F.base, fontWeight: 700, cursor: "pointer", fontFamily: F.family,
};
const x: CSSProperties = {
  background: "none", border: "none", color: C.panelSub,
  fontSize: 18, cursor: "pointer", padding: 0, lineHeight: 1,
};

export type { ReactNode };
