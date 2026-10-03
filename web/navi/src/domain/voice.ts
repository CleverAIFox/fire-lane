/**
 * domain/voice.ts — **무엇을 말할 것인가.** 한 틱에 하나.
 *
 * ── 왜 훅에서 내렸나 (2026-09-30 · PLAN §13 W13-5 · DECISIONS §329) ──
 * 이 사슬은 `app/useVoice.ts` 의 `useEffect` 안에 살았다. 값은 **정책**인데
 * 자리가 React 였고, 그래서 물으려면 렌더러가 필요했다 — `vitest` 환경이
 * `node` 라 렌더러가 없고, 그것을 더하는 것은 정책 하나를 물자고 의존성을
 * 늘리는 일이다. **정책은 훅일 이유가 없다.**
 *
 * 내리고 나니 훅에 남은 것은 React 배선뿐이다 — 참조 · 효과 · 속도 평활.
 *
 * ── 우선순위 ────────────────────────────────────────────────────
 *     이탈 > 재동기화 > **영상 통과불가** > 회전 > 규칙 > 사정 > 판정
 *
 * ★ 2026-10-03 (DECISIONS §363). **영상이 「못 지난다」고 하면 회전을 밀어낸다.**
 *   회전을 놓치면 재탐색이고 되돌릴 수 있다. 못 지나는 골목에 들어가면
 *   소방차가 후진한다 — 되돌리는 값이 다르면 순서도 달라야 한다.
 *   막지 않은 영상 소견은 **규칙과 같은 단**이다(둘 다 「가 봐야 아는 것」).
 *
 * ★ 규칙이 판정보다 앞이다. **폭은 지나가며 볼 수 있지만 대향차는 들어가
 *   봐야 안다**(§215-1).
 * ★ 회전이 판정을 이긴다. 회전을 놓치면 경로를 벗어나고, 벗어나면 그 뒤의
 *   판정 안내는 전부 엉뚱한 자리의 말이 된다.
 *
 * ── 기억을 제자리에서 옮긴다 ────────────────────────────────────
 * `step()` 은 **순수하지 않다** — `VoiceMemory` 를 그 자리에서 고친다.
 * 그렇게 둔 이유는 훅의 `useRef` 들이 하던 일을 그대로 옮겨야 **동작이
 * 같음**을 눈으로 확인할 수 있기 때문이다. 순수하게 만들려고 「무엇을
 * 기억하라」를 반환값에 담으면, 부르는 쪽이 그것을 적용하는 코드가 또
 * 생기고 거기에 시험이 없다. 이름으로 적어 둔다 — **한 걸음(step)이다.**
 *
 * 밖  **말하지 않는다.** 발화기에 넘기는 것은 훅이 한다.
 *     **급함의 뜻은 안 든다.** 무엇을 먼저 버리고 무엇이 자르는가는
 *     `infra/speech.ts` 의 `RANK` 다 — 여기는 자리마다 이름만 붙인다.
 *     **속도를 재지 않는다.** 훅이 재서 넘긴다.
 */
import { phrase as cvPhrase, urgencyOf, type CvView } from "./cv";
import { gateIndex, mergePhrase, type Maneuver } from "./turn";
import { lookAhead } from "./routeDerive";
import { nextRule, rulePhrase } from "./rules";
import { hazardPhrase, nextHazard, type Hazard } from "./context";
import type { Priority, RoutePlan, VerdictStyle } from "./types";

// ★ 내보내지 않는다. 밖에서 쓸 일이 없고, `export` 면 번들러가 상수를
//   못 접어 진입 청크가 는다(`naviweight` 래칫 137KB). 문턱의 **뜻**은
//   `reachOf` 가 내보내고 시험은 그것을 문다.
/** 판정 안내를 이만큼 앞에서 미리 낸다(초). */
const VERDICT_AHEAD_SEC = 7;
const VERDICT_MIN_M = 40;
/** 주변 사정은 이보다 멀면 안 말한다 — 멀리서 말하면 어느 것인지 모른다. */
const HAZARD_MAX_M = 60;

