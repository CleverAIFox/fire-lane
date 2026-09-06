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
          source: "gps",
        }),
        (e) => onError?.(`위치 없음 (${e.message})`),
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 8000 },
      );
      return () => navigator.geolocation.clearWatch(id);
    },
  };
}
