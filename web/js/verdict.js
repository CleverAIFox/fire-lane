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

/* unknown 의 사유. 회색의 정의는 no_cctv 하나다.
   width(폭 산출 실패)는 설계에 없던 버그 상태이며 0 으로 수렴시키는 중이다.
   그 값이 0 이 아닌 동안에는 툴팁에 사유가 그대로 노출된다. */
export const REASON = CONFIG.reason;
