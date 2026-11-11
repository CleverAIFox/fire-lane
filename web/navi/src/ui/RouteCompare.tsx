/**
 * ui/RouteCompare.tsx — **경로 설명.** 고르는 판이 아니다.  (DECISIONS §400)
 *
 * ★ 2026-10-05. 종전 이름은 「경로 비교」였고 기사가 둘 중 하나를 **골랐다.**
 *   사람이 그 전제를 잘랐다 — 「내비가 스스로 고를 수 있는건 없다」. 경로는
 *   관제가 정해서 지령에 실어 보내고, 이 판은 **왜 이 길인지**를 보인다.
 *   둘을 나란히 그리는 것은 비교가 아니라 설명이다. `onSelect` 를 지웠다.
 *
 * ★ 「폭 기준」을 **안전**으로 고쳐 부른다. 그래서 하단 고지가 더 중요해졌다 —
 *   안 지우고 **「폭으로만 본 안전이다」**로 다시 적었다. 이름이 세질수록
 *   한계를 더 적는다.
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
 *
 * ── ★ 2026-09-23 (멘토링 §219 → DECISIONS §220) 두 경로가 **같을 때** ────────────
 * 종전엔 같으면 둘째 카드를 숨기고 「비교할 둘째 경로가 없다」 한 줄을 냈다. 읽는 사람은
 * 계산이 덜 됐다고 읽는다 — 실은 **가장 좋은 답**이다. 같으면 카드 하나를
 * 「안전하면서 빠른 추천 경로」 로 낸다. 같은 줄을 두 번 그리지 않는다.
 *
 * 다르면 둘을 그대로 두되 **어디가 다른지**를 수로 보인다 — 길이 · 통행 불가 경유 ·
 * 규칙 경고 수. 세 줄 다 두 경로에 같은 자리에 있어서 눈으로 뺄 수 있다.
 */
import { useState, type CSSProperties } from "react";
import { C, F, fmtDur } from "./tokens";
import { Cta, Sheet } from "./Sheet";
import { clearanceBand, fmtClearance } from "../domain/clearance";
import { SAME_ROUTE_TITLE } from "../domain/compare";
import { CLEARANCE_SCALE } from "./clearanceMeaning";

export interface RouteOption {
  title: string;
  recommended: boolean;
  sec: number;
  lengthM: number;
  uncertainCount: number;
  /** 그중 폭 모름(`unknown`) 구간 수 — 최소폭이 이 구간을 못 본다 */
  unknownCount: number;
  uncertainM: number;
  minWidthM: number | null;
  requiredM: number;
  /** 지나는 통행 불가 구간 수(§220). A* 가 막으므로 보통 0 이고, 그 0 을 보인다 */
  blockedCount: number;
  /** 통행 규칙 경고 수(§220) — 역주행 · 방향 미확인 · 회전 금지 · 급회전 */
  ruleCount: number;
  /** 상대 경로 대비 시간차(초). 양수면 느리다 */
  deltaSec: number;
  note: string;
  /** 통행 규칙 요약(`domain/rules.ts ruleSummary`). 없으면 null */
  rules: string | null;
  /** 경로 **위** 경고(PLAN #78 ③) — 어느 구간이 어떻게 위험한지. 줄은 `RISK_LINES_MAX` 까지 · 넘치면 `more` 수만 */
  risks: { lines: string[]; more: number };
  /** 경로 주변 사정 요약(§216-3) — 과속방지턱 · 단속카메라 · 보호구역 시설. 없으면 null */
  around: string | null;
}

interface Props {
  safe: RouteOption;
  fast: RouteOption | null;
  /**
   * 빠른 경로가 **안전 경로와 같은 구간 순서**인가(`domain/compare.ts::sameRoute`).
   * true 면 카드 하나를 「안전하면서 빠른 추천 경로」 로 낸다. `fast` 가 없으면서
   * 이것이 false 면 빠른 경로 자체를 못 낸 것이다 — 다른 말을 한다.
   */
  same: boolean;
  /** 관제가 정한 경로. **기사는 못 바꾼다.** */
  chosen: "safe" | "fast";
  /** 그 값이 지령에서 왔는가. 거짓이면 기본값이고 화면이 그렇게 적는다. */
  fromOrder: boolean;
  onConfirm: () => void;
}