/** 한 틱의 입력. **훅이 이미 계산한 것만 받는다.** */
export interface VoiceTick {
  enabled: boolean;
  offRoute: boolean;
  plan: RoutePlan | null;
  /** 경로 시작부터 온 거리(m) */
  driven: number | null;
  /** 지수 평활한 속도(m/s). 문턱이 여기 비례한다 */
  speed: number;
  /** 다음 회전 · 그 다음 · 남은 거리 */
  m: Maneuver | null;
  after: Maneuver | null;
  distM: number | null;
  style: Record<string, VerdictStyle>;
  hazards?: readonly Hazard[];
  /**
   * 앞 구간의 영상 소견. **훅이 `cv.fold()` 로 접어서 준다** — 이 파일은
   * 나이도 신뢰도도 안 센다(§363). `null`·`undefined` 면 영상이 없는 것이고,
   * 그때 이 함수는 **오늘과 한 글자도 다르지 않다.**
   */
  cv?: { view: CvView; blocked: boolean } | null;
}

/** 틱을 넘어 사는 기억. 훅의 `useRef` 들이다. */
export interface VoiceMemory {
  /** 회전 자리(atM) → 그 자리에서 **가장 안쪽까지** 말한 문턱 */
  gate: Map<number, number>;
  /** 마지막으로 말한 회색 구간 */
  verdict: string | null;
  /** 이미 말한 규칙 · 사정의 열쇠 */
  said: Set<string>;
  /** 직전 틱이 이탈이었나 — 이탈 안내는 **들어갈 때 한 번**이다 */
  wasOff: boolean;
}

export function newMemory(): VoiceMemory {
  return { gate: new Map(), verdict: null, said: new Set(), wasOff: false };
}

export interface Utterance {
  text: string;
  urgency: Priority;
}

/** 재동기화가 낼 말. 문턱을 **안 기다린다**(§213-2). */
export function resync(t: VoiceTick, mem: VoiceMemory): Utterance | null {
  mem.gate.clear();
  mem.verdict = null;
  mem.said.clear();
  if (!t.enabled || t.offRoute) return null;
  if (!t.m || t.distM == null) return null;
  // ★ 문턱 기록을 **먼저** 채운다. 안 채우면 같은 렌더의 본 걸음이 같은 말을
  //   한 번 더 한다 — 훅에서 효과 선언 순서로 지키던 규칙이고, 여기서는
  //   같은 함수 안이라 순서가 눈에 보인다.
  mem.gate.set(t.m.atM, Math.max(0, gateIndex(t.distM, t.speed)));
  return { text: mergePhrase(t.m, t.after, t.distM), urgency: "critical" };
}

/** 내다볼 거리(m). 정지 상태에서 0 이 되지 않게 하한을 둔다. */
export function reachOf(speed: number): number {
  return Math.max(VERDICT_MIN_M, speed * VERDICT_AHEAD_SEC);
}

/**
 * 한 걸음. 말할 것 하나를 내고 **기억을 제자리에서 옮긴다.**
 *
 * ★ 아무것도 안 말하는 것이 기본이다. 내비는 조용한 것이 정상이고,
 *   말할 때만 말한다.
 */
/**
 * 영상 소견 하나를 말로. 이미 말한 측정이면 `null`.
 *
 * ★ **같은 측정은 한 번만.** 새 측정이 오면 `at` 이 달라 다시 말한다 —
 *   열쇠에 시각을 넣는 이유가 그것이다. 구간만 넣으면 그 골목에서 영영
 *   한 번만 말하고, 차가 빠져 넓어진 것도 안 말한다.
 */
function cvSay(cv: { view: CvView; blocked: boolean }, mem: VoiceMemory): Utterance | null {
  const u = urgencyOf(cv.blocked, cv.view.age);
  if (!u) return null;
  const text = cvPhrase(cv.view, cv.blocked);
  if (!text) return null;
  const k = `cv:${cv.view.seg}@${cv.view.at}`;
  if (mem.said.has(k)) return null;
  mem.said.add(k);
  return { text, urgency: u === "critical" ? "critical" : "rule" };
}

