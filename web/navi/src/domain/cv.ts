/**
 * domain/cv.ts — **영상이 실시간으로 재 준 통과폭을 경로·안내가 받는 자리.**
 *                                                          (DECISIONS §363)
 *
 * ══ 상용 내비와 **다른 축**이다 ═══════════════════════════════════
 * 상용 턴바이턴의 재탐색 방아쇠는 둘이다 — **이탈**과 **소통(시간)**. TomTom
 * SDK 가 그렇고(`hasDeviated` → 같은 비용모형으로 자동 재계획), 카카오·티맵도
 * 같다. 그 둘의 공통점은 **옛 경로가 여전히 갈 수는 있다**는 것이다. 늦을 뿐이다.
 * 그래서 재탐색을 미뤄도 되고, 미루는 것이 오히려 화면을 안 흔든다.
 *
 * 우리 방아쇠는 셋째다 — **통과 가능성**. 영상이 「이 골목 지금 2.1m」라고 하면
 * 옛 경로는 늦은 것이 아니라 **틀린 것**이고, 그때 차는 이미 들어가 있을 수 있다.
 * 늦게 알면 소방차가 후진한다. 그래서 셋이 달라진다 —
 *
 *     선점   폭 경고가 회전 안내를 **밀어낸다**(아래 `urgencyOf`). 회전을 놓치면
 *            재탐색이지만, 못 지나는 골목에 들어가면 후진이다
 *     신선도 **낡은 측정은 `clear` 로 남으면 안 된다.** 통과폭을 정하는 것은
 *            주차된 차이고 그것은 분 단위로 바뀐다. 셋으로 삭는다
 *     퇴행   영상이 없는 곳이 **대부분이다**(CCTV 유효범위 밖 830/1,281).
 *            없을 때 오늘과 **한 글자도 다르지 않아야** 한다
 *
 * ══ ★ 좁히는 쪽만 받는다 (1판) ════════════════════════════════════
 * 영상이 정적 판정보다 **좁게** 재면 즉시 받는다. **넓게** 재면 안 쓴다.
 *
 *     거짓 좁음의 값   돌아간다 — 되돌릴 수 있다
 *     거짓 넓음의 값   소방차가 골목에 낀다 — 못 되돌린다
 *
 * 값이 비대칭이면 신뢰도 비대칭이어야 한다. 넓히는 쪽을 켜려면 **정적 판정이
 * 얼마나 자주 과하게 보수적인가**를 먼저 재야 한다(PLAN 이 그 측정을 든다).
 * 「근거 없이 막지 않는다」(§81 · §86-4)의 거울이다 — **근거 없이 열지 않는다.**
 *
 * ★ 순수하다. React · MapLibre · fetch · 전송을 모른다. `opsProtocol.ts` 와 같은
 *   규율이다 — 말의 모양만 여기 두고 전송은 `infra` 가 고른다.
 */

/** 영상이 한 번 잰 것. **사실이지 명령이 아니다.** */
export interface CvReading {
  t: "cv";
  /** 어느 구간인가. `segments.geojson` 의 `seg_uid` */
  seg: string;
  /**
   * 잰 통과폭(m). `null` 은 **못 쟀다**는 뜻이다 — 가림 · 야간 · 화각 밖.
   * 「넓다」가 아니다. 못 잰 것을 넓다고 읽으면 그것이 가장 비싼 거짓이다.
   */
  passM: number | null;
  /** 잰 시각(epoch ms) */
  at: number;
  /** 어느 카메라가 냈나 */
  cam: string;
  /** 0‥1. 낮으면 **경로를 안 바꾸고 말만 한다** */
  conf: number;
}

/** 이 안이면 측정이 **권위 있다** — 경로가 받는다(ms) */
export const CV_FRESH_MS = 90_000;
/** 이보다 낡으면 **버린다** — 정적 판정으로 돌아간다(ms) */
export const CV_STALE_MS = 300_000;
/** 이 아래 신뢰도는 경로를 안 바꾼다. 말은 할 수 있다 */
export const CV_ROUTE_CONF = 0.6;

/** 측정이 지금 어느 나이인가. */
export type CvAge = "fresh" | "aging" | "stale";

