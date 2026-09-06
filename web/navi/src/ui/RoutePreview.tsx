/**
 * ui/RoutePreview.tsx — 목적지 확인과 안내 시작. (와이어프레임 흐름)
 *
 * ── 왜 필요한가 ─────────────────────────────────────────────────
 * 2026-09-06. 지도를 두 번 클릭하면 **즉시 안내가 시작됐다.** 상용 내비는
 * 그렇게 하지 않는다 — 목적지를 고르면 경로와 예상 시간을 보여주고
 * 사용자가 **시작을 누른다.**
 *
 * 와이어프레임에도 그 자리가 있다 — 화면 4 의 `이 경로 선택 →`,
 * 화면 7 의 `이 차량으로 경로 계산 →`. 컴포넌트만 만들고 흐름으로
 * 엮지 않았던 것이 내 누락이다.
 *
 * ★ **출발지는 현위치다.** 사용자가 고르지 않는다. GPS 가 없으면
 *   지도를 눌러 대체하는데, 그것은 개발·시연용 대체지 기능이 아니다.
 *
 * ★ 회색 구간 수를 **시작 전에** 보여준다. 목적지의 49% 가 회색에
 *   접해 있으므로 출발하기 전에 아는 것이 핵심이다.
 */
import type { CSSProperties } from "react";
import { C, F, S, fmtDist, fmtDur } from "./tokens";

export interface RoutePreviewData {
  destLabel: string;
  destVerdictLabel?: string;
  destVerdictColor?: string;
  vehicleKind: string;

  lengthM: number;
  sec: number;
  etaText: string;
  uncertainCount: number;
  uncertainM: number;
  minWidthM: number | null;
  requiredM: number;

  onStart: () => void;
  onCompare?: () => void;
  onChangeVehicle?: () => void;
  onCancel: () => void;
}

export function RoutePreview(d: RoutePreviewData) {
  const margin = d.minWidthM != null ? d.minWidthM - d.requiredM : null;
  const risky = margin != null && margin < 0.5;

  return (
    <div style={sheet}>
      <div style={bar}>
        <span style={{ fontWeight: 800, fontSize: F.mid }}>경로 확인</span>
        <span style={{ flex: 1 }} />
        <button onClick={d.onCancel} style={x} aria-label="취소">✕</button>
      </div>

      <div style={{ padding: S.pad }}>
        <div style={{ fontSize: F.tiny, color: C.panelSub }}>목적지</div>
        <div style={{ fontSize: F.big, fontWeight: 800, marginTop: 2 }}>
          {d.destLabel}
        </div>
        {d.destVerdictLabel && (
          <div style={{ fontSize: F.small, fontWeight: 700, marginTop: 4,
                        color: d.destVerdictColor }}>
            목적지 앞 도로 · {d.destVerdictLabel}
          </div>
        )}

        <div style={row}>
          <Big k="예상 도착" v={d.etaText} />
          <Big k="거리" v={fmtDist(d.lengthM)} />
          <Big k="소요" v={fmtDur(d.sec)} />
        </div>

        <div style={{ ...box, borderColor: d.uncertainCount ? C.warn : C.safe }}>
          <div style={{ fontSize: F.base, fontWeight: 800,
                        color: d.uncertainCount ? C.warnInk : C.safeInk }}>
            {d.uncertainCount
              ? `확인 필요 구간 ${d.uncertainCount}개 · ${Math.round(d.uncertainM)}m`
              : "확인 필요 구간 없음"}
          </div>
          <Line k="최소 유효 도로 폭"
                v={d.minWidthM != null ? `${d.minWidthM.toFixed(2)}m` : "—"} />
          <Line k="차량 요구 폭" v={`${d.requiredM.toFixed(1)}m`} />
          <Line k="계산상 최소 여유"
                v={margin != null ? `${margin.toFixed(2)}m` : "—"} warn={risky} />
        </div>

        {/* ★ 출발 전에 알린다. 지우지 마라. */}
        <div style={note}>
          실시간 주정차 · 공사 · 이동 장애물은 반영되지 않았습니다.<br />
          폭은 도면 기반 미검증 값이며, 회전 및 높이는 판정하지 않습니다.
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          {d.onChangeVehicle && (
            <button onClick={d.onChangeVehicle} style={ghost}>
              {d.vehicleKind}
            </button>
          )}
          {d.onCompare && (
            <button onClick={d.onCompare} style={ghost}>경로 비교</button>
          )}
        </div>
        <button onClick={d.onStart} style={primary}>안내 시작 →</button>
      </div>
    </div>
  );
}

function Big({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: F.tiny, color: C.panelSub }}>{k}</div>
      <div style={{ fontSize: F.mid, fontWeight: 800, marginTop: 2 }}>{v}</div>
    </div>
  );
}
function Line({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between",
                  fontSize: F.small, padding: "2px 0", marginTop: 2 }}>
      <span style={{ color: C.panelSub }}>{k}</span>
      <span style={{ fontWeight: 700, color: warn ? C.danger : C.panelInk }}>{v}</span>
    </div>
  );
}

const sheet: CSSProperties = {
  position: "absolute", zIndex: 7, top: 0, left: 0, bottom: 0, width: 370,
  background: C.panel, color: C.panelInk, overflowY: "auto",
  boxShadow: "8px 0 34px rgba(0,0,0,.45)",
};
const bar: CSSProperties = {
  display: "flex", alignItems: "center", gap: 10,
  background: C.panelInk, color: "#fff", padding: "14px 16px",
};
const row: CSSProperties = {
  display: "flex", gap: 12, marginTop: 14, paddingTop: 12,
  borderTop: `1px solid ${C.panelLine}`,
};
const box: CSSProperties = {
  marginTop: 14, padding: "12px 14px",
  border: `1.5px solid ${C.panelLine}`, borderRadius: S.radiusSm,
};
const note: CSSProperties = {
  marginTop: 12, fontSize: F.tiny, color: C.panelSub, lineHeight: 1.6,
};
const primary: CSSProperties = {
  marginTop: 8, width: "100%", background: C.link, color: "#fff",
  border: "none", borderRadius: S.radiusSm, padding: "15px 0",
  fontSize: F.mid, fontWeight: 800, cursor: "pointer", fontFamily: F.family,
};
const ghost: CSSProperties = {
  flex: 1, background: "transparent", color: C.panelInk,
  border: `1px solid ${C.panelLine}`, borderRadius: S.radiusSm,
  padding: "11px 12px", fontSize: F.base, fontWeight: 700,
  cursor: "pointer", fontFamily: F.family,
};
const x: CSSProperties = {
  background: "none", border: "none", color: "#fff",
  fontSize: 18, cursor: "pointer", padding: 0, lineHeight: 1,
};
