/**
 * voice.test.ts — **한 틱에 무엇을 말하는가.** 우선순위 사슬.
 * (PLAN §13 W13-5 · DECISIONS §329 · `src/domain/voice.ts`)
 *
 * ── 왜 이 파일이 생겼나 (2026-09-30) ────────────────────────────
 * 이 사슬은 `app/useVoice.ts` 의 `useEffect` 안에 살았다. 값은 **정책**인데
 * 자리가 React 라, 물으려면 렌더러가 있어야 했고 `vitest` 환경은 `node` 다.
 * **정책 하나를 물자고 의존성을 늘리는 대신 정책을 내렸다.**
 *
 * 그 사슬이 이 앱에서 제일 값이 큰 판단이다 —
 *
 *     이탈 > 재동기화 > 회전 > 규칙 > 사정 > 판정
 *
 * 순서가 한 칸만 어긋나도 **회전 실행 안내가 판정 안내에 밀린다.** 밀리면
 * 길을 잘못 들고, 잘못 들면 그 뒤의 안내는 전부 엉뚱한 자리의 말이 된다.
 * 이 사슬은 세 번 고쳐졌고(§213-2 재동기화 · §215-1 규칙 · §216-3 사정)
 * **세 번 다 시험 없이 고쳤다.**
 *
 * ★ 잠그는 것은 **순서와 한 번뿐임**이다. 문구가 예쁜지는 안 본다 — 문구는
 *   `mergePhrase` · `rulePhrase` · `hazardPhrase` 가 각자 들고 그쪽에
 *   시험이 있다.
 * ★ 밖 — **급함의 뜻은 안 본다.** 무엇을 먼저 버리고 무엇이 자르는가는
 *   발화기의 `RANK` 이고 `speech.test.ts` 가 든다. 여기는 자리마다 옳은
 *   이름을 붙였는가만 본다.
 */
import { beforeEach, describe, expect, it } from "vitest";
import { newMemory, reachOf, resync, step, type VoiceMemory, type VoiceTick }
  from "../src/domain/voice";
import { fold as foldCv, type CvReading } from "../src/domain/cv";
import { GATES_MIN_M, type Maneuver } from "../src/domain/turn";
import type { GraphEdge, RoutePlan, RuleWarning, VerdictStyle }
  from "../src/domain/types";

const STYLE: Record<string, VerdictStyle> = {
  needs_cv: { label: "판정 보류" } as VerdictStyle,
  unknown: { label: "영상판정 불가" } as VerdictStyle,
};

function edge(o: Partial<GraphEdge> = {}): GraphEdge {
  return {
    seg_uid: "S1", verdict: "clear", width_min_m: 5, length_m: 100, ...o,
  } as GraphEdge;
}

function plan(edges: GraphEdge[], rules: RuleWarning[] = []): RoutePlan {
  return {
    edges, forward: edges.map(() => true), nodes: [], coords: [],
    cost: 0, lengthM: edges.reduce((a, e) => a + (e.length_m ?? 0), 0),
    byVerdict: {}, rules,
  } as RoutePlan;
}

/**
 * 앞에 회색 구간이 있는 경로.
 *
 * ★ `lookAhead` 는 **지금 달리는 구간을 안 돌려준다** — 「진입 전에 말한다」가
 *   목적이라 그렇다. 그래서 첫 구간을 짧게 깔고 그 다음에 물을 것을 둔다.
 *   한 구간짜리로 물으면 **언제나 `null`** 이고, 시험은 조용히 초록이 된다.
 */
function ahead(e: GraphEdge, rules: RuleWarning[] = []): RoutePlan {
  return plan([edge({ seg_uid: "HERE", length_m: 30 }), e], rules);
}

function maneuver(atM: number): Maneuver {
  return { atM, kind: "left", deltaDeg: -80, forks: 3, edge: null, roadName: null };
}

/** 아무것도 말할 것이 없는 평온한 틱. 시험마다 필요한 것만 얹는다. */
function calm(o: Partial<VoiceTick> = {}): VoiceTick {
  return {
    enabled: true, offRoute: false, plan: plan([edge()]), driven: 0,
    speed: 10, m: null, after: null, distM: null, style: STYLE, ...o,
  };
}

let mem: VoiceMemory;
beforeEach(() => { mem = newMemory(); });

describe("조용한 것이 기본이다", () => {
  it("말할 것이 없으면 아무 말도 안 한다", () => {
    expect(step(calm(), mem)).toBeNull();
  });

  it("꺼져 있으면 무엇이 있어도 안 말한다", () => {
    const t = calm({ enabled: false, offRoute: true, m: maneuver(100), distM: 20 });
    expect(step(t, mem)).toBeNull();
    // ★ 기억도 안 움직인다 — 꺼진 동안 「말했다」고 적히면 켜자마자 침묵한다.
    expect(mem.wasOff).toBe(false);
    expect(mem.gate.size).toBe(0);
  });
});

