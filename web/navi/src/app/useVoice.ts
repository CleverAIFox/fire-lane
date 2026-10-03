/**
 * app/useVoice.ts — **무엇을 언제 말할 것인가.** TBT 의 본체다.
 *
 * ══ 상용 내비를 그대로 모사하고, 우리 것만 얹는다 ══════════════
 *   상용 그대로   분기 있는 곳에서만 안내 · 거리 문턱 · 연속 회전 병합
 *                 이탈 시 즉시
 *   우리 것       "잠시 후 판정 보류 구간. 폭 3.2미터"
 *
 * ── ★ 문턱을 **시간**으로 잡는다 ────────────────────────────────
 * 2026-09-06. 거리 문턱(150·60·20m)을 고정했다가 안내가 늦었다.
 * 시속 30km 에서 150m 는 18초 전이지만 **시속 144km 시뮬레이션에서는
 * 3.7초 전**이다 — 말이 끝나기도 전에 회전이 온다.
 *
 * 상용은 시간으로 잡는다. 우리도 그렇게 한다 —
 *
 *     먼저 알림   12초 전   (최소 80m · 최대 250m)
 *     준비        6초 전    (최소 40m)
 *     실행        2.5초 전  (최소 15m)
 *
 * 하한을 두는 이유는 정지 상태(속도 0)에서 문턱이 0 이 되기 때문이다.
 *
 * ── ★ 판정 안내는 진입 **전에** ─────────────────────────────────
 * 회색 구간에 들어가 놓고 "주행 중" 이라고 하면 늦다. `lookAhead` 가
 * 앞 구간을 미리 읽는다. 이것도 속도에 비례한다.
 *
 * ── ★ 순간이동하면 끊고 다시 말한다 (2026-09-22 · DECISIONS §213-2) ──────
 * GPS 가 음영에서 끊겼다가 수백 m 앞에서 다시 잡히면, 그 사이 말했어야 할 회전은
 * 이미 지나갔고 말하던 문장은 **엉뚱한 자리의 안내**다. 위치 추정기가 `jumpSeq` 를
 * 올리면 — 말하던 것을 끊고, 문턱 기록을 비우고, **새 자리의 다음 회전을 바로**
 * 말한다. 문턱(12·6·2.5초)을 기다리지 않는다. 상용 내비가 터널을 나오며 하는 일이다.
 *
 * ★ 우선순위 — 이탈 > 재동기화 > 회전 > 규칙 > 사정 > 판정.
 *
 * ── ★ 그 우선순위를 **발화기에도 알려준다** (2026-09-29 · DECISIONS §301) ──────
 * 이 훅의 `return` 사슬은 **한 틱에 하나만** 말하게 한다. 그런데 말한 것이 재생되는
 * 2~3초 동안 다음 틱이 오고, 그것들이 발화기 큐에 쌓인다. 종전에는 회전과 판정이
 * **둘 다 `normal`** 이라 발화기가 급함을 몰랐고, 큐가 밀리면 **도착 순서로** 버렸다 —
 * 회전 실행 안내가 판정 안내에 밀려나갈 수 있었다.
 * 이제 자리마다 급함을 준다: 회전 `turn` · 규칙 `rule`(역주행은 `critical`) ·
 * 사정·판정 `notice`. 발화기는 **가장 안 급한 것부터** 버리고 **더 급한 것이 오면 자른다.**
 * ★ 이 훅은 `RoutePlan` 만 받고 **그것이 어떻게 만들어졌는지 모른다.**
 *   경로 알고리즘이 바뀌어도 여기는 안 바뀐다.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { createSpeaker } from "../infra/speech";
import {
  buildIncidence, extractManeuvers, nextManeuver, mergePhrase,
  type Incidence, type Maneuver,
} from "../domain/turn";
import { newMemory, reachOf, resync, step, type VoiceTick } from "../domain/voice";
import { type Hazard } from "../domain/context";
import { cvAhead } from "../domain/reroute";
import { type CvView } from "../domain/cv";
import { requiredWidth } from "../domain/vehicle";
import type {
  NaviGraph, RoutePlan, VehicleSpec, VerdictStyle,
} from "../domain/types";

/** 이보다 가까운 다음 회전은 묶어서 한 번에 말한다. */
const MERGE_M = 45;

export interface VoiceInput {
  graph: NaviGraph | null;
  spec: VehicleSpec | null;
  plan: RoutePlan | null;
  /** 경로 시작부터 온 거리(m). 위치 추정기(`domain/progress`)가 낸다 */
  driven: number | null;
  /** 재동기화 횟수. 바뀌면 끊고 새 자리 안내를 낸다 */
  jumpSeq: number;
  offRoute: boolean;
  style: Record<string, VerdictStyle>;
  enabled: boolean;
  /** 경로 위 주변 사정(§216-3) — 과속방지턱 · 단속카메라 · 보호구역 시설 */
  hazards?: readonly Hazard[];
  /**
   * 영상이 지금 재 준 통과폭 — **구간별로 접힌 것**(`cv.fold`).
   *
   * ★ 이 훅이 **고르는** 자리다. `domain/voice.ts` 의 틱은 「앞 구간 소견」
   *   하나만 받고, 그 「앞」이 어디까지인가는 **속도에 달려 있다**
   *   (`reachOf(speed)`) — 속도를 아는 것은 이 훅이다(아래 `speed`).
   *   고르는 판별식 자체는 `domain/reroute.cvAhead` 가 든다.
   * ★ 없으면 틱의 `cv` 가 `null` 이고, 그때 음성은 **오늘과 한 글자도
   *   다르지 않다**(`test/voice.test.ts` 가 그 한 글자를 문다).
   */
  cv?: ReadonlyMap<string, CvView> | null;
}

