/**
 * ui/RouteCompare.tsx — 경로 비교.  (와이어프레임 02 · 2026-09-21)
 *
 * ★ "빠른 경로" 는 **폭 위험을 감수한 최단**이지 아무 데나 최단이 아니다.
 *   `buildAdjacency(..., "fastest")` 가 `blocked` 와 필요폭 미만은 여전히
 *   막는다 — 소방차가 못 가는 길은 빠른 것이 아니라 못 가는 길이다.
 *
 * ★ 지도에는 **두 경로를 같이** 그린다(파랑·주황). 카드만 보고는 어디가
 *   갈리는지 모른다 — 와이어프레임 02 가 그 뜻으로 두 줄을 겹쳐 그렸다.
 *
 * ★ 하단 고지를 지우지 마라. 두 경로 모두 실시간 장애물을 안 본다.
 *
 * ★ 2026-09-22 (§214-2) 카드를 와이어프레임 모양으로 — 꽉 찬 색 **머리띠**(추천 초록 ·
 *   빠른 노랑)와 머리띠 색의 시간 글자. 안내 문구는 **실제 수로** 쓴다: 추천이 확인 구간을
 *   다 피하면 「우회합니다」, 덜 지나면 「N개 적습니다」, 같으면 같다고.
 */
import type { CSSProperties } from "react";
import { C, F, fmtDur } from "./tokens";
import { Cta, Ghost, Sheet } from "./Sheet";

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
  /** 통행 규칙 요약(`domain/rules.ts ruleSummary`). 없으면 null */
  rules: string | null;
  /** 경로 주변 사정 요약(§216-3) — 과속방지턱 · 단속카메라 · 보호구역 시설. 없으면 null */
  around: string | null;
}

interface Props {
  safe: RouteOption;
  fast: RouteOption | null;
  selected: "safe" | "fast";
  onSelect: (k: "safe" | "fast") => void;
  onConfirm: () => void;
  onChangeVehicle?: () => void;
}

export function RouteCompare(p: Props) {
  return (
    <Sheet wf="02" footer={
      <div style={{ display: "flex", gap: 10 }}>
        {p.onChangeVehicle && <Ghost onClick={p.onChangeVehicle}>차량 변경</Ghost>}
        <div style={{ flex: 1 }}><Cta onClick={p.onConfirm}>안내 시작</Cta></div>
      </div>
    }>
      <div style={{ fontSize: 22, fontWeight: 800 }}>추천 경로를 선택하세요</div>
      <div style={{ fontSize: 13, color: C.panelSub, marginTop: 4 }}>
        도착 시간과 폭 판정 결과를 비교합니다.
      </div>

      <Card o={p.safe} k="safe" on={p.selected === "safe"} onPick={p.onSelect}
            accent={C.toneGreen} chip="추천" title="폭 기준 추천" />
      {p.fast ? (
        <Card o={p.fast} k="fast" on={p.selected === "fast"} onPick={p.onSelect}
              accent={C.toneYellow}
              chip={p.fast.deltaSec < -1 ? `${fmtDur(-p.fast.deltaSec)} 빠름` : "같음"}
              title="빠른 경로" />
      ) : (
        <div style={{ ...note, marginTop: 12 }}>빠른 경로가 폭 기준 추천과 같다 — 비교할 둘째 경로가 없다.</div>
      )}

      <div style={{ fontSize: 11, color: C.panelSub, marginTop: 12, lineHeight: 1.5 }}>
        폭 기준 판정 · 회전 및 높이 미반영 · 실시간 주정차 미반영 ·
        일방통행은 방향을 대부분 몰라 양쪽 다 불리하게 계산
      </div>
    </Sheet>
  );
}

function Card({ o, k, on, onPick, accent, chip, title }: {
  o: RouteOption; k: "safe" | "fast"; on: boolean; onPick: (k: "safe" | "fast") => void;
  accent: string; chip: string; title: string;
}) {
  const margin = o.minWidthM != null ? o.minWidthM - o.requiredM : null;
  const ink = k === "safe" ? C.safeInk : "#c2570c";
  return (
    <button onClick={() => onPick(k)}
            style={{ ...card, borderColor: on ? accent : C.sheetLine,
                     boxShadow: on ? `0 0 0 3px ${accent}66` : "0 1px 3px rgba(0,0,0,.06)" }}>
      <div style={{ ...band, background: on ? accent : `${accent}55` }}>
        <span style={{ ...radio, borderColor: C.panelInk, background: "#fff" }}>
          {on && <span style={radioDot} />}
        </span>
        <b style={{ fontSize: 17 }}>{title}</b>
        <span style={{ flex: 1 }} />
        <span style={chipS}>{chip}</span>
      </div>
      <div style={{ padding: "10px 14px 12px" }}>
        <div style={{ fontSize: 23, fontWeight: 800, color: ink, margin: "2px 0 8px" }}>
          {fmtDur(o.sec)} · {(o.lengthM / 1000).toFixed(1)}km
        </div>
        <Row k="폭 기준 확인 구간"
             v={o.uncertainCount ? `${o.uncertainCount}개 · ${Math.round(o.uncertainM)}m` : "0개"} />
        <Row k="최소 유효폭" v={o.minWidthM != null ? `${o.minWidthM.toFixed(1)}m` : "—"} />
        <Row k="계산상 폭 여유" v={margin != null ? `${margin.toFixed(1)}m` : "—"}
             warn={margin != null && margin < 0.5} />
        <Row k="통행 규칙" v={o.rules ?? "없음"} warn={!!o.rules} />
        {o.around && <Row k="경로 주변" v={o.around} />}
        <div style={{ ...note, background: k === "safe" ? "#f0fdf4" : "#fffbeb" }}>{o.note}</div>
      </div>
    </button>
  );
}

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "3px 0" }}>
      <span style={{ color: C.panelSub }}>{k}</span>
      <span style={{ fontWeight: 800, color: warn ? C.danger : C.panelInk }}>{v}</span>
    </div>
  );
}

const card: CSSProperties = {
  display: "block", width: "100%", textAlign: "left", marginTop: 14, border: "2px solid",
  borderRadius: 16, padding: 0, background: "#fff", cursor: "pointer", overflow: "hidden",
  fontFamily: F.family, color: C.panelInk,
};
const band: CSSProperties = {
  display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", color: C.toneInk,
};
const radio: CSSProperties = {
  width: 18, height: 18, borderRadius: 999, border: "2px solid", display: "grid", placeItems: "center",
};
const radioDot: CSSProperties = { width: 8, height: 8, borderRadius: 999, background: C.panelInk };
const chipS: CSSProperties = {
  borderRadius: 8, padding: "3px 9px", fontSize: 12, fontWeight: 800, color: C.toneInk,
  background: "#fff",
};
const note: CSSProperties = {
  marginTop: 8, borderRadius: 8, padding: "8px 10px", fontSize: 12, color: "#334155", lineHeight: 1.5,
  background: "#f8fafc",
};
