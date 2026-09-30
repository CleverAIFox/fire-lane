/**
 * infra/speech.ts — 음성 합성. Web Speech API 래퍼.
 *
 * ── 왜 SDK 를 안 쓰나 ───────────────────────────────────────────
 * `speechSynthesis` 는 브라우저 내장이고 한국어를 지원한다. 공짜이고
 * 오프라인에서도 돈다. 상용 SDK 가 필요한 이유는 음성이 아니라 회전
 * 안내 문구를 만들 데이터인데, 그것은 `domain/turn.ts` 가 우리 그래프에서
 * 직접 낸다(2026-09-05).
 *
 * ── ★ 왜 끊겼나 (2026-09-05) ────────────────────────────────────
 * 세 가지가 겹쳤다.
 *
 *   ① 말할 때마다 `cancel()` 을 불렀다. cancel 은 **재생 중인 발화를
 *      즉시 잘라낸다.** 안내가 겹칠 일이 없는데도 매번 잘랐다.
 *   ② 큐가 없어서 짧은 간격의 두 안내가 서로를 지웠다. 동명동은 회전
 *      간격 중앙이 64m 라 이 일이 계속 일어난다.
 *   ③ Chrome 은 발화가 길거나 오래 쉬면 합성기가 멈춘다(알려진 버그).
 *      `resume()` 을 주기적으로 불러야 살아난다.
 *
 * ★ **아이내비 시절에는 TTS 를 안 썼다.** 성우 녹음 조각을 이어붙였다 —
 *   내비 어휘는 닫힌 집합이라 200개면 된다. 우리도 품질이 더 필요하면
 *   그 길이 있다. 지금은 정책을 먼저 고친다.
 */

/**
 * 안내의 **급함**. 큐가 밀리면 이 순서로 버린다.
 *
 * ★ 2026-09-29 (DECISIONS §301). 종전에는 `critical | normal` 둘이었고
 *   `normal` 끼리는 **도착 순서로** 버렸다 — 큐가 둘을 넘으면 가장 오래된 것을
 *   밀어냈다. 그래서 **회전 실행 안내가 판정 안내 때문에 버려질 수 있었다.**
 *   둘 다 `normal` 이기 때문이다. 버리는 기준이 「언제 왔나」였고 「얼마나
 *   급한가」가 아니었다.
 *
 *   turn      회전 · 이탈 — 놓치면 길을 잘못 든다
 *   rule      통행 규칙 — 놓치면 역주행한다
 *   notice    판정 · 주변 사정 — 놓쳐도 운전은 된다
 */
// ★ 2026-09-30 (§329). 타입의 집은 `domain/types.ts` 다 — 여기서 다시
//   선언하면 정본이 둘이 된다. **뜻은 아래 `RANK` 가 든다.**
export type { Priority } from "../domain/types";
import type { Priority } from "../domain/types";

/** 급한 순서. 큰 수가 급하다. `normal` 은 종전 호출부를 위해 `notice` 와 같다. */
export const RANK: Readonly<Record<Priority, number>> = {
  critical: 3, turn: 2, rule: 1, notice: 0, normal: 0,
};

export interface Speaker {
  readonly available: boolean;
  readonly koVoice: boolean;
  readonly enabled: boolean;
  /**
   * 말한다.
   * @param priority `critical` 은 큐를 비우고 **말하던 것을 자르고** 즉시 말한다.
   *   나머지는 재생 중이면 큐에 넣고 **자르지 않는다.** 큐가 밀리면
   *   `RANK` 가 낮은 것부터 버린다 — 도착 순서가 아니다(§301).
   */
  say(text: string, priority?: Priority): void;
  cancel(): void;
  setEnabled(on: boolean): void;
  /**
   * 합성기를 놓는다. 깨우기 타이머를 끄고 말하던 것을 멈춘다.
   *
   * ★ 2026-09-24 (PLAN §13 W13-5). 종전에는 이것이 **없었고** 깨우기
   *   `setInterval` 의 핸들도 안 잡았다 — 페이지 수명 내내 못 끄는 타이머가
   *   하나(StrictMode 개발 모드에서는 둘) 돌았다.
   */
  dispose(): void;
}

