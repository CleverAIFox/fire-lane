/**
 * domain/reroute.ts — **영상이 길을 막았을 때 경로를 다시 낼 것인가.** (DECISIONS §366)
 *
 * ══ 상용 내비의 방아쇠 둘, 우리의 셋째 ════════════════════════════
 * `cv.ts` 머리말이 축을 적었다 — 상용의 재탐색 방아쇠는 **이탈**과 **소통**이고
 * 둘 다 「옛 경로는 여전히 갈 수는 있다」다. 우리 셋째는 **통과 가능성**이고
 * 그때 옛 경로는 늦은 것이 아니라 **틀린 것**이다.
 *
 * 그 차이가 이 파일의 모든 규율을 정한다. 틀린 경로를 늦게 버리면 소방차가
 * 못 지나는 골목에 들어가고, 그때 할 수 있는 일은 **후진**뿐이다.
 *
 * ══ 그런데 재탐색도 값이 든다 ═════════════════════════════════════
 * 「틀렸으면 즉시 다시 낸다」만으로는 못 짠다. 통과폭을 정하는 것은 주차된
 * 차이고 그것은 **분 단위로 들락거린다.** 폴링마다 2.1 → 3.4 → 2.1 이 오면
 * 폴링마다 경로가 바뀌고, 화면이 떨리는 내비는 운전자가 끈다.
 *
 * 그래서 방아쇠를 **좁게** 둔다. 네 규율 —
 *
 *     ① 앞만 본다       지나온 구간이 좁아진 것은 재탐색이 아니다.
 *                       `rules.nextRule(ws, driven, reachM)` 과 같은 축이다
 *     ② 막힘만 센다     좁아져도 지나면 **말**이고 경로가 아니다. 상용이
 *                       소통으로 다시 내는 그 자리를 우리는 **비운다** —
 *                       우리 영상은 「몇 분 더 걸린다」를 재지 못한다
 *     ③ 한 번만 쏜다    같은 구간은 **판정이 바뀔 때까지** 다시 안 쏜다.
 *                       이력(hysteresis)이 없으면 깜빡임이 곧 재탐색이다
 *     ④ 낡음은 방아쇠가 아니고 **되돌림도 아니다**
 *                       측정이 삭으면 폭은 정적 판정으로 **조용히** 돌아간다
 *                       (`cv.effectiveWidth`). 그러나 「다시 지날 수 있습니다」
 *                       라고 **말하지 않고** 우회를 되돌리지도 않는다 —
 *                       이미 돌아간 차를 삭은 값으로 불러들이는 것이
 *                       「거짓 넓음」의 가장 비싼 꼴이다(§363 1판)
 *
 * ══ ★ 발밑과 앞은 **다른 일**이다 ═══════════════════════════════
 * 막힌 구간이 **지금 밟고 있는 구간**이면 재탐색은 쓸모가 없다 — 앞으로 못
 * 나가는 구간에서 「앞으로 가는 길」을 다시 계산하는 셈이다. 그때 필요한 것은
 * 경로가 아니라 **「정지하고 후진」**이고, 그 말은 회전 안내를 밀어내야 한다
 * (`cv.urgencyOf` 가 `critical` 을 내는 그 자리다).
 *
 * 그래서 이 함수는 **어느 경우인지를 말한다.** 둘을 한 값으로 뭉치면 훅이
 * 발밑에서 경로를 다시 내고, 그 경로는 같은 구간으로 다시 들어간다.
 *
 * ★ 순수하다. React · fetch · A* 를 모른다. **경로를 안 낸다** — 「다시 낼
 *   것인가」와 「무엇으로」만 답하고, 내는 것은 `routeSolve` 일이다.
 *
 * IN    RoutePlan · `cv.fold()` 가 접은 구간별 소견 · 필요폭 · 주행거리
 * OUT   RerouteSignal 또는 null
 * 밖    **경로를 안 낸다.** 그래프도 인접리스트도 안 만진다 — 영상 폭이
 *       비용에 들어가는 자리는 `adjacency.buildAdjacency` 의 `cv` 인자다.
 *       **말도 안 만든다**(`voice.ts` · `cv.phrase`).
 */

import { effectiveWidth, type CvView } from "./cv";
import type { RoutePlan } from "./types";

/**
 * 막힌 구간이 **어디인가.** 둘은 다른 처방을 받는다.
 *
 *     ahead      앞에 있다 → 경로를 다시 낸다
 *     underfoot  밟고 있다 → **재탐색이 아니라 정지·후진**이다
 */
