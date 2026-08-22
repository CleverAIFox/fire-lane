/* Fire-Lane · 공유 가변 상태
   ────────────────────────────────────────────────────────────
   ★ 왜 객체 하나에 모아두나.
     원본 app.js 는 전체가 IIFE 하나라 `map` · `miniMap` · `lightTheme` ·
     `dispatchMode` 가 전부 클로저 변수였다. 모듈로 쪼개면 그 클로저가
     사라지므로 어딘가에 두어야 한다.

     `export let lightTheme` 로 두면 안 된다 — import 한 쪽에서 재대입이
     불가능하고, 값 복사라 갱신이 전파되지 않는다. 객체 필드는 참조가
     공유되므로 원본의 동작이 그대로 유지된다.

   ★ 이 파일은 아무것도 import 하지 않는다. 의존 그래프의 뿌리라서
     여기에 import 를 하나라도 넣으면 순환이 생길 수 있다.
   ──────────────────────────────────────────────────────────── */
export const S = {
  map      : null,     // 메인 지도
  miniMap  : null,     // 미니맵
  VIEW     : null,     // web/data/view.json
  TB       : null,     // 타일 소스 bounds

  lightTheme  : false,
  dispatchMode: false,

  /* 마커 데이터. 레이어 갱신 시 재사용한다. */
  DATA: {},
  SEG : null,

  off      : new Set(),   // 꺼진 판정(범례 토글)
  markerOff: new Set(),   // 꺼진 마커 레이어
};
