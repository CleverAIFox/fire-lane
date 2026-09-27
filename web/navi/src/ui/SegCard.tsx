/**
 * ui/SegCard.tsx — 관제가 도로 하나를 눌렀을 때 뜨는 구간 카드.
 *
 * ★ 2026-09-23 (DECISIONS §220). 두 가지가 들어왔다 — **여유폭을 수로**(색과 같은 4단
 *   색을 글자에 입힌다) 와 **사유 한 줄**. 사유는 빨강만이 아니라 판정마다 낸다.
 *   초록이고 여유가 넉넉하면 `segmentReason` 이 null 을 내고 그 칸이 통째로 빠진다 —
 *   관제사가 그것으로 취할 조치가 없으면 화면에서도 뺀다.
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `OpsApp.tsx` 가 744줄로 상한(600)을 넘었다. 이 카드는 구간 **하나**만
 *   보고 그리는 조각이라 관제 배선을 하나도 모른다 — 떼도 잃는 것이 없다.
 *
 * ★ 판정 색표를 `Bundle["graph"]["style"]` 로 받던 것을 `Record<string, VerdictStyle>`
 *   로 적는다. **같은 타입**이지만(`domain/types.ts` 가 `NaviGraph.style` 을 그렇게
 *   선언한다) `ui/` 가 `infra/` 를 아는 것은 계층 위반이다 — 타입만 넘나드는 것도
 *   위반이고, 그것이 `test/layering.test.ts` 가 세워진 이유다(§244).
 *
 * ★ 이름은 `SegCard` 그대로다. 갈랐다는 것을 이름으로 알리려고 부르는 쪽 코드를
 *   고치면, 옮긴 것과 바꾼 것이 한 배치에 섞여 되돌릴 때 무엇이 무엇인지 모른다.
 *
 * IN    구간 하나 · 판정 색표 · 차 제원 · 도달 가능 여부 · 차 이름
 * OUT   카드 한 장
 * 밖    구간을 고르지 않는다. 고르는 것은 지도와 `OpsApp.tsx` 다.
 */
import { edgeClearance, fmtClearance } from "../domain/clearance";
import type { GraphEdge, VehicleSpec, VerdictStyle } from "../domain/types";
import { CLEARANCE_SCALE, segmentReason } from "./clearanceMeaning";
import { grayReason, VERDICT_MEANING } from "./verdictMeaning";
import { countText } from "../domain/pressure";
import { Row } from "./OpsBits";
import { D, dot, secBox, whyBox } from "./opsTheme";

export function SegCard({ e, style, spec, reachable, vehicle, onClose }: {
  e: GraphEdge; style: Record<string, VerdictStyle>; spec: VehicleSpec; reachable: boolean | null;
  vehicle: string; onClose: () => void;
}) {
  const s = style[e.verdict];
  const c = edgeClearance(e, spec);
  const why = segmentReason(e, spec);
  const cctvOk = e.cctv_dist_m != null && e.cctv_dist_m <= 25;
  const gray = grayReason(e);
  return (
    <div style={{ ...secBox }}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <b style={{ fontSize: 15, flex: 1 }}>{e.seg_label ?? e.road_name ?? e.seg_uid}</b>
        <button onClick={onClose} style={{ border: "none", background: "none", fontSize: 18, cursor: "pointer", color: D.sub }}>✕</button>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
        <i style={{ ...dot, background: s?.color }} />
        <b>{s?.label ?? e.verdict}</b>
        <span style={{ fontSize: 11, color: D.sub }}>{VERDICT_MEANING[e.verdict]}</span>
      </div>
      {why && (
        <div style={{ ...whyBox, borderColor: CLEARANCE_SCALE[c.band].color }}>
          <b style={{ color: CLEARANCE_SCALE[c.band].color }}>{why.head}</b>
          <div style={{ color: D.ink, marginTop: 2 }}>{why.detail}</div>
          {why.action && <div style={{ color: D.sub, marginTop: 2 }}>→ {why.action}</div>}
        </div>
      )}
      <Row k="최소 · 최대 유효폭" v={`${e.width_min_m?.toFixed(1) ?? "—"} · ${e.width_max_m?.toFixed(1) ?? "—"}m`} />
      <Row k={`${vehicle} 요구폭 (전폭 + 여유)`} v={`${c.requiredM.toFixed(1)}m`} />
      {/* ★ 멘토링 §219 — 「여유폭을 색과 수로」. 이 한 줄이 그 수다 */}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "4px 0",
                    borderBottom: `1px solid ${D.line}` }}>
        <span style={{ color: D.sub }}>여유폭 = 최소 유효폭 − 요구폭</span>
        <b style={{ color: CLEARANCE_SCALE[c.band].color, textAlign: "right" }}>
          {fmtClearance(c.m)} <span style={{ fontWeight: 600, color: D.sub }}>{CLEARANCE_SCALE[c.band].short}</span>
        </b>
      </div>
      <Row k="측정 신뢰도 · 폭 표본" v={`${e.width_cov != null ? Math.round(e.width_cov * 100) + "%" : "—"} · ${e.n_sample ?? "—"}개`} />
      <Row k="가까운 CCTV" v={e.cctv_dist_m != null ? `${Math.round(e.cctv_dist_m)}m ${cctvOk ? "(영상판정 가능)" : "(25m 밖)"}` : "—"} />
      {gray && (
        <div style={{ fontSize: 12, background: "#0f172a", border: `1px solid ${D.line}`, borderRadius: 8, padding: "7px 9px", marginTop: 6, lineHeight: 1.5 }}>
          <b>회색 사유 — {gray.short}</b><br />{gray.long}
        </div>
      )}
      {/* ★ 「없음」 으로 접지 않는다 — `null`(도로명이 없어 못 셌다)과 0(세었고 없다)이 다르다.
          `warn` 은 모름에 안 건다: 증거가 없는 것을 위험으로도 안전으로도 읽지 않는다. */}
      <Row k="불법주정차 단속(도로명 · 3년)" v={countText(e.park, "건")} warn={(e.park ?? 0) >= 200} />
      <Row k="단속 카메라(도로명)" v={countText(e.ecam, "지점")} />
      {e.ow ? (
        <Row k="일방통행" v={e.ow === 2 ? "방향 미확인" : "방향 확정"} warn={e.ow === 2} />
      ) : null}
      <Row k="길이" v={e.length_m != null ? `${Math.round(e.length_m)}m` : "—"} />
      <Row k="선택 센터에서" v={reachable == null ? "—" : reachable ? "도달 가능" : "도달 불가"} warn={reachable === false} />
      <div style={{ fontSize: 11, color: D.sub, marginTop: 8, lineHeight: 1.5 }}>
        폭은 도면 기반 미검증 값이다. 실시간 주정차 · 공사 · 회전 · 높이는 반영하지 않는다.
      </div>
    </div>
  );
}