export function createSpeaker(): Speaker {
  const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
  let enabled = true;
  let ko: SpeechSynthesisVoice | null = null;
  let speaking = false;
  /** ★ §301. 글만 담으면 급함을 모르고, 모르면 도착 순서로 버릴 수밖에 없다. */
  const queue: { text: string; rank: number }[] = [];
  /** 지금 말하는 것의 급함. 더 급한 것이 오면 자른다. */
  let nowRank = -1;
  /**
   * 지금 말하는 **글**. 중복 제거가 이것을 봐야 한다.
   *
   * ★ 2026-09-29 (§301-2). 종전 중복 제거는 `queue` 만 봤다. 재생에 들어간 문장은
   *   큐에서 빠졌으므로, 같은 문장이 한 번 더 오면 **또 큐에 들어가 두 번 나갔다.**
   *   시험을 쓰자마자 잡혔다 — 이 파일에 시험이 없어서 그동안 안 보였다(W13-5).
   */
  let nowText: string | null = null;

  const pick = () => {
    if (!synth) return;
    const vs = synth.getVoices();
    ko = vs.find((v) => v.lang === "ko-KR")
      ?? vs.find((v) => v.lang?.startsWith("ko")) ?? null;
  };
  let wake = 0;
  if (synth) {
    pick();
    // 음성 목록은 비동기로 채워진다. 한 번 더 잡는다.
    synth.onvoiceschanged = pick;
    // ★ Chrome 이 합성기를 멈추는 버그. 주기적으로 깨운다.
    //   핸들을 잡는다 — 못 끄는 타이머는 누수다(W13-5).
    wake = window.setInterval(() => {
      if (synth.speaking && !synth.paused) { synth.pause(); synth.resume(); }
    }, 8000);
  }

  const drain = () => {
    if (!synth || !enabled || speaking) return;
    // ★ §301. **가장 급한 것부터** 낸다. 같은 급함이면 먼저 온 것부터.
    let at = 0;
    for (let k = 1; k < queue.length; k += 1) {
      if (queue[k].rank > queue[at].rank) at = k;
    }
    const item = queue.splice(at, 1)[0];
    if (!item) return;
    const { text } = item;
    nowRank = item.rank;
    nowText = text;
    speaking = true;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR";
    if (ko) u.voice = ko;
    u.rate = 1.0;
    u.onend = u.onerror = () => {
      speaking = false; nowRank = -1; nowText = null; drain();
    };
    synth.speak(u);
  };

  return {
    get available() { return !!synth; },
    get koVoice() { return !!ko; },
    get enabled() { return enabled; },
    setEnabled(on) {
      enabled = on;
      if (!on) { queue.length = 0; speaking = false; nowRank = -1; nowText = null; synth?.cancel(); }
    },
    cancel() {
      queue.length = 0; speaking = false; nowRank = -1; synth?.cancel();
    },
    dispose() {
      if (wake) { clearInterval(wake); wake = 0; }
      queue.length = 0; speaking = false; nowRank = -1; nowText = null; enabled = false;
      if (synth) { synth.onvoiceschanged = null; synth.cancel(); }
    },
    say(text, priority = "normal") {
      if (!synth || !enabled || !text) return;
      const rank = RANK[priority] ?? 0;
      if (priority === "critical") {
        queue.length = 0;
        synth.cancel();
        speaking = false;
        nowRank = -1;
        nowText = null;
      } else if (text === nowText || queue.some((q) => q.text === text)) {
        return;     // 같은 안내가 **재생 중이거나** 대기 중이면 넣지 않는다(§301-2)
      } else if (speaking && rank > nowRank) {
        // ★ §301-1. **더 급한 것이 오면 자른다.** 2026-09-05 에 「말할 때마다
        //   cancel 을 불렀다」를 고쳤는데(안 겹치는데도 매번 잘랐다) 그때 자르기를
        //   **전부** 없앴다. 그래서 「300m 앞 우회전」이 재생되는 3초 동안 실행
        //   문턱(2.5초 전)이 지나가면 「우회전입니다」가 뒤에 붙어 **늦게** 나갔다.
        //   시속 30km 에서 2.5초는 21m 다 — 회전을 지나서 말하는 것이다.
        //   ★ 조건이 좁다. **엄격히 더 급할 때만** 자른다. 같은 급함끼리는 안 자른다.
        synth.cancel();
        speaking = false;
        nowRank = -1;
        nowText = null;
      } else if (queue.length >= 2) {
        // ★ §301. 밀린 안내는 버린다 — 지난 안내를 늦게 듣는 것은 방해다.
        //   다만 **가장 안 급한 것**을 버린다. 종전에는 가장 오래된 것을 버려
        //   회전 실행 안내가 판정 안내에 밀려나갔다.
        let worst = 0;
        for (let k = 1; k < queue.length; k += 1) {
          if (queue[k].rank < queue[worst].rank) worst = k;
        }
        // 새로 온 것이 큐의 어느 것보다도 안 급하면 **새 것을 버린다.**
        if (queue[worst].rank > rank) { drain(); return; }
        queue.splice(worst, 1);
      }
      queue.push({ text, rank });
      drain();
    },
  };
}
