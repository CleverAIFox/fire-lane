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
import { C, F } from "./tokens";
import type { VerdictStyle } from "../domain/types";

interface Props {
  style: Record<string, VerdictStyle>;
  open: boolean;
  onToggle: () => void;
}

/** components/layers.ts 의 색과 같아야 한다. */
const FEATURES = [
  { color: "#ff4d3d", label: "119안전센터" },
  { color: "#ffd54a", label: "CCTV" },
  { color: "#4ad1ff", label: "소화전" },
];

const ORDER = ["clear", "needs_cv", "unknown", "blocked"];

export function Legend({ style, open, onToggle }: Props) {
  return (
    <div style={{ position: "absolute", zIndex: 4, right: 14, bottom: 76 }}>
      <button onClick={onToggle} style={btn}>
        {open ? "범례 ✕" : "범례"}
      </button>
      {open && (
        <div style={panel}>
          <div style={head}>구간 판정</div>
          {ORDER.filter((k) => style[k]).map((k) => (
            <Row key={k} color={style[k].color} label={style[k].label} />
          ))}
          <div style={{ ...head, marginTop: 10 }}>지형지물</div>
          {FEATURES.map((f) => (
            <Row key={f.label} color={f.color} label={f.label} />
          ))}
          {/* ★ 이 한 줄을 지우지 마라. 지도가 보여주는 색이 확정 판정처럼
              읽히는 것을 막는 유일한 장치다. */}
          <div style={note}>도면 기반 1차 판정 · 폭 미검증</div>
        </div>
      )}
    </div>
  );
}

function Row({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8,
                  fontSize: F.small, padding: "2px 0" }}>
      <i style={{ width: 10, height: 10, borderRadius: 5, background: color,
                  border: "1px solid rgba(255,255,255,.25)" }} />
      {label}
    </div>
  );
}

const btn: React.CSSProperties = {
  background: C.dark, border: "1px solid rgba(255,255,255,.14)",
  borderRadius: 10, color: C.darkInk, padding: "7px 12px",
  fontSize: F.small, cursor: "pointer", fontFamily: F.family,
};
const panel: React.CSSProperties = {
  position: "absolute", right: 0, bottom: 38, minWidth: 150,
  background: C.dark, color: C.darkInk,
  border: "1px solid rgba(255,255,255,.1)", borderRadius: 12,
  padding: "12px 14px", backdropFilter: "blur(12px)",
};
const head: React.CSSProperties = {
  fontSize: F.tiny, opacity: .55, marginBottom: 4, fontWeight: 700,
};
const note: React.CSSProperties = {
  marginTop: 10, paddingTop: 8, borderTop: "1px solid rgba(255,255,255,.1)",
  fontSize: F.tiny, opacity: .5, lineHeight: 1.4,
};
