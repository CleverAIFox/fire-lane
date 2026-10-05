/**
 * domain/handoff.ts — **관제 지령을 읽는 한 자리.**  (DECISIONS §386)
 *
 * ── 정책 (사용자 결정 2026-10-04 · §382-1) ─────────────────────
 * 이 내비는 일반 내비가 아니다. **관제가 정한 지령을 그대로 따라간다** —
 * 승객이 부른 경로가 기사 화면에 고정되는 호출택시 내비와 같은 꼴이다.
 * 소방차 기사는 목적지를 고르지 않는다.
 *
 * 고를 수 있게 두면 지령과 화면이 갈리고, 갈린 둘 중 어느 쪽이 기록으로
 * 남는지가 불분명해진다. 출동 기록은 관제가 든다.
 *
 * ── 왜 한 자리인가 ────────────────────────────────────────────
 * 종전에는 `new URLSearchParams(location.search)` 가 `App.tsx` 안에서만
 * **네 번** 따로 불렸다(사건 · 차종 · 센터 · dev). 깃발이 늘 때마다 한 번씩
 * 더 늘고, 「지령이 왔는가」를 묻고 싶으면 그 넷을 다 봐야 했다 — 물음이
 * 어디에도 없었다는 뜻이다. 여기가 그 물음의 집이다.
 *
 * IN    location.search
 * OUT   Handoff (순수 값)
 * 밖    **화면을 안 그린다.** 무엇을 숨길지는 부르는 쪽이 정한다.
 *       그리고 **좌표가 스코프 안인지도 안 본다** — 그것은 `setDestAt` 이
 *       스냅과 함께 든다. 여기가 드는 것은 「지령이 왔는가」 하나다.
 */
import type { LngLat } from "./geo";

export type Handoff = {
  /** 관제가 사건 위치를 줬다. **참이면 기사는 목적지를 고르지 않는다.** */
  readonly inherited: boolean;
  readonly incident: LngLat | null;
  readonly label: string | null;
  readonly sub: string | null;
  readonly vehicle: string | null;
  readonly station: string | null;
  /** `?demo=1` — 발표용. 경로를 따라 달린다(GPS 흉내가 아니다). */
  readonly demo: boolean;
  /** `?dev=1` — 시연 막대. **켜는 쪽을 명시한다**(§W13-1). */
  readonly dev: boolean;
};

const EMPTY: Handoff = {
  inherited: false, incident: null, label: null, sub: null,
  vehicle: null, station: null, demo: false, dev: false,
};

/** `lon,lat` 를 읽는다. 하나라도 수가 아니면 **없는 것**으로 본다. */
function point(v: string | null): LngLat | null {
  if (!v) return null;
  const parts = v.split(",");
  // ★ 빈 칸은 수가 아니다. `Number("")` 가 **0** 이라 `?incident=,` 가
  //   기니만 앞바다(0,0)로 들어온다 — 시험이 그 자리를 물었다.
  if (parts.length !== 2 || parts.some((s) => s.trim() === "")) return null;
  const [lon, lat] = parts.map(Number);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  // 경위도 범위 밖은 오타다. 스코프 판정이 아니라 **자릿수** 판정이다.
  if (Math.abs(lon) > 180 || Math.abs(lat) > 90) return null;
  return [lon, lat];
}

/** 질의 문자열 → 지령. 부작용이 없다. */
export function readHandoff(search: string): Handoff {
  let q: URLSearchParams;
  try {
    q = new URLSearchParams(search);
  } catch {
    return EMPTY;
  }
  const incident = point(q.get("incident"));
  return {
    inherited: incident !== null,
    incident,
    label: incident ? (q.get("label") ?? "접수 위치") : null,
    sub: incident ? q.get("sub") : null,
    vehicle: q.get("vehicle"),
    station: q.get("station"),
    // ★ 둘 다 **켜는 쪽을 명시**한다. `!== "0"` 로 두면 인자가 없는 배포 링크가
    //   켜진 채로 나가고, 운전석에서 손이 스치면 모의 주행이 실제 GPS 를
    //   대체한다(§W13-1 이 실제로 겪은 일이다).
    demo: q.get("demo") === "1",
    dev: q.get("dev") === "1",
  };
}

/**
 * 기사가 목적지를 **고를 수 있는가**.
 *
 * ★ 지령이 왔으면 못 고른다. 이것이 이 모듈의 전부이고, 화면 셋(지도 탭 ·
 *   검색 · 스왑)이 전부 이 한 값을 본다 — 세 곳이 각자 판단하면 갈린다.
 */
export function canPickDestination(h: Handoff): boolean {
  return !h.inherited;
}

/**
 * 바꾸는 손을 **들려줄 것인가**. 들려주지 않으면 `null` 이다.
 *
 * ★ 2026-10-04. 왜 함수가 따로 생겼나 — 종전 `App.tsx` 는
 *   `onArm={canPick ? setArmed : () => {}}` 꼴이었다. **손만 묶이고 버튼은
 *   그대로 그려졌다.** 지령이 온 운전석 화면에 말없이 씹는 버튼이 둘
 *   (「위치 변경」 · 「지도에서 직접 선택」), 그리고 **아예 안 묶인 것이 하나**
 *   (「⇅ 출발·도착 바꾸기」 — `onSwap` 에는 조건이 없었다) 있었다.
 *   누르면 되는 줄 아는 버튼이 말없이 씹는 것은 족1(무음 통과)이고,
 *   세 번째는 지령 받은 내비에서 출발·도착을 실제로 뒤집었다.
 *
 * ★ `null` 이 답이면 **그릴 손 자체가 없다.** 「그려 놓고 묶는」 모양이
 *   만들어지지 않는다 — 목줄은 틀린 걸 잡는 것이 아니라 틀린 모양이
 *   존재할 수 없게 하는 것이다.
 *
 * ★ 출발 센터도 같은 문에 둔다. 「목적지만 고정」으로 가르면 기사가 센터를
 *   바꿔 지령과 화면이 갈리고, **갈리는 자리를 둘로 늘리면** 이 모듈이
 *   없애려던 그것(세 곳이 각자 판단한다)이 되돌아온다.
 */
export function editHands<T>(h: Handoff, hands: T): T | null {
  return canPickDestination(h) ? hands : null;
}