export function step(t: VoiceTick, mem: VoiceMemory): Utterance | null {
  if (!t.enabled) return null;

  // ── 이탈이 최우선 ────────────────────────────────────────────
  if (t.offRoute) {
    if (mem.wasOff) return null;
    mem.wasOff = true;
    return { text: "경로를 벗어났습니다. 재탐색합니다.", urgency: "critical" };
  }
  mem.wasOff = false;

  // ── 영상이 **막았을 때만** 회전보다 앞이다 (§363) ────────────
  //   막지 않은 소견은 「가 봐야 아는 것」이라 규칙과 같은 단이고, 아래에서
  //   회전 뒤에 낸다. 여기서 둘을 같이 내보내면 **회전이 영영 안 나간다.**
  if (t.cv?.blocked) {
    const u = cvSay(t.cv, mem);
    if (u) return u;
  }

  // ── 회전. 문턱이 속도에 비례한다 ─────────────────────────────
  if (t.m && t.distM != null) {
    // ★ **가장 안쪽 문턱**을 고른다. 바깥 문턱부터 맞추면 「실행(2.5초 전)」
    //   자리에서도 「먼저 알림」으로 세어져, 한 번 말한 뒤로는 실행 안내가
    //   영영 안 나간다. 그 결함이 실제로 있었다.
    const gate = gateIndex(t.distM, t.speed);
    if (gate >= 0) {
      const prev = mem.gate.get(t.m.atM);
      if (prev == null || gate > prev) {
        mem.gate.set(t.m.atM, gate);
        return { text: mergePhrase(t.m, t.after, t.distM), urgency: "turn" };
      }
    }
  }

  if (!t.plan || t.driven == null) return null;
  const reach = reachOf(t.speed);

  // ── 영상(안 막음). 규칙과 같은 단이다 ────────────────────────
  if (t.cv && !t.cv.blocked) {
    const u = cvSay(t.cv, mem);
    if (u) return u;
  }

  // ── 통행 규칙. 판정보다 앞이다 ───────────────────────────────
  const rule = nextRule(t.plan.rules, t.driven, reach);
  if (rule) {
    const k = `${rule.kind}@${rule.atM.toFixed(0)}`;
    if (!mem.said.has(k)) {
      mem.said.add(k);
      return {
        text: rulePhrase(rule),
        urgency: rule.kind === "wrong_way" ? "critical" : "rule",
      };
    }
  }

  // ── 주변 사정. 규칙 다음, 판정 앞 ────────────────────────────
  const hz = nextHazard(
    t.hazards ?? [], t.driven,
    t.hazards?.length ? Math.min(reach, HAZARD_MAX_M) : 0,
  );
  if (hz) {
    const k = `hz-${hz.kind}@${hz.atM.toFixed(0)}`;
    if (!mem.said.has(k)) {
      mem.said.add(k);
      return { text: hazardPhrase(hz), urgency: "notice" };
    }
  }

  // ── 판정. 회색 구간에만, 진입 **전에** ───────────────────────
  const ahead = lookAhead(t.plan, t.driven, reach);
  if (!ahead) return null;
  if (ahead.verdict !== "needs_cv" && ahead.verdict !== "unknown") return null;
  if (ahead.seg_uid === mem.verdict) return null;

  mem.verdict = ahead.seg_uid;
  const label = t.style[ahead.verdict]?.label ?? ahead.verdict;
  const w = ahead.width_min_m != null
    ? ` 폭 ${ahead.width_min_m.toFixed(1)}미터.` : "";
  // ★ §215-2. 회색은 **왜** 회색인지 한 마디 붙인다 — 카메라가 없어서인지가
  //   운전자에게 제일 쓸모 있다.
  const why = ahead.verdict === "unknown"
    && ahead.unknown_reason?.startsWith("no_cctv") ? " CCTV 없음." : "";
  return { text: `잠시 후 ${label} 구간.${w}${why}`, urgency: "notice" };
}
