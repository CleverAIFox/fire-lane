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
 * ★ 측위가 `STALE_S` 동안 안 오면 **서 있는 것**으로 본다 — 브라우저의 `watchPosition` 은 정지 중에 콜백을 안 주는 경우가 있다(그래서 침묵이 곧 정지다).
 *   반대쪽 위험(달리는데 신호가 끊김)은 위 「밖」 이다.
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

/** 히스테리시스 — 모르는 속도(`null`)는 이전 상태를 유지한다. */
export function nextMoving(was: boolean, v: number | null): boolean {
  if (v == null) return was;
  return was ? v >= STOPPED_MPS : v >= MOVING_MPS;
}
