/**
 * infra/position/gps.ts — 진짜 GPS.
 *
 * ★ 위치 실패를 치명적으로 다루지 않는다. 데스크톱에는 GPS 가 없고 WSL 은
 *   더 없다. 그런데 출동 차량에는 있다. **없다고 화면이 안 뜨면 개발을
 *   못 한다.** 오류는 콜백으로 넘기고 앱은 계속 돈다.
 *
 * ★ HTTPS 또는 localhost 에서만 된다. GitHub Pages 는 HTTPS 라 배포는
 *   문제없고, 개발은 localhost 예외로 돈다.
 */
import type { PositionSource } from "./types";

/**
 * 에포크 ms → `performance.now()` 시계.
 *
 * ★ **시계를 섞으면 안 된다.** `Fix.t` 를 읽는 쪽(`useNavigation.onFix`)은
 *   `performance.now()` 로 기본값을 채우고, `replay` 도 rAF 타임스탬프
 *   (= 같은 시계)를 넣는다. `GeolocationPosition.timestamp` 만 에포크다.
 *   그대로 넣으면 첫 dt 가 수십억 ms 가 되어 속도가 0 으로 죽는다.
 */
function perfTime(epochMs: number): number | undefined {
  if (!Number.isFinite(epochMs)) return undefined;
  const origin = performance.timeOrigin;
  if (!Number.isFinite(origin)) return undefined;
  const t = epochMs - origin;
  // 시계가 어긋난 기계에서 음수나 미래가 나오면 안 쓴다 — 받는 쪽이 채운다.
  return t >= 0 && t <= performance.now() + 1000 ? t : undefined;
}

export function createGpsSource(): PositionSource {
  return {
    kind: "gps",
    start(onFix, onError) {
      if (!navigator.geolocation) {
        onError?.("이 브라우저에 위치 기능이 없다");
        return () => {};
      }
      const id = navigator.geolocation.watchPosition(
        (p) => onFix({
          lon: p.coords.longitude,
          lat: p.coords.latitude,
          // ★ 저속에서 null 이 자주 온다. 받는 쪽이 이동량으로 만든다.
          heading: Number.isFinite(p.coords.heading as number)
            ? (p.coords.heading as number) : null,
          // ★ 2026-09-24 (W13-2). 종전에는 이 둘을 안 읽었다.
          //   accuracy — 신호 품질. 없으면 08 화면을 띄울 근거가 없다.
          //   t — **측위 시각**. `maximumAge: 5000` 이라 최대 5초 묵은 캐시가
          //       올 수 있는데, 받는 쪽이 「받은 시각」으로 덮으면 dt 가
          //       실제보다 작아져 순간속도가 부풀고 추측항법이 차를 앞으로 민다.
          accuracy: Number.isFinite(p.coords.accuracy) ? p.coords.accuracy : null,
          t: perfTime(p.timestamp),
          source: "gps",
        }),
        (e) => onError?.(`위치 없음 (${e.message})`),
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 8000 },
      );
      return () => navigator.geolocation.clearWatch(id);
    },
  };
}
