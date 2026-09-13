/* Fire-Lane · 판정 표현 계층
   ────────────────────────────────────────────────────────────
   판정 4종. 런타임에 호모그래피를 돌릴지가 유일한 분기라
   '통과 확실'과 '통과 유력'을 나눌 실익이 없어 하나로 합쳤다.
   세부 구분이 필요하면 툴팁의 width_min_m 을 보면 된다.

   현재는 1단계(도면 프루닝) 결과다. 최종 판정이 아니다.
   라벨에서 "도면상"은 뺐다(2025-08 팀 요청). 대신 좌측 #warn 이
   "도면 기반 1차 분류"라는 단서를 계속 진다. #warn 문구를 지우면
   화면에 단서가 하나도 안 남으니 지우지 말 것.

   ★ 임계값의 정본은 src/firelane/segments.py 다. 여기는 표현만 한다.
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "./config-access.js";
import { S } from "./state.js";

export const VERDICT = Object.fromEntries(Object.entries(CONFIG.verdict)
  .map(([k,v])=>[k,{c:v.color, cl:v.lightColor||v.color, nm:v.label, d:v.desc}]));

/* 지금 테마에서 쓸 판정 색. setTheme() 이 S.lightTheme 을 뒤집으면
   지도 선·범례가 함께 따라온다. */
export const vColor = k => (S.lightTheme ? VERDICT[k].cl : VERDICT[k].c);

/* MapLibre 판정색 match 식. **유도의 정본이다.**
   ★ 2026-09-11 (B3). `layers/segments.js` 와 `ui/minimap.js` 가 똑같은 식을
     각자 조립하고 있었다. 판정이 하나 늘면 두 곳을 고쳐야 하고, 한 곳만
     고치면 미니맵과 큰 지도가 다른 색이 된다 — 같은 구간인데 색이 다르면
     화면이 거짓말을 한다.
   ★ 소비자를 하나씩 고치지 않고 유도를 정본으로 만든다(HANDOFF 원칙 ⑤).

   pick 은 판정키 → 색배열. 기본은 현재 테마(`vColor`)이고, 레이어를 만들 때는
   다크 고정(`k => VERDICT[k].c`)을 넘긴다. 지도는 항상 다크로 만들어지고
   setTheme() 이 그 위를 덮기 때문이다. */
export const verdictMatch = (pick = vColor) => [
  "match", ["get", "verdict"],
  "blocked",  `rgb(${pick("blocked")})`,
  "needs_cv", `rgb(${pick("needs_cv")})`,
  "clear",    `rgb(${pick("clear")})`,
  `rgb(${pick("unknown")})`,
];

/* 레이어 생성 시점용. 테마를 안 탄다. */
export const vDark = k => VERDICT[k].c;

/* unknown 의 사유. 회색의 정의는 no_cctv 하나다.
   width(폭 산출 실패)는 설계에 없던 버그 상태이며 0 으로 수렴시키는 중이다.
   그 값이 0 이 아닌 동안에는 툴팁에 사유가 그대로 노출된다. */
export const REASON = CONFIG.reason;
