/**
 * ui/verdictMeaning.ts — 판정 4색이 **무엇을 뜻하는가**, 사람 말로.  (DECISIONS §214-4)
 *
 * ★ 색은 여기 없다. 정본은 `web/config.js` 이고 `navi_graph.json.style` 로 온다.
 *   여기는 색마다 붙이는 **한 줄 설명**뿐이다 — 2026-09-22 사용자 정의 그대로:
 *
 *     초록  CV 할 필요 없이 통행 가능
 *     빨강  CV 할 필요 없이 통행 불가
 *     회색  CV 를 못 한다 (CCTV 25m 밖)
 *     주황  CV 대상 — CV 를 돌리면 초록 아니면 빨강. **바뀌는 것은 주황뿐이다**
 *
 * 내비 범례와 관제 범례가 같은 줄을 쓴다.
 */
export const VERDICT_ORDER = ["clear", "needs_cv", "blocked", "unknown"] as const;

export const VERDICT_MEANING: Record<string, string> = {
  clear: "영상판정 없이 통행 가능",
  blocked: "영상판정 없이 통행 불가",
  unknown: "영상판정 불가 — CCTV 25m 밖",
  needs_cv: "영상판정 대상 — 판정 뒤 초록 또는 빨강",
};
