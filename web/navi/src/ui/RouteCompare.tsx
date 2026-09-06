/**
 * ui/RouteCompare.tsx — 안전 경로 vs 빠른 경로. (와이어프레임 4)
 *
 * ★ "빠른 경로" 는 **폭 위험을 감수한 최단**이지 아무 데나 최단이 아니다.
 *   `buildAdjacency(..., "fastest")` 가 `blocked` 와 필요폭 미만은 여전히
 *   막는다 — 소방차가 못 가는 길은 빠른 것이 아니라 못 가는 길이다.
 *
 * ★ 시간차는 `cost` 차를 속도로 나눈 것이다. `edgeCost` 의 배수가 곧
 *   감속이므로 `cost` 는 실효 거리이고, **별도 시간 모델을 만들지 않는다.**
 *
 * ★ 하단 고지를 지우지 마라. 두 경로 모두 실시간 장애물을 안 본다.
 */
import type { CSSProperties, ReactNode } from "react";
import { C, F, S, fmtDist, fmtDur } from "./tokens";

export interface RouteOption {
  title: string;
  recommended: boolean;
  sec: number;
  lengthM: number;
  uncertainCount: number;
  uncertainM: number;
  minWidthM: number | null;
  requiredM: number;
  /** 상대 경로 대비 시간차(초). 양수면 느리다 */
  deltaSec: number;
  note: string;
}

interface Props {
  safe: RouteOption;
  fast: RouteOption;
  selected: "safe" | "fast";
  onSelect: (k: "safe" | "fast") => void;
  onConfirm: () => void;
  onClose: () => void;
  vehicleKind: string;
  onChangeVehicle?: () => void;
}

export function RouteCompare(p: Props) {
  return (
    <div style={sheet}>
      <div style={bar}>
        <span style={{ fontWeight: 800, fontSize: F.mid }}>경로 비교</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: F.small, opacity: .75 }}>{p.vehicleKind}</span>
        <button onClick={p.onClose} style={x} aria-label="닫기">✕</button>
      </div>

      <div style={{ padding: S.pad }}>
        <div style={{ fontSize: F.mid, fontWeight: 800 }}>추천 경로를 선택하세요</div>
        <div style={{ fontSize: F.small, color: C.panelSub, marginTop: 3 }}>
          도착 시간과 폭 판정 결과를 비교합니다.
        </div>

        <Card o={p.safe} on={p.selected === "safe"}
              onClick={() => p.onSelect("safe")} accent={C.safe} />
        <Card o={p.fast} on={p.selected === "fast"}
              onClick={() => p.onSelect("fast")} accent={C.warn} />

        {/* ★ 두 경로 모두 이것을 안 본다. 지우지 마라. */}
        <div style={note}>
          폭 기준 판정 · 회전 및 높이 미반영 · 실시간 주정차 미반영
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          {p.onChangeVehicle && (
            <button onClick={p.onChangeVehicle} style={ghost}>차량 변경</button>
          )}
          <button onClick={p.onConfirm} style={primary}>이 경로 선택 →</button>
        </div>
      </div>
    </div>
  );
}

function Card({ o, on, onClick, accent }: {
  o: RouteOption; on: boolean; onClick: () => void; accent: string;
}) {
  return (
    <div onClick={onClick} style={{
      marginTop: 12, padding: 14, cursor: "pointer",
      border: `2px solid ${on ? accent : C.panelLine}`,
      borderRadius: S.radius,
      background: on ? `${accent}14` : "transparent",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <i style={{
          width: 14, height: 14, borderRadius: 7, flexShrink: 0,
          border: `2px solid ${on ? accent : C.panelLine}`,
          background: on ? accent : "transparent",
        }} />
        <span style={{ fontSize: F.mid, fontWeight: 800 }}>{o.title}</span>
        <span style={{ flex: 1 }} />
        {o.recommended
          ? <Tag bg={C.safe} fg="#fff">추천</Tag>
          : o.deltaSec < -1
            ? <Tag bg="rgba(245,158,11,.2)" fg={C.warnInk}>
                {fmtDur(-o.deltaSec)} 빠름
              </Tag>
            : null}
      </div>

      <div style={{ fontSize: F.big, fontWeight: 800, marginTop: 6,
                    color: on ? accent : C.panelInk }}>
        {fmtDur(o.sec)} · {fmtDist(o.lengthM)}
      </div>

      <div style={{ marginTop: 8 }}>
        <Row k="확인 필요 구간"
             v={o.uncertainCount
               ? `${o.uncertainCount}개 · ${Math.round(o.uncertainM)}m` : "0개"} />
        <Row k="최소 유효폭"
             v={o.minWidthM != null ? `${o.minWidthM.toFixed(2)}m` : "—"} />
        <Row k="총 안전 여유"
             v={o.minWidthM != null
               ? `${(o.minWidthM - o.requiredM).toFixed(2)}m` : "—"} />
      </div>

      <div style={{
        marginTop: 10, padding: "8px 10px", borderRadius: S.radiusSm,
        background: on ? "rgba(255,255,255,.65)" : "rgba(15,23,42,.05)",
        fontSize: F.small, color: C.panelSub, lineHeight: 1.5,
      }}>{o.note}</div>
    </div>
  );
}

const Tag = ({ bg, fg, children }: {
  bg: string; fg: string; children: ReactNode;
}) => (
  <span style={{ background: bg, color: fg, borderRadius: 999,
                 padding: "3px 10px", fontSize: F.tiny, fontWeight: 700 }}>
    {children}
  </span>
);
const Row = ({ k, v }: { k: string; v: string }) => (
  <div style={{ display: "flex", justifyContent: "space-between",
                fontSize: F.small, padding: "2px 0" }}>
    <span style={{ color: C.panelSub }}>{k}</span>
    <span style={{ fontWeight: 700 }}>{v}</span>
  </div>
);

const sheet: CSSProperties = {
  position: "absolute", zIndex: 7, top: 0, left: 0, bottom: 0, width: 380,
  background: C.panel, color: C.panelInk, overflowY: "auto",
  boxShadow: "8px 0 34px rgba(0,0,0,.45)",
};
const bar: CSSProperties = {
  display: "flex", alignItems: "center", gap: 10,
  background: C.panelInk, color: "#fff", padding: "14px 16px",
};
const note: CSSProperties = {
  marginTop: 12, fontSize: F.tiny, color: C.panelSub, lineHeight: 1.5,
};
const primary: CSSProperties = {
  flex: 1, background: C.link, color: "#fff", border: "none",
  borderRadius: S.radiusSm, padding: "13px 0", fontSize: F.base,
  fontWeight: 800, cursor: "pointer", fontFamily: F.family,
};
const ghost: CSSProperties = {
  background: "transparent", color: C.panelInk,
  border: `1px solid ${C.panelLine}`, borderRadius: S.radiusSm,
  padding: "13px 16px", fontSize: F.base, fontWeight: 700,
  cursor: "pointer", fontFamily: F.family,
};
const x: CSSProperties = {
  background: "none", border: "none", color: "#fff",
  fontSize: 18, cursor: "pointer", padding: 0, lineHeight: 1,
};