describe("이탈이 최우선", () => {
  it("회전이 코앞이어도 이탈을 먼저 말한다", () => {
    const t = calm({ offRoute: true, m: maneuver(100), distM: 5 });
    expect(step(t, mem)?.text).toContain("벗어났습니다");
    // ★ 이탈 안내는 **들어갈 때 한 번**이다. 매 틱 반복하면 재탐색 동안
    //   다른 말이 아무것도 못 나간다.
    expect(step(t, mem)).toBeNull();
  });

  it("돌아오면 다시 말할 수 있다", () => {
    const off = calm({ offRoute: true });
    step(off, mem);
    step(calm(), mem);                               // 경로 복귀
    expect(step(off, mem)?.text).toContain("벗어났습니다");
  });

  it("이탈은 critical 이다", () => {
    expect(step(calm({ offRoute: true }), mem)?.urgency).toBe("critical");
  });
});

describe("회전", () => {
  const near = (d: number) => calm({ m: maneuver(1000), distM: d });

  it("문턱 안이면 말한다", () => {
    expect(step(near(GATES_MIN_M[0]), mem)).not.toBeNull();
  });

  it("문턱 밖이면 안 말한다", () => {
    expect(step(calm({ m: maneuver(9999), distM: 5000 }), mem)).toBeNull();
  });

  it("같은 문턱에서 두 번 말하지 않는다", () => {
    expect(step(near(110), mem)).not.toBeNull();
    expect(step(near(110), mem)).toBeNull();
  });

  it("★ 더 안쪽 문턱에 들어가면 다시 말한다", () => {
    // 종전 결함 — 바깥 문턱부터 맞추는 바람에 실행 안내가 영영 안 나갔다.
    expect(step(near(110), mem)).not.toBeNull();   // 먼저 알림 (문턱 120)
    expect(step(near(50), mem)).not.toBeNull();    // 준비      (문턱 60)
    expect(step(near(20), mem)).not.toBeNull();    // 실행      (문턱 25)
  });

  it("회전이 판정을 이긴다", () => {
    const t = calm({
      m: maneuver(1000), distM: 100,
      plan: ahead(edge({ verdict: "needs_cv", seg_uid: "G1" })),
    });
    expect(step(t, mem)?.urgency).toBe("turn");
    // ★ 그리고 회색 구간을 **안 삼켰다** — 다음 틱에 나온다.
    expect(step({ ...t, m: null, distM: null }, mem)?.text).toContain("판정 보류");
  });
});

describe("규칙이 판정보다 앞이다", () => {
  const rule = (kind: RuleWarning["kind"]): RuleWarning =>
    ({ kind, atM: 10, seg_uid: "S1", text: "" });

  it("역주행은 critical 이다 — 들어가 봐야 아는 것이라", () => {
    const t = calm({ plan: ahead(edge({ verdict: "needs_cv" }), [rule("wrong_way")]) });
    const u = step(t, mem);
    expect(u?.urgency).toBe("critical");
    expect(u?.text).toContain("역주행");
  });

  it("그 밖의 규칙은 rule 이다", () => {
    const t = calm({ plan: ahead(edge(), [rule("oneway_unknown")]) });
    expect(step(t, mem)?.urgency).toBe("rule");
  });

  it("같은 규칙을 두 번 말하지 않는다", () => {
    const t = calm({ plan: ahead(edge(), [rule("oneway_unknown")]) });
    expect(step(t, mem)).not.toBeNull();
    expect(step(t, mem)).toBeNull();
  });
});

describe("주변 사정", () => {
  const hz = [{ kind: "speedbump" as const, atM: 20, at: [0, 0] as [number, number], text: "" }];

  it("가까우면 한 번 말한다", () => {
    const t = calm({ hazards: hz });
    expect(step(t, mem)?.urgency).toBe("notice");
    expect(step(t, mem)).toBeNull();
  });

  it("★ 멀면 안 말한다 — 멀리서 말하면 어느 것인지 모른다", () => {
    const far = [{ ...hz[0], atM: 400 }];
    expect(step(calm({ hazards: far, speed: 40 }), mem)).toBeNull();
  });

  it("사정이 판정보다 앞이다", () => {
    const t = calm({ hazards: hz, plan: ahead(edge({ verdict: "unknown" })) });
    expect(step(t, mem)?.text).toContain("과속방지턱");
  });
});

describe("판정 안내", () => {
  it("회색 구간만 말한다", () => {
    expect(step(calm({ plan: ahead(edge({ verdict: "clear" })) }), mem)).toBeNull();
    expect(step(calm({ plan: ahead(edge({ verdict: "blocked" })) }), mem)).toBeNull();
  });

  it("폭을 붙인다", () => {
    const t = calm({ plan: ahead(edge({ verdict: "needs_cv", width_min_m: 3.24 })) });
    expect(step(t, mem)?.text).toBe("잠시 후 판정 보류 구간. 폭 3.2미터.");
  });

  it("★ 회색은 왜 회색인지 한 마디 붙인다", () => {
    const t = calm({
      plan: ahead(edge({
        verdict: "unknown", width_min_m: null, unknown_reason: "no_cctv_band",
      })),
    });
    expect(step(t, mem)?.text).toContain("CCTV 없음");
  });

  it("같은 구간을 두 번 말하지 않는다", () => {
    const t = calm({ plan: ahead(edge({ verdict: "needs_cv", seg_uid: "G9" })) });
    expect(step(t, mem)).not.toBeNull();
    expect(step(t, mem)).toBeNull();
  });
});

