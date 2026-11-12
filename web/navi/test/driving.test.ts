/**
 * test/driving.test.ts — **주행 중 화면의 시선 기준**(DECISIONS §702 · §703). 렌더된 수는 `scripts/glance.mjs` 가 재고, 여기는 **구조**를 문다:
 * 병목 패널의 기본 화면은 다음 구간 하나 · 네 줄이고(「외 N곳」만 수로 남는다), 폭 모름이면 여유를 안 쓰며, 누르는 곳은 76 이상이다.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ok, test } from "./harness";
import { BottleneckPanel, TARGET, type BottleneckData } from "../src/ui/BottleneckPanel";
import { MapControls } from "../src/ui/MapControls";
import { TopBar } from "../src/ui/TopBar";
import { STATUS, type StatusKey } from "../src/domain/status";

const base: BottleneckData = {
  kind: "needs_cv", more: 3, segUid: "s1", segLabel: "밤실로4번길 1-11", aheadM: 323.4, widthM: 3.4, requiredM: 3.0,
  lengthM: 36, coverage: 1, samples: 16, verdictLabel: "판정 보류", verdictColor: "#f59e0b", cctvDistM: 5, grayReason: null,
  reason: { head: "REASON머리", detail: "REASON근거", action: "REASON조치" }, park: 4, ecam: 0,
};
const html = (over: Partial<BottleneckData> = {}, open = true, locked = false) =>
  renderToStaticMarkup(createElement(BottleneckPanel, { ...base, ...over, open, locked, onToggle: () => {}, onShare: () => {}, onReport: () => {} }));

/** 마크업의 `<button … style="…">` 마다 누르는 범위(`width`·`height`·`min-*`)의 **작은 쪽**을 뽑는다. */
function targets(h: string): number[] {
  const out: number[] = [];
  for (const m of h.matchAll(/<button[^>]*style="([^"]*)"/g)) {
    const css = m[1];
    const get = (k: string) => { const r = css.match(new RegExp(`(?:^|;)${k}:(\\d+)px`)); return r ? Number(r[1]) : 0; };
    const w = Math.max(get("width"), get("min-width")), hh = Math.max(get("height"), get("min-height"));
    out.push(Math.min(w || 0, hh || 0));
  }
  return out;
}

test("병목 패널 기본 화면 — 다음 구간 하나 · 거리 · 도로명 · 위험 종류 · 여유 · 외 N곳", () => {
  const h = html();
  for (const t of ["323m 앞", "밤실로4번길 1-11", "확인 필요", "여유 +0.4m", "외 3곳"]) ok(h.includes(t), `${t} 가 안 보인다`);
});

test("병목 패널 기본 화면 — 옛 몸통(유효폭 · 요구폭 · 사유 · 판정 근거)은 접혀 있고 「자세히」 안에 있다(지운 것이 아니다)", () => {
  const h = html();
  for (const gone of ["최소 유효폭", "요구폭", "측정 신뢰도", "REASON머리", "장애물", "판정 근거", "미반영"]) ok(!h.includes(gone), `기본 화면에 ${gone} 가 남았다`);
  ok(h.includes("자세히"), "자세히 단추가 없다");
});

test("병목 패널 — 구간 하나만 말한다(구간 목록이 아니다): 도로명이 한 번만 나온다", () => {
  const h = html();
  ok(h.split("밤실로4번길 1-11").length - 1 === 1, "구간이 둘 이상 나온다");
});

test("병목 패널 — 폭 모름이면 여유 줄이 없다(모르는 수를 쓰면 보는 사람이 믿는다)", () => {
  const h = html({ kind: "unknown", widthM: 2.4 });
  ok(h.includes("폭 모름") && !h.includes("여유"), "폭 모름인데 여유가 적혔다");
});

test("병목 패널 — 「외 N곳」은 남았을 때만(0 이면 안 보인다)", () => {
  ok(!html({ more: 0 }).includes("외 "), "남은 구간이 없는데 외 N곳이 보인다");
});

