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
import type { CSSProperties } from "react";
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
  if (p.same) return <SameRoute {...p} />;
  return (
    <Sheet wf="02" footer={
      <Cta onClick={p.onConfirm}>안내 시작</Cta>
    }>
      <div style={{ fontSize: 22, fontWeight: 800 }}>
        {p.chosen === "safe" ? "안전 경로로 간다" : "빠른 경로로 간다"}
      </div>
      <div style={{ fontSize: 13, color: C.panelSub, marginTop: 4 }}>
        {p.fromOrder
          ? "관제가 정한 경로다. 아래는 다른 경로와의 차이다."
          : "지령에 경로 지정이 없어 안전으로 간다."}
      </div>

      <Card o={p.safe} on={p.chosen === "safe"}
            accent={C.toneGreen} chip={p.chosen === "safe" ? "지령" : "안 간다"}
            title="안전 경로" />
      {p.fast ? (
        <Card o={p.fast} on={p.chosen === "fast"}
              accent={C.toneYellow}
              chip={p.chosen === "fast" ? "지령"
                : p.fast.deltaSec < -1 ? `${fmtDur(-p.fast.deltaSec)} 빠름` : "같음"}
              title="빠른 경로" />
      ) : (
        <div style={{ ...note, marginTop: 12 }}>
          이 차종 · 이 조건에서 둘째 경로가 서지 않았다 — 안전 경로 하나로 안내한다.
        </div>
      )}

      <div style={{ fontSize: 11, color: C.panelSub, marginTop: 12, lineHeight: 1.5 }}>
        <b>폭으로만 본 안전이다</b>
      </div>
    </Sheet>
  );
}

/**
 * 안전 경로 = 빠른 경로일 때의 화면.  (멘토링 §219 → DECISIONS §220)
 *
 * ★ 고르게 하지 않는다. 고를 것이 없다 — 라디오 두 개를 두면 같은 줄을 두 번 읽힌다.
 *   그대로 「안내 시작」 으로 간다. (2026-10-05 이후로는 **다를 때도** 안 고른다.)
 */
function SameRoute(p: Props) {
  const o = p.safe;
  const margin = o.minWidthM != null ? o.minWidthM - o.requiredM : null;
  return (
    <Sheet wf="02" footer={
      <Cta onClick={p.onConfirm}>안내 시작</Cta>
    }>
      <div style={{ fontSize: 22, fontWeight: 800 }}>{SAME_ROUTE_TITLE}</div>
      <div style={{ fontSize: 13, color: C.panelSub, marginTop: 4 }}>
        안전 경로와 최단 경로가 같은 길이다.
      </div>

      <div style={{ ...card, cursor: "default", borderColor: C.toneGreen }}>
        <div style={{ ...band, background: C.toneGreen }}>
          <b style={{ fontSize: 17 }}>{SAME_ROUTE_TITLE}</b>
          <span style={{ flex: 1 }} />
          <span style={chipS}>안전 · 최속 동일</span>
        </div>
        <div style={{ padding: "10px 14px 12px" }}>
          <div style={{ fontSize: 23, fontWeight: 800, color: C.safeInk, margin: "2px 0 8px" }}>
            {fmtDur(o.sec)} · {(o.lengthM / 1000).toFixed(1)}km
          </div>
          <Diff o={o} />
          <Row k="최소 유효폭 · 요구폭"
               v={`${o.minWidthM != null ? `${o.minWidthM.toFixed(1)}m` : "—"} · ${o.requiredM.toFixed(1)}m`} />
          <ClearanceRow m={margin} />
          <Row k="통행 규칙" v={o.rules ?? "없음"} warn={!!o.rules} />
          {o.around && <Row k="경로 주변" v={o.around} />}
          <div style={{ ...note, background: "#f0fdf4" }}>{o.note}</div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: C.panelSub, marginTop: 12, lineHeight: 1.5 }}>
        <b>폭으로만 본 안전이다</b>
      </div>
    </Sheet>
  );
}

