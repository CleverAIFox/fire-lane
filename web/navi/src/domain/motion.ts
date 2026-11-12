/**
 * domain/motion.ts — **차가 달리고 있는가.**  (DECISIONS §704)
 *
 * IN    측위(`Fix` — 속도가 실렸으면 그것, 아니면 앞 측위와의 차분) · 마지막 측위 이후 경과
 * OUT   달리는가(`boolean`). 순수 함수 — 상태는 `useNavigation` 이 든다
 * PARAM `MOVING_MPS` · `STOPPED_MPS`(히스테리시스) · `STALE_S`
 * 밖    **신호가 아주 끊긴 채 달리는 차는 못 본다** — 그 상태는 `gpsWeak` · `offline` 상태가 따로 말한다. 여기는 「측위가 오는 동안의 속도」다.
 *
 * ★ 왜 있나 — 「자세히」(병목 상세)는 정차 중 상세로 세는 파일로 뺐는데(DECISIONS §703) **달리는 중에도 열렸다.** 속도로 잠가야 그 분류가 참이 된다.
 * ★ 속도의 출처 — `Fix.speedMps`(GPS 의 도플러 `coords.speed` · 시뮬레이션 · 재생이 싣는다). 비어 있으면 앞 측위와의 **차분**이고, 차분은 측위 오차 안의
 *   움직임을 **정지로 본다**(정지한 GPS 가 흔들려 달리는 것으로 읽히면 정차 중에도 잠긴다).
 * ★ 측위가 `STALE_S` 동안 안 오면 — 마지막 속도가 **느렸을 때만** 선 것으로 본다(`silenceStops`). 브라우저의 `watchPosition` 은 정지 중에 콜백을 안 주는 경우가 있다.
 *   마지막 속도가 달리는 속도였으면 **신호가 끊긴 것이다**(GPS 음영) — 잠금을 유지한다. 신호가 **아주 끊긴 채 오래 달리는 차**는 그래도 못 본다(위 「밖」).
 */
import { distM } from "./geo";
import type { Fix } from "./types";

/** 이 속도(m/s ≈ 3.6km/h) 이상이면 달리는 것이다. */
export const MOVING_MPS = 1.0;
/** 달리다가 이 속도(m/s) **미만**이 돼야 선 것이다 — 두 문턱 사이는 이전 상태를 유지한다(깜박임 방지). */
export const STOPPED_MPS = 0.5;
/** 측위가 이만큼(초) 안 오면 선 것으로 본다. */
export const STALE_S = 3;
/** 차분 속도를 믿는 측위 간격(초). 이보다 짧으면 잡음이 크고 길면 그 사이 선 것을 모른다. */
const DT_MIN_S = 0.2, DT_MAX_S = 5;

export interface PrevFix { lon: number; lat: number; t: number }

/** 이 측위의 속도(m/s). 모르면 `null`. */
export function fixSpeed(prev: PrevFix | null, f: Fix, tMs: number): number | null {
  if (f.speedMps != null && Number.isFinite(f.speedMps) && f.speedMps >= 0) return f.speedMps;
  if (!prev) return null;
  const dt = (tMs - prev.t) / 1000;
  if (dt < DT_MIN_S || dt > DT_MAX_S) return null;
  const d = distM([prev.lon, prev.lat], [f.lon, f.lat]);
  // 측위 오차 안의 움직임은 정지다 — 정확도를 모르면 5m 로 본다.
  if (d <= Math.max(f.accuracy ?? 5, 5)) return 0;
  return d / dt;
}

/**
 * 측위가 끊긴 채 `silentS` 초가 지났을 때 **서 있는 것으로 볼 근거가 있는가.**
 *
 * ★ 2026-11-12 (DECISIONS §708). 침묵을 곧바로 정지로 읽으면 안 된다 — **GPS 음영(터널 · 고층 사이)에서 달리는 차의 잠금이 풀린다.** 소방차가 도시에서
 *   제일 자주 겪는 일이다(스모크의 「자세히」 시험이 시뮬레이션의 음영 8초에 실제로 풀려 빨갰다). 침묵 직전의 속도가 **달리는 속도(1.0 m/s 이상)였으면 신호가
 *   끊긴 것이지 선 것이 아니다** — 잠금을 유지한다. 서 있었거나(느렸거나) 속도를 한 번도 못 받았으면(근거 없음) 정지로 본다. 서는 차는 속도가 먼저 줄어
 *   마지막 측위가 느리다 — 그래서 이 규칙이 정지를 놓치지 않는다.
 */
export function silenceStops(lastSpeedMps: number | null, silentS: number): boolean {
  return silentS > STALE_S && (lastSpeedMps == null || lastSpeedMps < MOVING_MPS);
}

/** 히스테리시스 — 모르는 속도(`null`)는 이전 상태를 유지한다. */
export function nextMoving(was: boolean, v: number | null): boolean {
  if (v == null) return was;
  return was ? v >= STOPPED_MPS : v >= MOVING_MPS;
}