export function RouteBrief(p: Props) {
  const [open, setOpen] = useState(false);
  const two = !p.same && p.fast != null;
  const opts: { o: RouteOption; on: boolean; accent: string; chip: string; title: string }[] = p.same
    ? [{ o: p.safe, on: true, accent: C.toneGreen, chip: "안전 · 최속 동일", title: SAME_ROUTE_TITLE }]
    : [
        { o: p.safe, on: p.chosen === "safe", accent: C.toneGreen,
          chip: p.chosen === "safe" ? "지령" : "안 간다", title: "안전 경로" },
        ...(p.fast ? [{ o: p.fast, on: p.chosen === "fast", accent: C.toneYellow,
          chip: p.chosen === "fast" ? "지령" : "안 간다", title: "빠른 경로" }] : []),
      ];
  return (
    <Sheet wf="02" footer={<Cta onClick={p.onConfirm}>안내 시작</Cta>}>
      <div style={{ fontSize: 22, fontWeight: 800 }}>
        {p.same ? SAME_ROUTE_TITLE : p.chosen === "safe" ? "안전 경로로 간다" : "빠른 경로로 간다"}
      </div>
      {!p.same && (
        <div style={{ fontSize: 13, color: C.panelSub, marginTop: 4 }}>
          {p.fromOrder ? "관제가 정한 경로다." : "경로 지정이 없어 안전으로 간다."}
        </div>
      )}

      {/* ★ 두 경로는 **나란히** — 고르는 데 필요한 것은 수의 비교다(PLAN #73 · 진술 4 「흐르는 글자를 두지 않는다」 ·
          진술 7 「관련 있는 것만 뜬다」). 카드마다 네 줄이고 나머지는 아래 「자세히」 로 접는다 */}
      <div style={{ display: "grid", gridTemplateColumns: two ? "1fr 1fr" : "1fr", gap: 10, marginTop: 14 }}>
        {opts.map((x) => <Col key={x.title} {...x} />)}
      </div>
      {!two && !p.same && (
        <div style={{ ...note, marginTop: 12 }}>둘째 경로 없음 — 안전 경로로 안내한다.</div>
      )}
      {two && <DeltaLine safe={p.safe} fast={p.fast!} />}

      <button type="button" onClick={() => setOpen((x) => !x)} aria-expanded={open} style={moreBtn}>
        {open ? "접기 ▴" : "자세히 ▾"}
      </button>
      {open && opts.map((x) => <Details key={x.title} o={x.o} title={opts.length > 1 ? x.title : null} />)}

      <div style={{ fontSize: 11, color: C.panelSub, marginTop: 12, lineHeight: 1.5 }}>
        <b>폭으로만 본 안전이다</b>
      </div>
    </Sheet>
  );
}

/** 빠른 경로가 안전 경로보다 얼마나 다른가 — 문장이 아니라 두 수(시간 · 확인 필요 곳수) */
function DeltaLine({ safe, fast }: { safe: RouteOption; fast: RouteOption }) {
  const dt = Math.round(fast.sec - safe.sec);
  const dn = fast.uncertainCount - safe.uncertainCount;
  if (dt === 0 && dn === 0) return null;
  const time = dt === 0 ? "시간 같음" : dt < 0 ? `${fmtDur(-dt)} 빠름` : `${fmtDur(dt)} 느림`;
  return (
    <div style={{ marginTop: 10, fontSize: 14, fontWeight: 800, color: C.panelInk, textAlign: "center" }}>
      빠른 경로 {time} · 확인 필요 {dn > 0 ? "+" : ""}{dn}곳
    </div>
  );
}

/**
 * 경로 한 장 — **네 줄.** 제목 · 시간 거리 · 최소폭 여유 · 확인 필요. 통행 불가는 0 이 아닐 때만 한 줄 더.
 * **누를 수 없다**(§400). 규칙 경고 · 구간 목록 · 경로 주변 · 설명은 `Details`(접힘)로 갔다.
 *
 * ★ 최소폭은 폭을 **아는** 구간의 최소다. 폭 모름 구간이 있으면 그 수가 전부를 말하지 않으므로 그 사실을 같은 줄에 단다.
 */
