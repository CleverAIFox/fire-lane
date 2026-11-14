/**
 * infra/mapPitch.ts — 지도 기울임 상한(`maxPitch`)을 **주소 질의로 고른다.**  (PLAN #78 ②)
 *
 * ★ 왜 생겼나. `#78` 행은 85 를 적었고 코드는 75 다. 어느 쪽이 맞는지는 **눈으로 본 사람이 정한다** — 그런데 둘을 나란히 보려면
 *   코드를 고쳐 다시 빌드해야 했다. `?pitch=85` 로 같은 배포본에서 둘 다 본다. 정해지면 `MAX_PITCH_DEFAULT` 한 줄을 바꾸고 이 손잡이는 남긴다.
 * ★ 기본값은 **지금 값 그대로**(75)다 — 질의가 없으면 아무것도 안 바뀐다.
 * ★ 이 상한은 **사람 손의 기울임**(두 손가락 · Ctrl+끌기)만 묶는다. 코드가 주는 기울임은 최대 60(1인칭 추적 카메라 · `NaviMap.tsx`)이라
 *   상한이 60 아래로 내려가면 그 카메라가 잘린다 — 그래서 하한이 60 이다. 상한 85 는 행이 적은 값이다(그 위는 지평선이 화면을 덮는다).
 *
 * IN    `location.search`(글자)
 * OUT   기울임 상한(도) — 정수 `MAX_PITCH_LO`‥`MAX_PITCH_HI`
 * PARAM `MAX_PITCH_DEFAULT` 75 · `MAX_PITCH_LO` 60 · `MAX_PITCH_HI` 85
 * 밖    **어느 값이 보기 좋은가**는 안 본다 — 사람 눈이다. 지도에 실제로 걸렸는지도 여기서 안 본다(부르는 쪽 한 줄).
 */
export const MAX_PITCH_DEFAULT = 75;
export const MAX_PITCH_LO = 60;
export const MAX_PITCH_HI = 85;

/**
 * `?pitch=85` → 85. **없는 값 · 숫자가 아닌 값 · 범위 밖은 기본값**이다 — 반쯤 맞는 값을 가까운 쪽으로 당기지 않는다
 * (`?pitch=850` 을 85 로 읽으면 오타가 설정이 된다).
 */
export function maxPitchFrom(search: string): number {
  let raw: string | null;
  try {
    raw = new URLSearchParams(search).get("pitch");
  } catch {
    return MAX_PITCH_DEFAULT;
  }
  if (raw == null || !/^\d{1,3}$/.test(raw)) return MAX_PITCH_DEFAULT;
  const v = Number(raw);
  return v >= MAX_PITCH_LO && v <= MAX_PITCH_HI ? v : MAX_PITCH_DEFAULT;
}
