/**
 * speech.test.ts — 안내가 **급한 순서로** 나가는가.  (DECISIONS §301 · PLAN W13-5)
 *
 * ── 왜 이 파일이 생겼나 (2026-09-29) ────────────────────────────
 * `infra/speech.ts` 는 119줄이고 **시험이 하나도 없었다.** 내비 시험 14개 파일
 * 102개 중 발화기를 보는 것이 0이다 — W13-5 가 「React · infra 층에 시험이 없다」
 * 고 적은 그 자리다.
 *
 * 그동안 이 파일이 세 번 고쳐졌고(2026-09-05 큐 도입 · 09-24 `setEnabled` 배선 ·
 * 09-24 `dispose`) **세 번 다 시험 없이 고쳤다.** 그래서 09-29 에 남아 있던 결함을
 * 읽어서야 찾았다 — 큐가 밀릴 때 **도착 순서로** 버려서 회전 실행 안내가 판정
 * 안내에 밀려나갈 수 있었다.
 *
 * ★ 여기 잠그는 것은 **정책**이다. 브라우저 합성기의 소리는 재지 않는다 —
 *   `speechSynthesis` 를 가짜로 세우고 **무엇을 어떤 순서로 넘겼는가**만 본다.
 *   소리를 재려면 사람이 들어야 하고, 그것은 시험이 할 일이 아니다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createSpeaker, RANK } from "../src/infra/speech";

/** 가짜 합성기. **말한 순서**와 자른 횟수를 남긴다. */
function fakeSynth() {
  const spoken: string[] = [];
  let cancels = 0;
  let pending: { onend?: () => void } | null = null;
  const synth = {
    speaking: false,
    paused: false,
    onvoiceschanged: null as null | (() => void),
    getVoices: () => [{ lang: "ko-KR", name: "ko" } as SpeechSynthesisVoice],
    speak(u: SpeechSynthesisUtterance) {
      spoken.push(u.text);
      synth.speaking = true;
      pending = u as unknown as { onend?: () => void };
    },
    cancel() {
      cancels += 1;
      synth.speaking = false;
      pending = null;
    },
    pause() {}, resume() {},
  };
  /** 재생이 끝났다고 알린다 — 큐가 다음 것을 낸다. */
  const finish = () => {
    const p = pending;
    pending = null;
    synth.speaking = false;
    p?.onend?.();
  };
  return { synth, spoken, finish, cancelCount: () => cancels };
}

let F: ReturnType<typeof fakeSynth>;

beforeEach(() => {
  F = fakeSynth();
  vi.stubGlobal("window", {
    speechSynthesis: F.synth,
    setInterval: () => 0,
    clearInterval: () => {},
  });
  vi.stubGlobal("SpeechSynthesisUtterance",
    class { text: string; lang = ""; voice = null; rate = 1;
            onend: (() => void) | null = null;
            onerror: (() => void) | null = null;
            constructor(t: string) { this.text = t; } });
});

// ── 급함의 순서가 선언돼 있다 ──────────────────────────────────

describe("급함", () => {
  it("이탈 > 회전 > 규칙 > 판정 순이다", () => {
    expect(RANK.critical).toBeGreaterThan(RANK.turn);
    expect(RANK.turn).toBeGreaterThan(RANK.rule);
    expect(RANK.rule).toBeGreaterThan(RANK.notice);
  });

  it("종전 호출부의 `normal` 이 살아 있다", () => {
    // 이 낱말을 쓰는 자리가 남아 있을 수 있다. 없는 키는 0 이 되어 조용히 제일
    // 안 급해지므로, **선언에 있는지**를 잰다.
    expect(RANK.normal).toBeDefined();
  });
});

// ── 큐가 밀릴 때 무엇을 버리는가 ────────────────────────────────

describe("큐가 밀릴 때", () => {
  it("가장 **안 급한** 것을 버린다 — 도착 순서가 아니다", () => {
    const s = createSpeaker();
    // ★ 같은 급함으로 시작해야 선점이 안 끼어들어 큐가 실제로 찬다
    s.say("첫 회전", "turn");            // 바로 재생에 들어간다
    s.say("판정 안내", "notice");        // 큐 1 — 제일 안 급하다
    s.say("우회전입니다", "turn");        // 큐 2
    s.say("좌회전입니다", "turn");        // 큐가 2였다 → **판정 안내**가 버려진다

    F.finish(); F.finish(); F.finish();
    expect(F.spoken).not.toContain("판정 안내");
    expect(F.spoken).toContain("우회전입니다");
    expect(F.spoken).toContain("좌회전입니다");
  });

  it("회전이 판정보다 먼저 나간다", () => {
    const s = createSpeaker();
    s.say("첫 문장", "notice");
    s.say("잠시 후 판정 보류 구간", "notice");
    s.say("우회전입니다", "turn");
    F.finish();                          // 첫 문장이 끝나고 큐에서 고른다
    expect(F.spoken[1]).toBe("우회전입니다");
  });

  it("새로 온 것이 큐의 모든 것보다 안 급하면 **새 것을 버린다**", () => {
    const s = createSpeaker();
    s.say("첫 회전", "turn");            // 재생
    s.say("우회전입니다", "turn");        // 큐 1
    s.say("좌회전입니다", "turn");        // 큐 2
    s.say("과속방지턱", "notice");       // 큐가 2였고 둘 다 더 급하다 → 새 것을 버린다
    F.finish(); F.finish(); F.finish();
    expect(F.spoken).not.toContain("과속방지턱");
    expect(F.spoken).toContain("우회전입니다");
    expect(F.spoken).toContain("좌회전입니다");
  });
});

