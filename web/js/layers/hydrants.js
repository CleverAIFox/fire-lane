/* Fire-Lane · 소화전 물결
   ────────────────────────────────────────────────────────────
   지면에 링이 퍼지고 그 위에 3D 기둥이 선다. 출동 모드에서만 움직인다.
   기여: @marscoolcat

   ★ 채운 원 → 테두리 링(2025-08).
     지면에 눕는 원(pitch-alignment:map)은 기울여 보면 타원으로 눌려 면적이 크게
     줄고, 반투명 얼룩처럼 흐려진다. 같은 크기라도 선으로 된 링이 훨씬 잘 잡힌다.
     그래서 circle-opacity(면)는 0 으로 고정하고 circle-stroke-*(선)만 애니메이션한다.
     색은 하늘색 유지 — 소화전 몸통이 빨강으로 바뀌어도 물결은 그대로 간다.
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";

export function addHydrantPulse(hyd){
  const map = S.map;
  map.addSource("hyd",{type:"geojson",data:hyd});
  const ringPaint = {
    "circle-color":"#4fc3f7", "circle-opacity":0,        // 면은 항상 투명
    "circle-radius":6,
    "circle-stroke-color":"#7fd8ff", "circle-stroke-width":2.5, "circle-stroke-opacity":0,
    "circle-pitch-alignment":"map", "circle-pitch-scale":"map"};
  map.addLayer({id:"hyd-pulse2",type:"circle",source:"hyd",paint:{...ringPaint}});
  map.addLayer({id:"hyd-pulse", type:"circle",source:"hyd",paint:{...ringPaint}});

  const HYD_T0 = performance.now(), HYD_SPEED = CONFIG.dispatch.pulseMs;
  (function ripple(now){
    if(map.getLayer("hyd-pulse")){
      /* CONFIG.dispatch.hydPulse 가 false 면 아래 애니메이션을 통째로 건너뛴다.
         코드는 지우지 않았다 — config.js 에서 true 로 되돌리면 그대로 다시 돈다. */
      if(S.dispatchMode && CONFIG.dispatch.hydPulse){
        const t  = ((now - HYD_T0) % HYD_SPEED) / HYD_SPEED;
        const t2 = (t + 0.5) % 1;
        const zf = Math.max(1, Math.min(4, 1 + (map.getZoom() - 15) * 0.7));  // 확대할수록 넓게
        /* 퍼질수록 선을 가늘게 — 실제 물결처럼 보이고, 초기 링이 굵어 눈에 먼저 띈다 */
        const ring = (id, u) => {
          map.setPaintProperty(id, "circle-radius", (6 + u*26)*zf);
          map.setPaintProperty(id, "circle-stroke-width", (3.4 - u*2.0)*Math.min(2, zf));
          map.setPaintProperty(id, "circle-stroke-opacity", 0.95*(1-u)*(1-u));
        };
        ring("hyd-pulse",  t);
        ring("hyd-pulse2", t2);
      } else {
        map.setPaintProperty("hyd-pulse",  "circle-stroke-opacity", 0);
        map.setPaintProperty("hyd-pulse2", "circle-stroke-opacity", 0);
      }
    }
    requestAnimationFrame(ripple);
  })(performance.now());
}
