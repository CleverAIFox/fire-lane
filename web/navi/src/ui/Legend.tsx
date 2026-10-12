/**
 * ui/Legend.tsx — 지도 범례.
 *
 * ★ 판정 4색을 여기서 정의하지 않는다. `navi_graph.json.style` 이
 *   주는 것을 그대로 쓴다. 정본은 `web/config.js` 하나다(MASTER §10-2).
 *
 * ★ 지형지물 색은 `components/layers.ts` 와 손으로 맞춰야 한다.
 *   같은 값을 두 곳에 적는 것이라 위험하지만, 레이어 스타일 표현식에서
 *   색만 뽑아오는 것이 더 부서지기 쉽다. **한쪽을 고치면 다른 쪽도
 *   고쳐라** — 이 주석이 그 강제자다.
 */
import { C, F, S } from "./tokens";
import type { VerdictStyle } from "../domain/types";
import { VERDICT_ORDER } from "./verdictMeaning";

interface Props {
  style: Record<string, VerdictStyle>;
  open: boolean;
  onToggle: () => void;
}

/** components/layers.ts 의 색과 같아야 한다. (2026-09-21 주간 테마로 바꿈) */
const FEATURES = [
  { color: C.station, label: "119안전센터" },
  // ★ 2026-10-09 (§444 · #148). 지점 핀 — **판정색을 안 쓴다.** 흰 고리이고
  //   경로에 안 붙는다. 4색 중 하나를 쓰면 「통행 가능한 지점」으로 읽힌다.
  { color: "#e2e8f0", label: "지점 (경로 밖)" },
  { color: "#facc15", label: "CCTV" },
  { color: "#ef4444", label: "소화전" },
];

/** 경로 어휘 — layers.ts::routeLayers 와 같아야 한다 */
const ROUTE = [
  { color: C.route, label: "안내 경로" },
  { color: C.routeUnverified, label: "CCTV 미검증 골목" },
  { color: C.routeBottleneck, label: "병목 · 확인 필요" },
  { color: C.routeAlt, label: "빠른 경로 (비교)" },
];


export function Legend({ style, open }: Props) {
  if (!open) return null;
  return (
    <div style={{ ...panel, position: "absolute", zIndex: 5, left: 86, top: S.guideBarH + 90 }}>
      <div style={head}>경로</div>
      {ROUTE.map((f) => (
        <Row key={f.label} label={f.label}
             color={f.label.startsWith("병목") ? (style.needs_cv?.color ?? f.color) : f.color} />
      ))}
      <div style={{ ...head, marginTop: 10 }}>구간 판정 (도로 음영)</div>
      {VERDICT_ORDER.filter((k) => style[k]).map((k) => (
        <Row key={k} color={style[k].color} label={style[k].label} />
      ))}
      <div style={{ ...head, marginTop: 10 }}>지형지물</div>
      {FEATURES.map((f) => <Row key={f.label} color={f.color} label={f.label} />)}
      {/* ★ 2026-10-09 (DECISIONS §445 · PLAN #143 닫힘). **설명이 화면에 없다.**
          §441 이 여기 한 줄을 「읽는 법」 시트로 옮겼고, 행이 그 시트 자체를
          걷으라고 했다 — 「매뉴얼이 필요한 GUI 는 못 만든 GUI 다」. 관제는
          **탐색 과제**(소화전 · CCTV · 1,281구간)라 읽을 거리가 탐색 시간을
          늘린다. 범례는 남는다 — 눈을 살짝 옮겨 찾는 **참조**이고 설명이 아니다.
          한계(무엇을 안 보는가)의 집은 `MASTER §15-4` 다. */}
    </div>
  );
}

function Row({ color, label, sub }: { color: string; label: string; sub?: string }) {
  return (
    <div style={{ display: "flex", alignItems: sub ? "flex-start" : "center", gap: 8,
                  fontSize: F.small, padding: "2px 0" }}>
      <i style={{ width: 10, height: 10, borderRadius: 5, background: color, marginTop: sub ? 3 : 0,
                  border: "1px solid rgba(255,255,255,.25)", flex: "0 0 auto" }} />
      <span>
        {label}
        {sub && <span style={{ display: "block", fontSize: F.tiny, opacity: .6 }}>{sub}</span>}
      </span>
    </div>
  );
}

const panel: React.CSSProperties = {
  minWidth: 170,
  background: C.dark, color: C.darkInk,
  border: "1px solid rgba(255,255,255,.1)", borderRadius: 12,
  padding: "12px 14px", backdropFilter: "blur(12px)",
};
const head: React.CSSProperties = {
  fontSize: F.tiny, opacity: .55, marginBottom: 4, fontWeight: 700,
};
