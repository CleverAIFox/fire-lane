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
 * ★ 우선순위 — 이탈 > 회전 > 판정.
 * ★ 이 훅은 `RoutePlan` 만 받고 **그것이 어떻게 만들어졌는지 모른다.**
 *   경로 알고리즘이 바뀌어도 여기는 안 바뀐다.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { createSpeaker } from "../infra/speech";
import {
  buildIncidence, extractManeuvers, nextManeuver, mergePhrase,
  type Incidence, type Maneuver,
} from "../domain/turn";
import { progressAlongRoute, lookAhead } from "../domain/graph";
import { requiredWidth } from "../domain/vehicle";
import type {
  NaviGraph, RoutePlan, SnapResult, VehicleSpec, VerdictStyle,
} from "../domain/types";

/** 안내 문턱(초 전). 상용 관례를 시간으로 옮긴 것이다. */
const GATES_SEC = [12, 6, 2.5];
/** 각 문턱의 거리 하한(m). 정지 상태에서 문턱이 0 이 되는 것을 막는다. */
const GATES_MIN_M = [80, 40, 15];
/** 먼저 알림의 거리 상한(m). 골목에서 너무 일찍 말하면 헷갈린다. */
const FIRST_MAX_M = 250;
/** 이보다 가까운 다음 회전은 묶어서 한 번에 말한다. */
const MERGE_M = 45;
/** 판정 안내를 이만큼 앞에서 미리 낸다(초). */
const VERDICT_AHEAD_SEC = 7;
const VERDICT_MIN_M = 40;

export interface VoiceInput {
  graph: NaviGraph | null;
  spec: VehicleSpec | null;
  plan: RoutePlan | null;
  current: SnapResult | null;
  offRoute: boolean;
  style: Record<string, VerdictStyle>;
  enabled: boolean;
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

  const driven = i.plan ? progressAlongRoute(i.plan, i.current) : null;

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

  useEffect(() => { speaker.setEnabled(i.enabled); }, [i.enabled, speaker]);

  useEffect(() => {
    spokenGate.current.clear();
    spokenVerdict.current = null;
    lastRef.current = null;
    speaker.cancel();
  }, [i.plan, speaker]);

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
      const gates = GATES_SEC.map((sec, k) => {
        const d = Math.max(GATES_MIN_M[k], speed * sec);
        return k === 0 ? Math.min(FIRST_MAX_M, d) : d;
      });
      const gate = gates.findIndex((g) => distM <= g);
      if (gate >= 0) {
        const prev = spokenGate.current.get(m.atM);
        if (prev == null || gate > prev) {
          spokenGate.current.set(m.atM, gate);
          speaker.say(mergePhrase(m, after, distM));
          return;   // 회전이 판정을 이긴다
        }
      }
    }

    // ── 판정 안내. 회색 구간에만, 진입 **전에** ────────────────
    if (!i.plan || driven == null) return;
    const ahead = lookAhead(
      i.plan, driven, Math.max(VERDICT_MIN_M, speed * VERDICT_AHEAD_SEC));
    if (!ahead) return;
    if (ahead.verdict !== "needs_cv" && ahead.verdict !== "unknown") return;
    if (ahead.seg_uid === spokenVerdict.current) return;

    spokenVerdict.current = ahead.seg_uid;
    const label = i.style[ahead.verdict]?.label ?? ahead.verdict;
    const w = ahead.width_min_m != null
      ? ` 폭 ${ahead.width_min_m.toFixed(1)}미터.` : "";
    speaker.say(`잠시 후 ${label} 구간.${w}`);
  }, [i.enabled, i.offRoute, i.plan, i.style, m, after, distM, driven,
      speed, speaker]);

  return {
    banner, maneuver: m, distM,
    available: speaker.available, koVoice: speaker.koVoice,
  };
}