export type RerouteKind = "ahead" | "underfoot";

export interface RerouteSignal {
  seg_uid: string;
  kind: RerouteKind;
  /** 경로 시작부터 그 구간 머리까지(m). 모르면 null */
  atM: number | null;
  /** 어느 카메라가 냈나 — 사람이 되짚을 수 있어야 한다 */
  cam: string;
  /** 영상이 잰 통과폭(m) */
  passM: number;
  /** 이 차가 필요한 폭(m) */
  requiredM: number;
}

/**
 * 이력(hysteresis)의 기억. **훅의 `useRef` 다.**
 *
 * ★ 값이 `seg_uid → 그때 쏜 통과폭` 인 이유 — 「쐈다」만 기억하면 같은 구간이
 *   **더 좁아져도** 조용하다. 2.1m 로 쏜 뒤 0.8m 가 오면 그것은 같은 사실이
 *   아니다(코너를 크게 돌 여지까지 사라진다). 폭을 기억해 **더 좁아질 때만**
 *   다시 쏜다. 넓어지는 쪽으로는 안 쏜다 — ④ 규율이다.
 */
export type RerouteMemory = Map<string, number>;

/** 「더 좁아졌는가」의 문턱(m). 측정 잡음으로 다시 쏘지 않을 만큼 */
export const RETRIGGER_DROP_M = 0.3;

export interface RerouteInput {
  plan: RoutePlan | null;
  /** `cv.fold()` 가 접은 구간별 소견 */
  cv: ReadonlyMap<string, CvView> | null | undefined;
  /** 이 차가 필요한 폭(m) — `vehicle.requiredWidth` 가 낸다 */
  requiredM: number;
  /** 경로 시작부터 온 거리(m). 이탈이거나 모르면 null */
  driven: number | null;
  /** 지금 밟고 있는 구간. 모르면 null */
  currentUid?: string | null;
  /** 기억. 없으면 이력 없이 본다(시험·일회성 판정) */
  mem?: RerouteMemory;
}

/**
 * 경로에서 구간마다 **머리까지의 거리**를 센다.
 *
 * ★ 같은 `seg_uid` 가 경로에 두 번 나올 수 있다(되돌아 나오는 골목). **처음
 *   나온 자리**를 쓴다 — 두 번째 자리를 쓰면 이미 지난 것이 「앞」이 된다.
 */
function headsOf(plan: RoutePlan): Map<string, number> {
  const out = new Map<string, number>();
  let acc = 0;
  for (const e of plan.edges) {
    if (!out.has(e.seg_uid)) out.set(e.seg_uid, acc);
    acc += e.length_m ?? 0;
  }
  return out;
}

/**
 * **지금 경로를 다시 내야 하는가.** 아니면 `null`.
 *
 * ★ 0건이 정상이다. 영상이 없거나(대부분 · CCTV 유효범위 밖 830/1,281) 아무
 *   구간도 막지 않으면 `null` 이고, 그때 이 함수는 **오늘과 한 글자도 다르지
 *   않다** — 그것이 §363 의 「퇴행 무손실」을 경로 쪽에서 지키는 자리다.
 */
export function rerouteSignal(t: RerouteInput): RerouteSignal | null {
  const { plan, cv, requiredM, driven, currentUid, mem } = t;
  if (!plan || !cv || cv.size === 0) return null;

  const heads = headsOf(plan);
  let best: RerouteSignal | null = null;

  for (const e of plan.edges) {
    const v = cv.get(e.seg_uid);
    if (!v || v.routeM == null) continue;      // 영상이 경로를 바꿀 자격이 없다
    // ② 막힘만 센다 — 「지나던 길이 영상으로 못 지나게 됐는가」
    const after = effectiveWidth(e.width_min_m, v);
    if (e.width_min_m == null || after == null) continue;
    if (!(e.width_min_m >= requiredM && after < requiredM)) continue;

    const atM = heads.get(e.seg_uid) ?? null;
    const underfoot = currentUid != null && currentUid === e.seg_uid;
    // ① 앞만 본다. 발밑은 「앞」이 아니지만 **버리지도 않는다** — 그쪽은
    //   재탐색이 아니라 정지·후진이고, 그 사실을 훅에 말해야 한다.
    if (!underfoot && driven != null && atM != null && atM < driven) continue;

    // ③ 한 번만 쏜다 — 같은 구간은 **더 좁아질 때만** 다시.
    const shot = mem?.get(e.seg_uid);
    if (shot != null && v.routeM > shot - RETRIGGER_DROP_M) continue;

    const sig: RerouteSignal = {
      seg_uid: e.seg_uid, kind: underfoot ? "underfoot" : "ahead",
      atM, cam: v.cam, passM: v.routeM, requiredM,
    };
    // ★ 발밑이 **언제나 먼저다.** 앞의 막힘은 돌아갈 수 있고 발밑은 못 간다.
    //   그 다음은 **가까운 쪽**이다 — 먼 막힘을 먼저 처리하면 차가 가까운
    //   막힘에 이미 들어가 있다.
    if (!best) best = sig;
    else if (sig.kind === "underfoot" && best.kind === "ahead") best = sig;
    else if (sig.kind === best.kind && (sig.atM ?? Infinity) < (best.atM ?? Infinity)) best = sig;
  }
  return best;
}

