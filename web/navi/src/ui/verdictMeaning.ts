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

/**
 * 회색이 **왜** 회색인가.  (DECISIONS §215-2)
 *
 * ★ 2026-09-17 멘토링 — 「CCTV 가 없는 곳이 대부분이다. 추천할 수 없는 경우도 사유를 명시하라.」
 *   파이프라인은 사유를 이미 낸다(`segments.py` 의 `unknown_reason` 넷 + `width`). 내비 · 관제가
 *   그것을 안 읽어 399구간이 「영상판정 불가」 한 줄로만 보였다.
 * ★ 폭 문턱 숫자를 여기 적지 않는다. 정본은 `seg/params.py` 이고, 여기에 3.0 을 박으면 그쪽이
 *   바뀌어도 화면이 옛 숫자를 말한다. 「소방차 기준폭」 으로 말한다.
 * `short` 는 범례 · 요약용, `long` 은 구간 카드용이다.
 */
export const GRAY_REASON: Record<string, { short: string; long: string }> = {
  no_cctv_band: {
    short: "폭 애매 · 주정차에 달림",
    long: "CCTV 없음 · 폭이 기준폭 이상이지만 양쪽 주정차를 감안한 폭에는 못 미친다 — 주정차가 있으면 막히고 없으면 지난다. 영상판정의 본래 대상인데 볼 카메라가 없다",
  },
  no_cctv_thin: {
    short: "측정폭만 좁음 · 근거 하나",
    long: "CCTV 없음 · 측정 노면폭은 기준폭 미만인데 도로대장폭은 아니거나 없다 — 근거가 하나뿐이라 통행 불가로 확정하지 않았다",
  },
  no_cctv_narrow: {
    short: "측정 · 대장 둘 다 좁음",
    long: "CCTV 없음 · 측정 노면폭과 도로대장폭이 둘 다 기준폭 미만 — 다만 담장 사이는 넓어 갓길로 지날 여지가 있어 확정하지 않았다",
  },
  no_cctv_single: {
    short: "폭 표본 하나 · 확정 보류",
    long: "CCTV 없음 · 넓게 나왔지만 폭 표본이 하나뿐이다 — 표본 하나로 통과를 확정했다가 틀린 사고(DM02825)가 있어 보류했다",
  },
  width: {
    short: "폭 산출 실패",
    long: "폭을 재지 못했거나 근거가 하나다 — 도면으로도 영상으로도 확정 못 한다",
  },
};

/** 회색 구간의 사유. 회색이 아니거나 사유가 없으면 null */
export function grayReason(e: { verdict: string; unknown_reason?: string | null }): { short: string; long: string } | null {
  if (e.verdict !== "unknown" || !e.unknown_reason) return null;
  return GRAY_REASON[e.unknown_reason] ?? { short: e.unknown_reason, long: e.unknown_reason };
}