// ── 자르기 ─────────────────────────────────────────────────────

describe("자르기", () => {
  it("더 급한 것이 오면 **자른다** — 늦은 회전 안내는 지나간 안내다", () => {
    const s = createSpeaker();
    s.say("300미터 앞 우회전", "notice");
    const before = F.cancelCount();
    s.say("우회전입니다", "turn");
    expect(F.cancelCount()).toBeGreaterThan(before);
    expect(F.spoken.at(-1)).toBe("우회전입니다");
  });

  it("같은 급함끼리는 **안 자른다** — 2026-09-05 에 고친 그 병이다", () => {
    const s = createSpeaker();
    s.say("우회전입니다", "turn");
    const before = F.cancelCount();
    s.say("좌회전입니다", "turn");
    expect(F.cancelCount()).toBe(before);
    expect(F.spoken).toEqual(["우회전입니다"]);   // 둘째는 큐에서 기다린다
  });

  it("덜 급한 것은 재생 중인 것을 **안 자른다**", () => {
    const s = createSpeaker();
    s.say("우회전입니다", "turn");
    const before = F.cancelCount();
    s.say("과속방지턱", "notice");
    expect(F.cancelCount()).toBe(before);
    expect(F.spoken).toEqual(["우회전입니다"]);
  });

  it("critical 은 큐를 비우고 자른다", () => {
    const s = createSpeaker();
    s.say("우회전입니다", "turn");
    s.say("좌회전입니다", "turn");
    s.say("경로를 벗어났습니다", "critical");
    expect(F.spoken.at(-1)).toBe("경로를 벗어났습니다");
    F.finish();
    // 큐가 비었으므로 뒤에 아무것도 안 나온다
    expect(F.spoken.at(-1)).toBe("경로를 벗어났습니다");
  });
});

// ── 종전 규율이 안 깨졌는가 ────────────────────────────────────

describe("종전 규율", () => {
  it("같은 문장이 대기 중이면 두 번 안 넣는다", () => {
    const s = createSpeaker();
    s.say("첫 회전", "turn");
    s.say("우회전입니다", "turn");
    s.say("우회전입니다", "turn");
    F.finish(); F.finish(); F.finish();
    expect(F.spoken.filter((x) => x === "우회전입니다")).toHaveLength(1);
  });

  it("같은 문장이 **재생 중**이어도 두 번 안 넣는다 (§301-2)", () => {
    // ★ 시험을 쓰자마자 잡힌 결함이다. 종전 중복 제거는 큐만 봤고, 재생에 들어간
    //   문장은 큐에서 빠졌으므로 같은 문장이 또 들어가 두 번 나갔다.
    const s = createSpeaker();
    s.say("우회전입니다", "turn");        // 바로 재생
    s.say("우회전입니다", "turn");        // 큐에는 없지만 재생 중이다
    F.finish(); F.finish();
    expect(F.spoken.filter((x) => x === "우회전입니다")).toHaveLength(1);
  });

  it("끄면 말하던 것을 멈추고 큐를 비운다 (W13-5)", () => {
    const s = createSpeaker();
    s.say("우회전입니다", "turn");
    s.say("좌회전입니다", "turn");
    s.setEnabled(false);
    const n = F.spoken.length;
    F.finish();
    expect(F.spoken).toHaveLength(n);   // 큐에 남은 것이 안 나간다
  });

  it("끈 뒤에는 새 안내도 안 나간다", () => {
    const s = createSpeaker();
    s.setEnabled(false);
    s.say("우회전입니다", "turn");
    expect(F.spoken).toHaveLength(0);
  });

  it("빈 글은 안 넣는다", () => {
    const s = createSpeaker();
    s.say("", "turn");
    expect(F.spoken).toHaveLength(0);
  });

  it("dispose 뒤에는 조용하다 — 못 끄는 타이머가 남으면 누수다", () => {
    const s = createSpeaker();
    s.dispose();
    s.say("우회전입니다", "turn");
    expect(F.spoken).toHaveLength(0);
  });
});