export function ageOf(r: CvReading, now: number): CvAge {
  const d = now - r.at;
  if (d < 0 || d <= CV_FRESH_MS) return "fresh";
  if (d <= CV_STALE_MS) return "aging";
  return "stale";
}

/** 구간 하나에 대해 지금 믿는 것. */
export interface CvView {
  seg: string;
  /** 경로가 써도 되는 폭(m). `null` = 안 쓴다(정적 판정 그대로) */
  routeM: number | null;
  /** 사람에게 말해도 되는 폭(m). `null` = 말할 것 없다 */
  sayM: number | null;
  age: CvAge;
  at: number;
  cam: string;
}

/**
 * 측정 묶음을 구간별 **한 벌**로 접는다. 같은 구간이면 **가장 최근**이 이긴다.
 *
 * ★ 가장 좁은 것이 아니라 **가장 최근**이다. 통과폭은 상태이지 성질이 아니다 —
 *   차가 빠지면 넓어지고, 가장 좁았던 순간을 영원히 들고 있으면 그 골목은
 *   영원히 막힌 것이 된다.
 */
export function fold(readings: readonly CvReading[], now: number): Map<string, CvView> {
  const latest = new Map<string, CvReading>();
  for (const r of readings) {
    if (ageOf(r, now) === "stale") continue;
    const cur = latest.get(r.seg);
    if (!cur || r.at > cur.at) latest.set(r.seg, r);
  }
  const out = new Map<string, CvView>();
  for (const [seg, r] of latest) {
    const age = ageOf(r, now);
    // 못 쟀으면 **아무 말도 안 한다.** 못 잰 것은 넓다는 뜻이 아니다
    const sayM = r.passM;
    const routeM =
      r.passM != null && age === "fresh" && r.conf >= CV_ROUTE_CONF ? r.passM : null;
    out.set(seg, { seg, routeM, sayM, age, at: r.at, cam: r.cam });
  }
  return out;
}

/**
 * 정적 폭과 영상 폭을 합친다. **좁히는 쪽만 받는다.**
 *
 * @param staticM 정적 판정이 든 최소 유효폭(`width_min_m`)
 * @param v       이 구간의 영상 소견. 없으면 `undefined`
 */
export function effectiveWidth(
  staticM: number | null | undefined,
  v: CvView | undefined,
): number | null {
  const s = staticM ?? null;
  if (!v || v.routeM == null) return s;
  if (s == null) return null;          // 정적이 모르면 영상 하나로 안 연다
  return Math.min(s, v.routeM);        // ★ 좁히는 쪽만
}

/** 영상이 **길을 막았는가** — 이 차가 못 지나게 됐는가. */
export function narrowedToBlocked(
  staticM: number | null | undefined,
  v: CvView | undefined,
  requiredM: number,
): boolean {
  const before = staticM ?? null;
  const after = effectiveWidth(staticM, v);
  if (before == null || after == null) return false;
  return before >= requiredM && after < requiredM;
}

/**
 * 안내의 급함. **막은 측정은 회전보다 앞이다.**
 *
 * ★ 상용 내비에는 이 갈래가 없다. 그쪽 최우선은 이탈이고, 이탈은 「길을 잘못
 *   들었다」다 — 되돌아가면 된다. 여기 최우선은 **「지금 가는 길로 못 간다」**이고
 *   그것을 늦게 말하면 후진이다.
 */
export function urgencyOf(blocked: boolean, age: CvAge): "critical" | "normal" | null {
  if (age === "stale") return null;
  if (blocked) return age === "fresh" ? "critical" : "normal";
  return "normal";
}

/** 사람에게 할 말. 없으면 `null`. */
export function phrase(v: CvView, blocked: boolean): string | null {
  if (v.sayM == null) return null;
  const w = v.sayM.toFixed(1);
  if (blocked) return `앞 구간 통과폭 ${w}미터. 이 차로 못 지납니다.`;
  if (v.age === "aging") return `앞 구간 통과폭 ${w}미터로 측정됐습니다. 조금 지난 값입니다.`;
  return `앞 구간 통과폭 ${w}미터.`;
}
