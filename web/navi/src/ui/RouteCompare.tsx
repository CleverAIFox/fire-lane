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
import { useState, type CSSProperties, type ReactNode } from "react";
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
  const orderChip = p.fromOrder ? "관제 지정" : "기본";
  const opts: { o: RouteOption; on: boolean; accent: string; chip: string; title: string; scope: boolean }[] = p.same
    ? [{ o: p.safe, on: true, accent: C.toneGreen, chip: "안전 · 최속 동일", title: SAME_ROUTE_TITLE, scope: true }]
    : [
        { o: p.safe, on: p.chosen === "safe", accent: C.toneGreen,
          chip: p.chosen === "safe" ? orderChip : "대안", title: "안전 경로", scope: true },
        ...(p.fast ? [{ o: p.fast, on: p.chosen === "fast", accent: C.toneYellow,
          chip: p.chosen === "fast" ? orderChip : "대안", title: "빠른 경로", scope: false }] : []),
      ];
  const cols = { display: "grid", gridTemplateColumns: two ? "1fr 1fr" : "1fr", gap: 10 } as const;
  return (
    <Sheet wf="02" footer={<Cta onClick={p.onConfirm}>안내 시작</Cta>}>
      <div style={{ fontSize: 22, fontWeight: 800 }}>
        {p.same ? SAME_ROUTE_TITLE : p.chosen === "safe" ? "안전 경로로 간다" : "빠른 경로로 간다"}
      </div>
      {/* ★ 고르는 데 필요한 것은 **둘의 차 한 줄**이다 — 카드 위에 먼저 둔다. 카드는 그 근거다(PLAN #73 · DECISIONS §701) */}
      {two && <Verdict safe={p.safe} fast={p.fast!} />}
      {!two && !p.same && (
        <div style={{ ...note, marginTop: 12 }}>둘째 경로 없음 — 안전 경로로 안내한다.</div>
      )}

      <div style={{ ...cols, marginTop: 12 }}>
        {opts.map((x) => <Col key={x.title} {...x} />)}
      </div>

      <button type="button" onClick={() => setOpen((x) => !x)} aria-expanded={open} style={moreBtn}>
        {open ? "접기 ▴" : "자세히 ▾"}
      </button>
      {/* 펼쳐도 **두 열을 지킨다** — 비교는 나란히 놓여야 산다 */}
      {open && <DetailsGrid opts={opts.map((x) => x.o)} />}
    </Sheet>
  );
}

/**
 * 빠른 경로가 안전 경로와 어떻게 다른가 — **한 문장 · 두 수**(시간 · 확인 필요 곳수). 카드보다 위에 선다.
 * 확인 필요가 늘면 경고색이다 — 빠른 대가가 그것이기 때문이다.
 */
export function verdictLine(safe: RouteOption, fast: RouteOption): { text: string; worse: boolean } {
  const dt = Math.round(fast.sec - safe.sec);
  const dn = fast.uncertainCount - safe.uncertainCount;
  const time = dt === 0 ? "시간이 같고" : dt < 0 ? `${fmtDur(-dt)} 빠르고` : `${fmtDur(dt)} 느리고`;
  const risk = dn === 0 ? "확인 필요는 같다" : `확인 필요가 ${Math.abs(dn)}곳 ${dn > 0 ? "많다" : "적다"}`;
  return { text: `빠른 경로가 ${time} ${risk}`, worse: dn > 0 };
}

function Verdict({ safe, fast }: { safe: RouteOption; fast: RouteOption }) {
  const v = verdictLine(safe, fast);
  return (
    <div style={{ marginTop: 10, borderRadius: 10, padding: "10px 12px", fontSize: 16, fontWeight: 800, lineHeight: 1.35,
                  color: v.worse ? "#9a3412" : C.panelInk, background: v.worse ? "#fff7ed" : "#f1f5f9",
                  border: `1px solid ${v.worse ? "#fed7aa" : C.sheetLine}` }}>
      {v.text}
    </div>
  );
}

/**
 * 경로 한 장. 크게 읽히는 것은 **고르는 데 쓰는 둘**(시간 · 확인 필요)이고 폭 값은 작은 줄이다(설명이지 선택 기준이 아니다).
 * 라벨은 값 **위에** 작게 놓는다 — 한 줄에 나란히 두면 250px 남짓에서 라벨과 값이 붙어 읽힌다. 통행 불가는 0 이 아닐 때만.
 * **누를 수 없다**(§400). 폭 모름 구간은 최소폭에서 빠진 수라 `*` 한 글자를 달고 풀이는 접힌 쪽에 있다.
 */
