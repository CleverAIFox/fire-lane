/**
 * ui/SearchPanel.tsx — 목적지 검색. (와이어프레임 · POI 2,077)
 *
 * ★ 결과를 고르면 호출부가 **도로에 스냅한 뒤** 목적지로 쓴다. 상가
 *   좌표를 그대로 쓰면 안 된다 — 상가→도로 거리가 p90 70.9m 다.
 *
 * ★ 판정색을 여기서 정하지 않는다. 호출부가 스냅 결과의 verdict 를
 *   넘겨주면 그 색으로 점을 찍는다. 목적지의 절반(49%)이 회색 구간에
 *   접해 있으므로 **고르기 전에 보이는 것**이 중요하다.
 */
import { useState, type CSSProperties } from "react";
import { C, F, S } from "./tokens";
import type { PoiHit } from "../domain/search";

interface Props {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  onQuery: (q: string) => PoiHit[];
  onPick: (hit: PoiHit) => void;
  /** 결과별 판정색·라벨. 호출부가 스냅해서 채운다 */
  verdictOf?: (hit: PoiHit) => { color: string; label: string } | null;
}

export function SearchPanel(p: Props) {
  const [q, setQ] = useState("");
  const hits = p.open && q ? p.onQuery(q) : [];

  if (!p.open) {
    return (
      <button onClick={p.onOpen} style={fab} aria-label="목적지 검색">
        🔍 목적지 검색
      </button>
    );
  }

  return (
    <div style={sheet}>
      <div style={bar}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
               placeholder="상가 · 업종 · 주소" style={input} />
        <button onClick={() => { setQ(""); p.onClose(); }} style={x}>✕</button>
      </div>

      <div style={{ overflowY: "auto", flex: 1 }}>
        {q && hits.length === 0 && (
          <div style={empty}>검색 결과가 없다</div>
        )}
        {hits.map((h, i) => {
          const v = p.verdictOf?.(h) ?? null;
          return (
            <div key={`${h.name}-${i}`} onClick={() => p.onPick(h)} style={row}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: F.base, fontWeight: 700 }}>{h.name}</div>
                <div style={{ fontSize: F.tiny, color: C.panelSub,
                              overflow: "hidden", textOverflow: "ellipsis",
                              whiteSpace: "nowrap" }}>
                  {h.sub} · {h.addr}
                </div>
              </div>
              {v && (
                <span style={{ display: "flex", alignItems: "center", gap: 5,
                               fontSize: F.tiny, color: v.color, flexShrink: 0 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 4,
                              background: v.color }} />
                  {v.label}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* ★ 목적지의 49% 가 회색 구간에 접한다. 고르기 전에 알린다. */}
      <div style={note}>
        목적지 앞 도로의 판정을 함께 표시합니다.<br />
        회색은 폭을 검증하지 못한 구간입니다.
      </div>
    </div>
  );
}

const fab: CSSProperties = {
  position: "absolute", zIndex: 5, top: 110, left: 14,
  background: C.panel, color: C.panelInk,
  border: `1px solid ${C.panelLine}`, borderRadius: 999,
  padding: "11px 18px", fontSize: F.base, fontWeight: 700,
  cursor: "pointer", fontFamily: F.family,
  boxShadow: "0 6px 20px rgba(0,0,0,.3)",
};
const sheet: CSSProperties = {
  position: "absolute", zIndex: 7, top: 0, left: 0, bottom: 0, width: 360,
  background: C.panel, color: C.panelInk,
  display: "flex", flexDirection: "column",
  boxShadow: "8px 0 34px rgba(0,0,0,.45)",
};
const bar: CSSProperties = {
  display: "flex", alignItems: "center", gap: 8,
  background: C.panelInk, padding: "12px 14px",
};
const input: CSSProperties = {
  flex: 1, background: "rgba(255,255,255,.12)", border: "none",
  borderRadius: S.radiusSm, color: "#fff", padding: "10px 12px",
  fontSize: F.base, fontFamily: F.family, outline: "none",
};
const row: CSSProperties = {
  display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
  padding: "11px 14px", borderBottom: `1px solid ${C.panelLine}`,
};
const empty: CSSProperties = {
  padding: 24, textAlign: "center", color: C.panelSub, fontSize: F.base,
};
const note: CSSProperties = {
  padding: "10px 14px", borderTop: `1px solid ${C.panelLine}`,
  fontSize: F.tiny, color: C.panelSub, lineHeight: 1.6,
};
const x: CSSProperties = {
  background: "none", border: "none", color: "#fff",
  fontSize: 18, cursor: "pointer", padding: 0, lineHeight: 1,
};