describe("재동기화 — 문턱을 안 기다린다", () => {
  it("순간이동한 자리의 다음 회전을 바로 말한다", () => {
    // 문턱 밖(2,000m)인데도 말한다. 터널을 나오며 상용 내비가 하는 일이다.
    const u = resync(calm({ m: maneuver(5000), distM: 2000 }), mem);
    expect(u?.urgency).toBe("critical");
  });

  it("★ 말한 뒤 같은 틱의 본 걸음이 같은 말을 또 하지 않는다", () => {
    const t = calm({ m: maneuver(1000), distM: 100 });
    expect(resync(t, mem)).not.toBeNull();
    expect(step(t, mem)).toBeNull();
  });

  it("기억을 비운다 — 끊긴 동안의 판단은 못 믿는다", () => {
    step(calm({ plan: ahead(edge({ verdict: "needs_cv", seg_uid: "G9" })) }), mem);
    expect(mem.verdict).toBe("G9");
    resync(calm(), mem);
    expect(mem.verdict).toBeNull();
    expect(mem.said.size).toBe(0);
  });

  it("꺼져 있거나 이탈 중이면 말하지 않는다 — 그래도 기억은 비운다", () => {
    mem.verdict = "G9";
    expect(resync(calm({ enabled: false, m: maneuver(1), distM: 1 }), mem)).toBeNull();
    expect(mem.verdict).toBeNull();
    expect(resync(calm({ offRoute: true, m: maneuver(1), distM: 1 }), mem)).toBeNull();
  });
});

describe("내다보는 거리", () => {
  it("정지 상태에서도 0 이 아니다", () => {
    expect(reachOf(0)).toBeGreaterThan(0);
  });

  it("속도에 비례해 는다", () => {
    expect(reachOf(30)).toBeGreaterThan(reachOf(10));
  });
});

// ── 영상이 회전을 밀어내는가 (DECISIONS §363) ───────────────────────
describe("영상 통과폭", () => {
  const NOW = 1_800_000_000_000;
  const view = (o: Partial<CvReading> = {}) =>
    foldCv([{ t: "cv", seg: "DM-1", passM: 2.1, at: NOW, cam: "C1", conf: 0.9, ...o }],
           NOW).get("DM-1")!;

  it("★ 막은 측정이 **회전을 밀어낸다** — 회전은 되돌릴 수 있고 후진은 아니다", () => {
    const t = calm({ m: maneuver(100), distM: 20, cv: { view: view(), blocked: true } });
    const u = step(t, mem);
    expect(u?.urgency).toBe("critical");
    expect(u?.text).toContain("못 지납니다");
  });

  it("안 막은 측정은 **회전에 진다** — 회전이 먼저 나간다", () => {
    const t = calm({ m: maneuver(100), distM: 20, cv: { view: view(), blocked: false } });
    expect(step(t, mem)?.urgency).toBe("turn");
  });

  it("같은 측정을 두 번 안 말한다", () => {
    const v = view();
    expect(step(calm({ cv: { view: v, blocked: true } }), mem)).not.toBeNull();
    expect(step(calm({ cv: { view: v, blocked: true } }), mem)).toBeNull();
  });

  it("새 측정이 오면 다시 말한다 — `at` 이 다르다", () => {
    expect(step(calm({ cv: { view: view(), blocked: true } }), mem)).not.toBeNull();
    const next = { view: view({ at: NOW + 1_000 }), blocked: true };
    expect(step(calm({ cv: next }), mem)).not.toBeNull();
  });

  it("★ 이탈이 여전히 최우선이다 — 영상이 그것을 못 민다", () => {
    const t = calm({ offRoute: true, cv: { view: view(), blocked: true } });
    expect(step(t, mem)?.text).toContain("경로를 벗어났습니다");
  });

  it("★ 영상이 없으면 **오늘과 한 글자도 다르지 않다**", () => {
    const withCv = calm({ m: maneuver(100), distM: 20, cv: null });
    const m2 = newMemory();
    expect(step(withCv, mem)).toEqual(step(calm({ m: maneuver(100), distM: 20 }), m2));
  });

  it("안 막은 소견은 **규칙과 같은 단**이다 — 회전이 지나간 뒤에 나온다", () => {
    const t = calm({ cv: { view: view(), blocked: false } });
    expect(step(t, mem)?.urgency).toBe("rule");
  });

  it("낡은 측정은 접히지도 않는다 — 훅이 `cv` 를 못 만든다", () => {
    expect(foldCv(
      [{ t: "cv", seg: "DM-1", passM: 2.1, at: NOW - 10_000_000, cam: "C1", conf: 0.9 }],
      NOW,
    ).size).toBe(0);
  });
});