/** 두 경로를 눈으로 뺄 수 있게 하는 세 줄(§220). 같은 자리에 같은 순서로 놓는다 */
function Diff({ o }: { o: RouteOption }) {
  return (
    <>
      <Row k="길이" v={`${(o.lengthM / 1000).toFixed(2)}km`} />
      <Row k="통행 불가 경유" v={`${o.blockedCount}곳`} warn={o.blockedCount > 0} />
      <Row k="규칙 경고" v={`${o.ruleCount}건`} warn={o.ruleCount > 0} />
      <Row k="폭 확인 필요 구간"
           v={o.uncertainCount ? `${o.uncertainCount}개 · ${Math.round(o.uncertainM)}m` : "0개"} />
    </>
  );
}

/** 여유폭 한 줄 — 수와 4단 색을 같이(§219 「색과 수로」) */
function ClearanceRow({ m }: { m: number | null }) {
  const b = CLEARANCE_SCALE[clearanceBand(m)];
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "3px 0" }}>
      <span style={{ color: C.panelSub }}>여유폭 = 최소 유효폭 − 요구폭</span>
      <span style={{ fontWeight: 800, color: b.color }}>
        {fmtClearance(m)} <span style={{ fontWeight: 700, color: C.panelSub }}>{b.short}</span>
      </span>
    </div>
  );
}

/**
 * 경로 한 장. **누를 수 없다.**
 *
 * ★ 2026-10-05 (§400). 종전에는 `<button onClick>` 이었다. 고르는 손이
 *   없어졌으므로 **`div` 로 바꿨다** — 누를 수 있는 모양으로 두면 언젠가
 *   누가 `onClick` 을 단다. 라디오 점도 뺐다.
 */
function Card({ o, on, accent, chip, title }: {
  o: RouteOption; on: boolean;
  accent: string; chip: string; title: string;
}) {
  const margin = o.minWidthM != null ? o.minWidthM - o.requiredM : null;
  const ink = on ? C.safeInk : "#c2570c";
  return (
    <div style={{ ...card, cursor: "default", borderColor: on ? accent : C.sheetLine,
                  opacity: on ? 1 : .72,
                  boxShadow: on ? `0 0 0 3px ${accent}66` : "0 1px 3px rgba(0,0,0,.06)" }}>
      <div style={{ ...band, background: on ? accent : `${accent}55` }}>
        <b style={{ fontSize: 17 }}>{title}</b>
        <span style={{ flex: 1 }} />
        <span style={chipS}>{chip}</span>
      </div>
      <div style={{ padding: "10px 14px 12px" }}>
        <div style={{ fontSize: 23, fontWeight: 800, color: ink, margin: "2px 0 8px" }}>
          {fmtDur(o.sec)} · {(o.lengthM / 1000).toFixed(1)}km
        </div>
        {/* ★ §220 — 두 카드가 **같은 네 줄을 같은 순서로** 낸다. 다른 곳이 어디인지
            눈으로 빼게 하려는 것이라, 한쪽만 줄을 빼면 안 된다 */}
        <Diff o={o} />
        <Row k="최소 유효폭" v={o.minWidthM != null ? `${o.minWidthM.toFixed(1)}m` : "—"} />
        <ClearanceRow m={margin} />
        <Row k="통행 규칙" v={o.rules ?? "없음"} warn={!!o.rules} />
        {o.around && <Row k="경로 주변" v={o.around} />}
        <div style={{ ...note, background: on ? "#f0fdf4" : "#fffbeb" }}>{o.note}</div>
      </div>
    </div>
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
const chipS: CSSProperties = {
  borderRadius: 8, padding: "3px 9px", fontSize: 12, fontWeight: 800, color: C.toneInk,
  background: "#fff",
};
const note: CSSProperties = {
  marginTop: 8, borderRadius: 8, padding: "8px 10px", fontSize: 12, color: "#334155", lineHeight: 1.5,
  background: "#f8fafc",
};