/**
 * 쏜 것을 기억에 적는다. **훅이 재탐색을 실제로 시작한 뒤에 부른다.**
 *
 * ★ 판단과 기록을 가른다. `rerouteSignal` 안에서 적으면 **보기만 해도 쐈다가
 *   되고**, 그러면 시험이 같은 입력을 두 번 물을 수 없다 — 두 번째는 늘
 *   `null` 이다. 같은 이유로 `voice.ts` 도 `say` 와 `remember` 를 가른다.
 */
export function rememberReroute(mem: RerouteMemory, sig: RerouteSignal): void {
  const prev = mem.get(sig.seg_uid);
  if (prev == null || sig.passM < prev) mem.set(sig.seg_uid, sig.passM);
}

/**
 * 경로가 바뀌었으니 기억을 **경로 밖만** 비운다.
 *
 * ★ 전부 비우면 안 된다. 새 경로가 같은 막힌 구간을 다시 물면(돌아갈 길이
 *   정말 없을 때 그렇게 된다) **곧바로 또 쏘고**, 그러면 재탐색이 무한히 돈다.
 *   경로에 남은 구간의 기억은 들고 간다.
 */
export function pruneReroute(mem: RerouteMemory, plan: RoutePlan | null): void {
  const live = new Set((plan?.edges ?? []).map((e) => e.seg_uid));
  for (const k of [...mem.keys()]) if (!live.has(k)) mem.delete(k);
}

/**
 * **앞에서 처음 만나는 영상 소견.** 말할 거리를 고르는 자리다(`voice.ts`).
 *
 * ★ 재탐색과 **다른 물음**이다. 재탐색은 「막혔는가」만 보지만 말은 막히지
 *   않은 것도 한다 — 「앞 구간 통과폭 3.4미터」는 운전자가 알아야 할 사실이고
 *   경로를 바꿀 사실은 아니다(§366 ② 규율의 나머지 반쪽).
 *
 * ★ `reachM` 안만 본다. 400m 앞 골목의 폭을 지금 말하면 도착할 때 잊는다 —
 *   `rules.nextRule` 이 같은 창을 쓴다.
 *
 * @returns `voice.ts` 의 `VoiceTick.cv` 가 그대로 받는 꼴. 없으면 null
 */
export function cvAhead(
  plan: RoutePlan | null,
  cv: ReadonlyMap<string, CvView> | null | undefined,
  driven: number | null,
  reachM: number,
  requiredM: number,
): { view: CvView; blocked: boolean } | null {
  if (!plan || !cv || cv.size === 0) return null;
  const d = driven ?? 0;
  let acc = 0;
  for (const e of plan.edges) {
    const L = e.length_m ?? 0;
    const head = acc;
    acc += L;
    if (acc < d) continue;                       // 이미 지났다
    if (head - d > reachM) break;                // 아직 멀다 — 뒤는 더 멀다
    const v = cv.get(e.seg_uid);
    if (!v || v.sayM == null) continue;          // 말할 것이 없다
    const before = e.width_min_m;
    const after = effectiveWidth(before, v);
    const blocked = before != null && after != null
      && before >= requiredM && after < requiredM;
    return { view: v, blocked };
  }
  return null;
}

/** 사람에게 할 말. 처방이 다르므로 **문구도 다르다.** */
export function reroutePhrase(sig: RerouteSignal): string {
  const w = sig.passM.toFixed(1);
  return sig.kind === "underfoot"
    ? `현재 구간 통과폭 ${w}미터. 이 차로 못 지납니다. 정지 후 후진하십시오.`
    : `앞 구간 통과폭 ${w}미터로 막혔습니다. 경로를 다시 찾습니다.`;
}
