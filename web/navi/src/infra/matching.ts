/**
 * infra/matching.ts — Mapbox Map Matching. 하이브리드 경계의 판정자.
 *
 * ── 무엇을 위한 것인가 ──────────────────────────────────────────
 * 우리 경로 좌표열을 상용 도로망에 정렬해 **턴바이턴 음성 지시를 받는다.**
 * 회전각·도로명 데이터를 우리가 만들 필요가 없어진다(node_link 미투입).
 *
 * 1,101 구간 전량 대조 결과(2026-09-05):
 *
 *     폭 <3m     23% 매칭   중앙 0.000
 *     폭 3-7m    86%
 *     폭 7-15m   90%
 *     폭 15+     93%
 *
 * **3.0m 에서 절벽처럼 갈린다.** 그리고 3.0m 는 우리 소방차 최소
 * 필요폭과 같은 숫자다 — 경계를 우리가 고른 것이 아니라 물리가 골라줬다.
 *
 * ★ 토큰이 없으면 아무것도 안 한다. 앱은 그대로 돌고 음성은 전부 자체
 *   문구로 나간다. **남는 사람이 토큰 없이 개발할 수 있어야 한다.**
 *
 * ★ 구간 단위로 던지지 마라. 짧은 구간(<30m)이 58% 로 낮은 것은 점이
 *   적어서다. **경로 좌표열 전체를 한 번에** 던지면 매칭률이 올라간다.
 */
import { MAPBOX_TOKEN, MATCHING_ENABLED } from "../config";
import type { LngLat } from "../domain/geo";

const API = "https://api.mapbox.com/matching/v5/mapbox/driving/";
/** Map Matching 좌표 상한. 넘으면 균등 추출한다. */
const MAX_PTS = 100;

export interface VoiceStep {
  /** 지시 문구. Mapbox 가 만든 것 */
  text: string;
  /** 이 지시를 낼 지점까지 남은 거리(m) */
  distanceAlongGeometry: number;
}

export interface MatchResult {
  ok: boolean;
  confidence: number | null;
  steps: VoiceStep[];
  /** 왜 실패했는지. 화면에 그대로 띄우지 말고 로그로 */
  reason?: string;
}

function thin(coords: LngLat[], max = MAX_PTS): LngLat[] {
  if (coords.length <= max) return coords;
  const step = Math.ceil(coords.length / max);
  const out = coords.filter((_, i) => i % step === 0);
  if (out[out.length - 1] !== coords[coords.length - 1]) {
    out.push(coords[coords.length - 1]);
  }
  return out;
}

export async function matchRoute(coords: LngLat[]): Promise<MatchResult> {
  if (!MATCHING_ENABLED) {
    return { ok: false, confidence: null, steps: [], reason: "토큰 없음" };
  }
  if (coords.length < 2) {
    return { ok: false, confidence: null, steps: [], reason: "좌표 부족" };
  }
  const path = thin(coords).map(([x, y]) => `${x.toFixed(6)},${y.toFixed(6)}`).join(";");
  const q = new URLSearchParams({
    steps: "true", voice_instructions: "true", banner_instructions: "true",
    geometries: "geojson", language: "ko", access_token: MAPBOX_TOKEN,
  });
  try {
    const r = await fetch(`${API}${path}?${q}`);
    const d = await r.json();
    const m = d.matchings?.[0];
    if (!m) {
      return { ok: false, confidence: null, steps: [], reason: d.code ?? "NoMatch" };
    }
    const steps: VoiceStep[] = [];
    for (const leg of m.legs ?? []) {
      for (const s of leg.steps ?? []) {
        for (const v of s.voiceInstructions ?? []) {
          steps.push({
            text: v.announcement,
            distanceAlongGeometry: v.distanceAlongGeometry,
          });
        }
      }
    }
    return { ok: true, confidence: m.confidence ?? null, steps };
  } catch (e) {
    return { ok: false, confidence: null, steps: [], reason: String(e) };
  }
}