function Col({ o, on, accent, chip, title, scope }: {
  o: RouteOption; on: boolean; accent: string; chip: string; title: string; scope: boolean;
}) {
  const margin = o.minWidthM != null ? o.minWidthM - o.requiredM : null;
  const b = CLEARANCE_SCALE[clearanceBand(margin)];
  return (
    <div style={{ ...card, marginTop: 0, cursor: "default", borderColor: on ? accent : C.sheetLine,
                  opacity: on ? 1 : .85,
                  boxShadow: on ? `0 0 0 3px ${accent}66` : "0 1px 3px rgba(0,0,0,.06)" }}>
      <div style={{ ...band, background: on ? accent : `${accent}55`, flexWrap: "wrap", gap: 4 }}>
        <b style={{ fontSize: 15 }}>{title}</b>
        <span style={{ flex: 1 }} />
        <span style={chipS}>{chip}</span>
      </div>
      <div style={{ padding: "8px 10px 10px" }}>
        {/* 두 카드의 첫 줄을 맞춘다 — 안전 경로만 단 한 줄이 있어 시간 · 확인 필요가 어긋나던 것을, 같은 높이의 빈 줄로 막는다 */}
        <div style={{ fontSize: 11, lineHeight: "15px", height: 15, marginBottom: 4, color: C.panelSub }}>{scope ? "폭으로만 본 안전" : ""}</div>
        <div style={{ fontSize: 26, fontWeight: 800, lineHeight: 1.1, color: on ? C.safeInk : "#c2570c" }}>
          {fmtDur(o.sec)} <span style={{ fontSize: 13, fontWeight: 700, color: C.panelSub }}>{(o.lengthM / 1000).toFixed(1)}km</span>
        </div>
        <div style={{ ...lab, marginTop: 10 }}>확인 필요</div>
        <div style={{ fontSize: 26, fontWeight: 800, lineHeight: 1.1, color: o.uncertainCount > 0 ? C.danger : C.panelInk }}>
          {o.uncertainCount}곳
        </div>
        {o.blockedCount > 0 && <div style={{ fontSize: 13, fontWeight: 800, color: C.danger, marginTop: 6 }}>통행 불가 {o.blockedCount}곳</div>}
        <div style={{ ...lab, marginTop: 10, lineHeight: 1.5 }}>
          최소폭 <b style={{ color: C.panelInk }}>{o.minWidthM != null ? `${o.minWidthM.toFixed(1)}m` : "—"}</b>
          {o.unknownCount > 0 && <sup>*</sup>}
          {" · 여유 "}<b style={{ color: b.color }}>{fmtClearance(margin)}</b>
        </div>
      </div>
    </div>
  );
}

/** 접힌 것의 칸들 — 규칙 경고 · 경로 주변 · 구간 목록 · 설명 · 각주. 두 열이 **같은 줄에 같은 칸**이 오도록 칸 이름을 고정한다 */
const SECTIONS = ["rules", "around", "risks", "note", "foot"] as const;
type Section = (typeof SECTIONS)[number];

function cells(o: RouteOption): Record<Section, ReactNode> {
  return {
    rules: o.ruleCount > 0 || o.rules ? <Block k="규칙 경고" v={o.rules ?? `${o.ruleCount}건`} warn /> : null,
    around: o.around ? <Block k="경로 주변" v={o.around} /> : null,
    risks: o.risks.lines.length > 0 ? (
      <div style={riskBox}>
        {o.risks.lines.map((l) => <div key={l}>{l}</div>)}
        {o.risks.more > 0 && <div style={{ color: C.panelSub }}>외 {o.risks.more}곳</div>}
      </div>
    ) : null,
    note: <div style={note}>{o.note}</div>,
    foot: o.unknownCount > 0 ? <div style={{ fontSize: 11, color: C.panelSub }}>* 폭 모름 {o.unknownCount}곳은 뺀 수</div> : null,
  };
}

/** 한 칸 — 라벨은 값 **위에** 작게. 좁은 열에서 나란히 두면 라벨이 두 줄로 꺾인다 */
function Block({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div>
      <div style={lab}>{k}</div>
      <div style={{ fontSize: 13, fontWeight: 800, color: warn ? C.danger : C.panelInk }}>{v}</div>
    </div>
  );
}

/** 접힌 것 하나(한 열). 시험이 이것을 직접 그려 접힌 내용이 다 있는지 본다 */
export function Details({ o }: { o: RouteOption }) {
  const c = cells(o);
  return <div style={{ display: "grid", gap: 8, fontSize: 12, minWidth: 0 }}>{SECTIONS.map((k) => c[k] && <div key={k}>{c[k]}</div>)}</div>;
}

/** 펼침 — **두 열을 지킨다.** 칸마다 두 경로가 같은 줄에 선다(한쪽에 칸이 없으면 그 자리는 빈다) */
function DetailsGrid({ opts }: { opts: RouteOption[] }) {
  const cs = opts.map(cells);
  return (
    <div style={{ display: "grid", gridTemplateColumns: opts.length > 1 ? "1fr 1fr" : "1fr", gap: "8px 10px", marginTop: 10, fontSize: 12 }}>
      {SECTIONS.filter((k) => cs.some((c) => c[k])).flatMap((k) => cs.map((c, i) => <div key={`${k}${i}`} style={{ minWidth: 0 }}>{c[k]}</div>))}
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
const lab: CSSProperties = { fontSize: 11, color: C.panelSub };
const moreBtn: CSSProperties = {
  display: "block", width: "100%", marginTop: 12, padding: "10px 0", border: `1px solid ${C.sheetLine}`,
  borderRadius: 10, background: "#fff", fontSize: 14, fontWeight: 800, color: C.panelInk, cursor: "pointer",
  fontFamily: F.family,
};
const note: CSSProperties = {
  marginTop: 8, borderRadius: 8, padding: "8px 10px", fontSize: 12, color: "#334155", lineHeight: 1.5,
  background: "#f8fafc",
};