test("누르는 곳은 전부 76 이상이다 — 병목 패널(닫힌 탭 · 접기 손잡이 · 단추 셋) · 지도 단추 다섯", () => {
  const sizes = { 닫힘: targets(html({}, false)), 열림: targets(html()), 지도: targets(renderToStaticMarkup(createElement(MapControls, {
    onCompass: () => {}, onLocate: () => {}, onZoomIn: () => {}, onZoomOut: () => {}, onLayers: () => {}, layersOn: false }))) };
  ok(sizes.닫힘.length === 1 && sizes.열림.length === 4 && sizes.지도.length === 5, `단추 수가 다르다 ${JSON.stringify(sizes)}`);
  for (const [k, v] of Object.entries(sizes)) ok(v.every((x) => x >= TARGET), `${k} 에 ${TARGET} 미만이 있다: ${v}`);
  ok(TARGET === 76, "기준이 76 이 아니다");
});

test("달리는 중이면 「자세히」 단추가 막혀 있다(disabled) · 서 있으면 열려 있다", () => {
  const moving = html({}, true, true), stopped = html({}, true, false);
  ok(/<button[^>]*disabled=""[^>]*>자세히</.test(moving), "달리는 중인데 자세히가 안 막혔다");
  ok(!/<button[^>]*disabled=""[^>]*>자세히</.test(stopped), "서 있는데 자세히가 막혔다");
  ok(!moving.includes("측정 신뢰도"), "달리는 중에 상세가 그려졌다");
});


// ── 상단 배지: 상태와 단추 문구가 어긋나지 않는다 (DECISIONS §724 · B1) ─────────────────────────
const bar = (key: StatusKey, over: Record<string, unknown> = {}) => renderToStaticMarkup(createElement(TopBar, {
  spec: STATUS[key], vars: {}, vehicleKind: "소방차", turnKind: null, nextDistM: null, roadName: null, nowText: "12:00", etaText: null, incidentText: null, ...over }));

test("안전 경로 주행의 배지에는 「빠른 경로」 문구가 없다 — 경로를 고르는 손이 없으면 단추 문구를 상태 칩으로 안 그린다", () => {
  const h = bar("safe");
  ok(h.includes("안전 경로 안내중"), "상태 글씨가 없다");
  ok(!h.includes("빠른 경로"), "안전 경로 안내중인데 배지가 「빠른 경로」 를 말한다 — 운전자가 가장 먼저 보는 줄에서 경로가 어긋난다");
});

test("빠른 경로 주행의 배지에는 「안전 경로」 문구가 없다", () => {
  const h = bar("fast");
  ok(h.includes("빠른 경로 안내중"), "상태 글씨가 없다");
  ok(!h.includes("안전 경로"), "빠른 경로 안내중인데 배지가 「안전 경로」 를 말한다");
});

test("경로를 바꿀 손이 있으면(onSwitchRoute) 단추 문구가 단추로 그려진다 — 사라진 것이 아니다", () => {
  const h = bar("safe", { onSwitchRoute: () => {} });
  ok(/<button[^>]*>➤ 빠른 경로 안내<\/button>/.test(h), "단추가 없다");
});

test("단추 문구(switchTag)는 safe · fast 둘뿐이고 그 문구는 **상태와 반대 경로**다 — 상태를 말하는 태그는 이 표식이 없다", () => {
  const keys = (Object.keys(STATUS) as StatusKey[]).filter((k) => STATUS[k].switchTag);
  ok(keys.length === 2 && keys.includes("safe") && keys.includes("fast"), `switchTag: ${keys.join(",")}`);
  for (const k of keys) {
    const route = (t: string) => (t.includes("안전") ? "안전" : t.includes("빠른") ? "빠른" : "?");
    ok(route(STATUS[k].tag) !== route(STATUS[k].label), `${k}: 단추 문구가 상태와 같은 경로다 — 단추는 **다른** 경로를 말해야 한다`);
  }
  ok(!bar("approach").includes("undefined") && bar("approach").includes("안전 경로"), "switchTag 가 아닌 상태의 태그(approach)는 그대로 그려져야 한다");
});
