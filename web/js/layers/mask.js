/* Fire-Lane · 3단 마스크
   ────────────────────────────────────────────────────────────
   동명동      원본 밝기      — 판정 대상
   접근 회랑   살짝 어둡게    — 119안전센터에서 오는 길. 보이되 주역은 아니다
   그 밖       덮는다         — 스코프 밖

   안전센터는 동명동 밖에 있다(대인 서 1.0km / 지산 동 1.2km).
   동 경계만 잠그면 출동 경로가 화면에서 잘린다.

   마스크 = 세계에서 동명동을 도려낸 폴리곤. 동 밖을 덮어 스코프를 눈으로
   못박는다. UI 작업 범위가 동명동을 넘지 않는다는 걸 화면 자체가 말해준다.
   ──────────────────────────────────────────────────────────── */
import { S } from "../state.js";

export function addMask(mask, maskSoft){
  S.map.addSource("mask-soft",{type:"geojson",data:maskSoft});
  S.map.addLayer({id:"mask-soft-l",type:"fill",source:"mask-soft",
    paint:{"fill-color":"#05070b","fill-opacity":.42}});
  S.map.addSource("mask",{type:"geojson",data:mask});
  S.map.addLayer({id:"mask-l",type:"fill",source:"mask",
    paint:{"fill-color":"#05070b","fill-opacity":.9}});
}

/* 동 경계 */
export function addBoundary(bnd){
  S.map.addSource("bnd",{type:"geojson",data:bnd});
  S.map.addLayer({id:"bnd-l",type:"line",source:"bnd",
    paint:{"line-color":"#5c6b82","line-width":1.4,"line-dasharray":[3,2],"line-opacity":.75}});
}

/* 건물 3D — MapLibre 자체 fill-extrusion */
export function addBuildings(bld){
  S.map.addSource("bld",{type:"geojson",data:bld});
  S.map.addLayer({id:"bld-3d",type:"fill-extrusion",source:"bld",
    paint:{
      "fill-extrusion-color":["interpolate",["linear"],["get","flo"],
        1,"#1d2430", 3,"#2b3545", 6,"#3b4759", 12,"#4d5a6f"],
      "fill-extrusion-height":["interpolate",["linear"],["zoom"],13.6,0,14.4,["get","h"]],
      "fill-extrusion-opacity":.88,
      "fill-extrusion-vertical-gradient":true}});
}
