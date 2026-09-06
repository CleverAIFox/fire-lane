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

export type Priority = "critical" | "normal";

export interface Speaker {
  readonly available: boolean;
  readonly koVoice: boolean;
  readonly enabled: boolean;
  /**
   * 말한다.
   * @param priority "critical" 이면 큐를 비우고 즉시 말한다(이탈 등).
   *   "normal" 은 재생 중이면 큐에 넣는다 — **자르지 않는다.**
   */
  say(text: string, priority?: Priority): void;
  cancel(): void;
  setEnabled(on: boolean): void;
}

export function createSpeaker(): Speaker {
  const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
  let enabled = true;
  let ko: SpeechSynthesisVoice | null = null;
  let speaking = false;
  const queue: string[] = [];

  const pick = () => {
    if (!synth) return;
    const vs = synth.getVoices();
    ko = vs.find((v) => v.lang === "ko-KR")
      ?? vs.find((v) => v.lang?.startsWith("ko")) ?? null;
  };
  if (synth) {
    pick();
    // 음성 목록은 비동기로 채워진다. 한 번 더 잡는다.
    synth.onvoiceschanged = pick;
    // ★ Chrome 이 합성기를 멈추는 버그. 주기적으로 깨운다.
    setInterval(() => {
      if (synth.speaking && !synth.paused) { synth.pause(); synth.resume(); }
    }, 8000);
  }

  const drain = () => {
    if (!synth || !enabled || speaking) return;
    const text = queue.shift();
    if (!text) return;
    speaking = true;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR";
    if (ko) u.voice = ko;
    u.rate = 1.0;
    u.onend = u.onerror = () => { speaking = false; drain(); };
    synth.speak(u);
  };

  return {
    get available() { return !!synth; },
    get koVoice() { return !!ko; },
    get enabled() { return enabled; },
    setEnabled(on) {
      enabled = on;
      if (!on) { queue.length = 0; speaking = false; synth?.cancel(); }
    },
    cancel() {
      queue.length = 0; speaking = false; synth?.cancel();
    },
    say(text, priority = "normal") {
      if (!synth || !enabled || !text) return;
      if (priority === "critical") {
        queue.length = 0;
        synth.cancel();
        speaking = false;
      } else if (queue.includes(text)) {
        return;                     // 같은 안내가 대기 중이면 넣지 않는다
      } else if (queue.length >= 2) {
        // 밀린 안내는 버린다. 지난 안내를 늦게 듣는 것은 방해다.
        queue.shift();
      }
      queue.push(text);
      drain();
    },
  };
}