function Col({ o, on, accent, chip, title }: {
  o: RouteOption; on: boolean; accent: string; chip: string; title: string;
}) {
  const margin = o.minWidthM != null ? o.minWidthM - o.requiredM : null;
  const b = CLEARANCE_SCALE[clearanceBand(margin)];
  return (
    <div style={{ ...card, marginTop: 0, cursor: "default", borderColor: on ? accent : C.sheetLine,
                  opacity: on ? 1 : .8,
                  boxShadow: on ? `0 0 0 3px ${accent}66` : "0 1px 3px rgba(0,0,0,.06)" }}>
      <div style={{ ...band, background: on ? accent : `${accent}55`, flexWrap: "wrap", gap: 4 }}>
        <b style={{ fontSize: 15 }}>{title}</b>
        <span style={{ flex: 1 }} />
        <span style={chipS}>{chip}</span>
      </div>
      <div style={{ padding: "8px 10px 10px" }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: on ? C.safeInk : "#c2570c", marginBottom: 6 }}>
          {fmtDur(o.sec)} · {(o.lengthM / 1000).toFixed(1)}km
        </div>
        <Row k="최소폭" v={o.minWidthM != null ? `${o.minWidthM.toFixed(1)}m` : "—"} />
        <Row k="여유" v={fmtClearance(margin)} color={b.color} />
        {o.unknownCount > 0 && <div style={{ fontSize: 11, color: C.panelSub }}>폭 모름 {o.unknownCount}곳은 뺀 수</div>}
        <Row k="확인 필요" v={`${o.uncertainCount}곳`} warn={o.uncertainCount > 0} />
        {o.blockedCount > 0 && <Row k="통행 불가" v={`${o.blockedCount}곳`} warn />}
      </div>
    </div>
  );
}

/** 접힌 것 — 규칙 경고 · 경로 위 구간 목록 · 경로 주변 · 설명. 지우지 않고 탭하면 펼친다 */
export function Details({ o, title }: { o: RouteOption; title: string | null }) {
  return (
    <div style={{ marginTop: 10, fontSize: 13 }}>
      {title && <div style={{ fontWeight: 800, marginBottom: 2 }}>{title}</div>}
      {(o.ruleCount > 0 || o.rules) && <Row k="규칙 경고" v={o.rules ?? `${o.ruleCount}건`} warn />}
      {o.around && <Row k="경로 주변" v={o.around} />}
      {o.risks.lines.length > 0 && (
        <div style={riskBox}>
          {o.risks.lines.map((l) => <div key={l}>{l}</div>)}
          {o.risks.more > 0 && <div style={{ color: C.panelSub }}>외 {o.risks.more}곳</div>}
        </div>
      )}
      <div style={note}>{o.note}</div>
    </div>
  );
}

function Row({ k, v, warn, color }: { k: string; v: string; warn?: boolean; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 6, fontSize: 13, padding: "2px 0" }}>
      <span style={{ color: C.panelSub }}>{k}</span>
      <span style={{ fontWeight: 800, color: color ?? (warn ? C.danger : C.panelInk) }}>{v}</span>
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
const chipS: CSSProperties = {
  borderRadius: 8, padding: "3px 9px", fontSize: 12, fontWeight: 800, color: C.toneInk,
  background: "#fff",
};
const riskBox: CSSProperties = {
  marginTop: 6, borderRadius: 8, padding: "6px 10px", fontSize: 12, lineHeight: 1.5,
  color: "#7c2d12", background: "#fff7ed", border: "1px solid #fed7aa",
};
const moreBtn: CSSProperties = {
  display: "block", width: "100%", marginTop: 12, padding: "10px 0", border: `1px solid ${C.sheetLine}`,
  borderRadius: 10, background: "#fff", fontSize: 14, fontWeight: 800, color: C.panelInk, cursor: "pointer",
  fontFamily: F.family,
};
const note: CSSProperties = {
  marginTop: 8, borderRadius: 8, padding: "8px 10px", fontSize: 12, color: "#334155", lineHeight: 1.5,
  background: "#f8fafc",
};