export interface VoiceState {
  /** 화면 상단이 그대로 쓰는 문구. **음성과 같다** */
  banner: string | null;
  maneuver: Maneuver | null;
  distM: number | null;
  available: boolean;
  koVoice: boolean;
}

export function useVoice(i: VoiceInput): VoiceState {
  const speaker = useMemo(() => createSpeaker(), []);
  // ★ 2026-09-30 (§329). 참조 넷이었다. 기억의 집이 `domain/voice.ts` 로
  //   내려가면서 여기 남는 것은 **그 기억을 틱 사이에 들고 있는 일**뿐이다.
  const mem = useRef(newMemory());

  // ── 실제 속도를 잰다. 문턱이 이것에 비례한다 ──────────────────
  const lastRef = useRef<{ m: number; t: number } | null>(null);
  const [speed, setSpeed] = useState(8);   // m/s. 초기 추정

  const inc: Incidence | null = useMemo(
    () => (i.graph ? buildIncidence(i.graph) : null), [i.graph]);

  const maneuvers = useMemo(() => {
    if (!i.plan || !inc || !i.spec) return [];
    return extractManeuvers(i.plan, inc, requiredWidth(i.spec));
  }, [i.plan, inc, i.spec]);

  const driven = i.plan ? i.driven : null;

  useEffect(() => {
    if (driven == null) { lastRef.current = null; return; }
    const now = performance.now();
    const prev = lastRef.current;
    lastRef.current = { m: driven, t: now };
    if (!prev) return;
    const dt = (now - prev.t) / 1000;
    const dm = driven - prev.m;
    // 뒤로 간 것과 순간이동은 버린다. 스냅이 튄 것이다.
    if (dt < 0.15 || dm <= 0 || dm / dt > 60) return;
    // 지수 평활. 한 틱의 잡음이 문턱을 흔들지 않게 한다.
    setSpeed((s) => s * 0.7 + (dm / dt) * 0.3);
  }, [driven]);

  const { m, distM, after } = nextManeuver(maneuvers, driven, MERGE_M);
  const banner = m ? mergePhrase(m, after, distM) : null;

  // ★ 한 틱의 입력. 아래 두 효과가 **같은 것**을 본다 — 종전에는 각자
  //   `i.*` 를 흩어 읽어서 무엇이 한 틱인지 읽는 사람이 모았어야 했다.
  // ★ 틱마다 다시 고른다. 접기(`cv.fold`)는 측정이 올 때 한 번이지만 **고르기는
  //   매 틱**이다 — 차가 가면 「앞」이 바뀌고, 나이도 흐른다.
  const cv = i.spec
    ? cvAhead(i.plan, i.cv, driven, reachOf(speed), requiredWidth(i.spec))
    : null;
  const tick: VoiceTick = {
    enabled: i.enabled, offRoute: i.offRoute, plan: i.plan, driven,
    speed, m, after, distM, style: i.style, hazards: i.hazards, cv,
  };
  const tickRef = useRef(tick);
  tickRef.current = tick;

  // ── 재동기화 — 순간이동한 자리에서 바로 말한다 ─────────────
  // ★ 이 효과가 아래 본 효과보다 **먼저** 선언돼야 한다. 같은 렌더에서 문턱 기록을
  //   먼저 채워야 본 효과가 같은 말을 한 번 더 하지 않는다.
  const seenJump = useRef(0);
  useEffect(() => {
    if (i.jumpSeq === seenJump.current) return;
    seenJump.current = i.jumpSeq;
    lastRef.current = null;            // 끊긴 동안의 속도는 모른다
    // ★ `resync` 가 기억을 비우는 것까지 든다 — 비우기와 말하기가 한 곳에
    //   있어야 「비웠는데 안 말했다」가 안 생긴다.
    const u = resync(tickRef.current, mem.current);
    if (!i.enabled || i.offRoute) return;
    speaker.cancel();
    if (u) speaker.say(u.text, u.urgency);
  }, [i.jumpSeq]); // eslint-disable-line react-hooks/exhaustive-deps

  // ★ 2026-09-24 (PLAN §13 W13-5). 종전에는 아래 효과가 `if (!i.enabled) return`
  //   하고 끝이었다 — **말하던 문장이 안 멈췄다.** 병목 구간에서 「조용히 해」를
  //   눌러도 그 문장과 큐에 남은 둘이 끝까지 나갔다. `speaker.setEnabled` 는
  //   만들어 놓고 **한 번도 안 불렀다**(전수 grep 0건).
  useEffect(() => {
    speaker.setEnabled(i.enabled);
    if (!i.enabled) speaker.cancel();
  }, [i.enabled, speaker]);

  // 페이지를 떠나면 합성기를 놓는다 — 깨우기 타이머가 남으면 누수다.
  useEffect(() => () => speaker.dispose(), [speaker]);

  // ★ 본 걸음. 무엇을 말할지는 `domain/voice.ts::step` 이 정하고 여기는
  //   **그것을 발화기에 넘길 뿐**이다(§329).
  useEffect(() => {
    const u = step(tickRef.current, mem.current);
    if (u) speaker.say(u.text, u.urgency);
  }, [i.enabled, i.offRoute, i.plan, i.style, i.hazards, m, after, distM, driven,
      speed, speaker]);

  return {
    banner, maneuver: m, distM,
    available: speaker.available, koVoice: speaker.koVoice,
  };
}
