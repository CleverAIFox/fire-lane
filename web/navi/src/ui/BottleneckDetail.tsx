/**
 * ui/BottleneckDetail.tsx — 병목 구간 **자세히**(정차 중에 읽는 것).  (DECISIONS §703 · 와이어프레임 04 의 몸통)
 *
 * ★ 2026-11-12. 종전 병목 패널은 열면 **54줄**이었다(DECISIONS §702) — 운전자가 한 시선 2초로 읽을 양이 아니다. 패널의 기본 화면은 이제
 *   **다음 구간 하나 · 네 줄**(`BottleneckPanel`)이고, 옛 몸통(유효폭 · 요구폭 · 여유폭 · 길이 · 사유 · 판정 근거)은 **여기로 옮겼다 — 지우지 않았다.**
 *   「자세히」 를 눌러야 열린다. 「판정이 무엇을 보고 무엇을 안 보는가」 를 화면에 남기는 장치(아래 「미반영」 줄들)가 이 안에 산다.
 * ★ 이 파일은 `tools/uidrive.py` 의 주행 중 수에 **안 든다** — 정차 중 상세다. 그 분류는 **속도 잠금으로 참이다**(DECISIONS §704): 달리는 중에는 「자세히」 가
 *   안 열리고 열려 있던 것도 닫힌다(`domain/motion.ts` · `BottleneckPanel` 의 `locked`).
 */
import type { CSSProperties, ReactNode } from "react";
import { C, F } from "./tokens";
import { CLEARANCE_SCALE, type SegmentReason } from "./clearanceMeaning";
import { clearanceBand, fmtClearance } from "../domain/clearance";
import { countText } from "../domain/pressure";

export interface BottleneckData {
  /** 위험 종류 — 패널 기본 화면의 둘째 줄(`needs_cv` · `unknown` · `tight`) */
  kind: "needs_cv" | "unknown" | "tight" | "blocked";
  /** 이 구간 **뒤로** 남은 앞서 알릴 구간 수 — 「외 N곳」 */
  more: number;
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
  /** 가장 가까운 CCTV 까지 거리(m). 19m 넘으면 영상판정이 성립 안 한다 */
  cctvDistM: number | null;
  /** 회색이면 왜 회색인가(§215-2). 아니면 null */
  grayReason: string | null;
  /**
   * 왜 그 색인가 · 지금 무엇을 하나(§220). 초록이고 여유가 넉넉하면 null —
   * 취할 조치가 없으면 그 칸을 통째로 뺀다.
   */
  reason: SegmentReason | null;
  /**
   * 그 도로명의 불법주정차 단속 건수(§216-3). 도로 단위 · 위험의 대리값.
   * ★ `null` 은 **모른다**(도로명이 없어 못 셌다)이고 `0` 은 세었고 없다는 뜻이다.
   *   섞으면 모르는 것을 「없음」 으로 말한다 — `countText` 가 가른다.
   */
  park: number | null;
  /** 그 도로명의 불법주정차 단속 **카메라 지점** 수. `park` 와 같은 null · 0 규약 */
  ecam: number | null;
}


export function BottleneckDetail(d: BottleneckData) {
  const margin = d.widthM != null && d.kind !== "unknown" ? d.widthM - d.requiredM : null;
  const band = CLEARANCE_SCALE[clearanceBand(margin)];
  const cctvOk = d.cctvDistM != null && d.cctvDistM <= 19;
  return (
    <div style={{ fontFamily: F.family }}>
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
        {/* ★ `d.park ? … : "없음"` 이었다. 그러면 **모르는 것이 「없음」 으로 찍힌다** —
            0 은 세었고 없는 것이고 `null` 은 안 세어진 것이다. `countText` 가 그것을 가른다. */}
        <Line k="불법주정차 단속 이력" v={countText(d.park, "건")} />
        <Line k="단속 카메라" v={countText(d.ecam, "지점")} />
        <Line k="회전 · 높이" v="미반영" />
      </Section>

      <Section title="판정 근거">
        <Line k="측정 신뢰도" v={d.coverage != null ? `${Math.round(d.coverage * 100)}%` : "—"} blue />
        <Line k="폭 표본" v={d.samples != null ? `${d.samples}개` : "—"}
              note={d.samples === 1 ? "표본 하나 — 통과 확정 보류" : undefined} />
        <Line k="가까운 CCTV" v={d.cctvDistM != null ? `${Math.round(d.cctvDistM)}m` : "—"}
              note={cctvOk ? "영상 판정 가능 거리" : "19m 밖 — 영상 판정 불가"} />
        <Line k="판정" v={d.verdictLabel} color={d.verdictColor} />
        {d.grayReason && (
          <div style={{ fontSize: 11, color: C.panelInk, padding: "6px 0", lineHeight: 1.5 }}>
            <b>회색 사유</b> — {d.grayReason}
          </div>
        )}
      </Section>
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

const grid: CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12,
};
const tile: CSSProperties = { background: "#f8fafc", borderRadius: 10, padding: "10px 12px" };
const why: CSSProperties = {
  marginTop: 10, border: "1.5px solid", borderRadius: 10, padding: "9px 11px",
  fontSize: 12, lineHeight: 1.5, background: "#f8fafc",
};
