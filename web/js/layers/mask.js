/* Fire-Lane · 3단 마스크
   ────────────────────────────────────────────────────────────
   동명동      원본 밝기      — 판정 대상
   접근 회랑   살짝 어둡게    — 119안전센터에서 오는 길. 보이되 주역은 아니다
   그 밖       덮는다         — 스코프 밖

   안전센터는 동명동 밖에 있다(대인 서 1.0km / 지산 동 1.2km).
   동 경계만 잠그면 출동 경로가 화면에서 잘린다.

   마스크 = 세계에서 **display_scope** 를 도려낸 폴리곤. 그 밖을 덮어 스코프를
   눈으로 못박는다.

   ★ 2026-09-20 정정 (PLAN §13 W9-5 · DECISIONS §205). 여기는
     「세계에서 **동명동**을 도려낸 폴리곤 … UI 작업 범위가 동명동을 넘지
     않는다는 걸 화면 자체가 말해준다」고 적고 있었다. **그 말이 거짓이었다.**
     실측 — 도려낸 구멍을 EPSG:5186 으로 재면 **1.7500km²** 이고 동명동
     (`boundary.geojson`)은 **0.4292km²** 다. **4.08배**다.
     도려낸 것은 `display_scope`(동 경계 ⊕ 회랑 ⊕ 안전센터원)이지 동명동이 아니다.
     화면이 말해준다는 그 말 때문에, 보는 사람은 마스크 안쪽을 전부 동명동으로
     읽는다 — 주석 하나가 지도의 뜻을 바꿔놓고 있었다(§1 #62 와 같은 뿌리).
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";

/* 크롬 색 정본은 config.js 의 chrome 이다. 생성은 다크로 하고
   setTheme() 이 그 위를 덮는다(ui/theme.js). */
const CH = CONFIG.chrome;

export function addMask(mask, maskSoft){
  S.map.addSource("mask-soft",{type:"geojson",data:maskSoft});
  S.map.addLayer({id:"mask-soft-l",type:"fill",source:"mask-soft",
    paint:{"fill-color":CH.mask.dark,"fill-opacity":.42}});
  S.map.addSource("mask",{type:"geojson",data:mask});
  S.map.addLayer({id:"mask-l",type:"fill",source:"mask",
    paint:{"fill-color":CH.mask.dark,"fill-opacity":.9}});
}

/* 동 경계 */
export function addBoundary(bnd){
  S.map.addSource("bnd",{type:"geojson",data:bnd});
  S.map.addLayer({id:"bnd-l",type:"line",source:"bnd",
    paint:{"line-color":CH.bnd.dark,"line-width":1.4,"line-dasharray":[3,2],"line-opacity":.75}});
}

/* 건물 3D — MapLibre 자체 fill-extrusion */
export function addBuildings(bld){
  S.map.addSource("bld",{type:"geojson",data:bld});
  S.map.addLayer({id:"bld-3d",type:"fill-extrusion",source:"bld",
    paint:{
      "fill-extrusion-color":["interpolate",["linear"],["get","flo"],
        1,CH.bldRamp.dark[0], 3,CH.bldRamp.dark[1],
        6,CH.bldRamp.dark[2], 12,CH.bldRamp.dark[3]],
      "fill-extrusion-height":["interpolate",["linear"],["zoom"],13.6,0,14.4,["get","h"]],
      "fill-extrusion-opacity":.88,
      "fill-extrusion-vertical-gradient":true}});
}
