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
 * ★ 우선순위 — 이탈 > 재동기화 > 회전 > 판정.
 * ★ 이 훅은 `RoutePlan` 만 받고 **그것이 어떻게 만들어졌는지 모른다.**
 *   경로 알고리즘이 바뀌어도 여기는 안 바뀐다.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { createSpeaker } from "../infra/speech";
import {
  buildIncidence, extractManeuvers, nextManeuver, mergePhrase, gateIndex,
  type Incidence, type Maneuver,
} from "../domain/turn";
import { lookAhead } from "../domain/graph";
import { nextRule, rulePhrase } from "../domain/rules";
import { hazardPhrase, nextHazard, type Hazard } from "../domain/context";
import { requiredWidth } from "../domain/vehicle";
import type {
  NaviGraph, RoutePlan, VehicleSpec, VerdictStyle,
} from "../domain/types";

/** 이보다 가까운 다음 회전은 묶어서 한 번에 말한다. */
const MERGE_M = 45;
/** 판정 안내를 이만큼 앞에서 미리 낸다(초). */
const VERDICT_AHEAD_SEC = 7;
const VERDICT_MIN_M = 40;

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
  const spokenGate = useRef(new Map<number, number>());
  const spokenVerdict = useRef<string | null>(null);
  const spokenRule = useRef(new Set<string>());
  const wasOff = useRef(false);

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

  const gateOf = (d: number) => gateIndex(d, speed);

  // ── 재동기화 — 순간이동한 자리에서 바로 말한다 ─────────────
  // ★ 이 효과가 아래 본 효과보다 **먼저** 선언돼야 한다. 같은 렌더에서 문턱 기록을
  //   먼저 채워야 본 효과가 같은 말을 한 번 더 하지 않는다.
  const seenJump = useRef(0);
  useEffect(() => {
    if (i.jumpSeq === seenJump.current) return;
    seenJump.current = i.jumpSeq;
    spokenGate.current.clear();
    spokenVerdict.current = null;
    spokenRule.current.clear();
    lastRef.current = null;            // 끊긴 동안의 속도는 모른다
    if (!i.enabled || i.offRoute) return;
    speaker.cancel();
    if (m && distM != null) {
      spokenGate.current.set(m.atM, Math.max(0, gateOf(distM)));
      speaker.say(mergePhrase(m, after, distM), "critical");
    }
  }, [i.jumpSeq]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!i.enabled) return;

    // ── 이탈이 최우선 ──────────────────────────────────────────
    if (i.offRoute) {
      if (!wasOff.current) {
        wasOff.current = true;
        speaker.say("경로를 벗어났습니다. 재탐색합니다.", "critical");
      }
      return;
    }
    wasOff.current = false;

    // ── 회전 안내. 문턱이 속도에 비례한다 ──────────────────────
    if (m && distM != null) {
      // ★ 가장 안쪽 문턱을 고른다. 종전 `findIndex` 는 **바깥 문턱부터** 맞춰
      //   「실행(2.5초 전)」 자리에서도 「먼저 알림」 으로 셌다 — 한 번 말한 뒤로는
      //   `gate > prev` 가 거짓이라 실행 안내가 안 나갔다.
      const gate = gateOf(distM);
      if (gate >= 0) {
        const prev = spokenGate.current.get(m.atM);
        if (prev == null || gate > prev) {
          spokenGate.current.set(m.atM, gate);
          speaker.say(mergePhrase(m, after, distM));
          return;   // 회전이 판정을 이긴다
        }
      }
    }

    // ── 통행 규칙. 역주행 · 방향 모를 일방통행 · 회전 금지 (§215-1) ──
    // ★ 판정보다 앞이다. 폭은 지나가며 볼 수 있지만 대향차는 들어가 봐야 안다.
    if (!i.plan || driven == null) return;
    const reach = Math.max(VERDICT_MIN_M, speed * VERDICT_AHEAD_SEC);
    const rule = nextRule(i.plan.rules, driven, reach);
    if (rule) {
      const k = `${rule.kind}@${rule.atM.toFixed(0)}`;
      if (!spokenRule.current.has(k)) {
        spokenRule.current.add(k);
        speaker.say(rulePhrase(rule), rule.kind === "wrong_way" ? "critical" : undefined);
        return;
      }
    }

    // ── 주변 사정. 규칙 · 회전 다음, 판정 앞 (§216-3) ─────────────
    // ★ 짧게 한 번. 60m 앞(속도 비례 문턱과 작은 쪽)에서만 — 멀리서 말하면 어느 것인지 모른다
    const hz = nextHazard(i.hazards ?? [], driven, i.hazards?.length ? Math.min(reach, 60) : 0);
    if (hz) {
      const k = `hz-${hz.kind}@${hz.atM.toFixed(0)}`;
      if (!spokenRule.current.has(k)) {
        spokenRule.current.add(k);
        speaker.say(hazardPhrase(hz));
        return;
      }
    }

    // ── 판정 안내. 회색 구간에만, 진입 **전에** ────────────────
    const ahead = lookAhead(i.plan, driven, reach);
    if (!ahead) return;
    if (ahead.verdict !== "needs_cv" && ahead.verdict !== "unknown") return;
    if (ahead.seg_uid === spokenVerdict.current) return;

    spokenVerdict.current = ahead.seg_uid;
    const label = i.style[ahead.verdict]?.label ?? ahead.verdict;
    const w = ahead.width_min_m != null
      ? ` 폭 ${ahead.width_min_m.toFixed(1)}미터.` : "";
    // ★ §215-2. 회색은 **왜** 회색인지 한 마디 붙인다. 카메라가 없어서인지가 운전자에게 제일 쓸모 있다
    const why = ahead.verdict === "unknown" && ahead.unknown_reason?.startsWith("no_cctv")
      ? " CCTV 없음." : "";
    speaker.say(`잠시 후 ${label} 구간.${w}${why}`);
  }, [i.enabled, i.offRoute, i.plan, i.style, i.hazards, m, after, distM, driven,
      speed, speaker]);

  return {
    banner, maneuver: m, distM,
    available: speaker.available, koVoice: speaker.koVoice,
  };
}
