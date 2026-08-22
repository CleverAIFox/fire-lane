/* Fire-Lane · 커버리지 원
   ────────────────────────────────────────────────────────────
   CCTV 커버리지 25m 원 — 지면에 반투명으로. 사각지대가 눈에 보이게.
   기여: @marscoolcat

   CONFIG.markers 의 spec.cover 선언으로 만든다.
   반경은 고정값(cover.radius) 또는 피처 속성(cover.by) 에서 온다.
   ★ 의미가 마커마다 다르다. CCTV 는 "이 범위를 본다"(실선),
     가로등은 "폴이 이 안 어딘가에 있다"(점선). 선 종류로 구분한다.
   ★ CCTV 색은 CONFIG.cctvCov 가 정본이다(라이트/다크 테마 전환 대상).
     ui/theme.js 의 syncCctv() 가 이 레이어 id 를 그대로 쓰므로
     id 규칙(spec.id + "-cov-f" / "-cov-l")을 바꾸지 말 것.
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";

export const circleRing = (lng,lat,m,steps=44) => {
  const dLat=m/111320, dLng=m/(111320*Math.cos(lat*Math.PI/180)), c=[];
  for(let i=0;i<=steps;i++){ const a=2*Math.PI*i/steps; c.push([lng+dLng*Math.cos(a), lat+dLat*Math.sin(a)]); }
  return c;
};

export function addCoverage(){
  const map = S.map;
  for (const spec of CONFIG.markers){
    const cv = spec.cover, src = S.DATA[spec.data];
    if (!cv || !src) continue;
    const fc = { type:"FeatureCollection", features:
      (src.features||[]).filter(f=>f.geometry && f.geometry.type==="Point").map(f=>({
        type:"Feature", properties:{...f.properties},
        geometry:{type:"Polygon", coordinates:[ circleRing(
          f.geometry.coordinates[0], f.geometry.coordinates[1],
          cv.by ? (+f.properties[cv.by] || 50) : cv.radius) ]} })) };
    const id = spec.id + "-cov";
    /* 테마 연동은 선언(cover.themed)으로 정한다. id 로 분기하면
       마커가 늘 때마다 if 가 늘어난다. */
    const th = cv.themed ? CONFIG[cv.themed] : null;
    const col = th ? th.colorDark : cv.color;
    /* ★ themed 가 없을 때의 기본 농도가 0.10 이었다. 테두리는 그 70% 인 0.07 이라
       사실상 안 보였다. cover.opacity / cover.lineWidth 로 선언에서 올릴 수 있게 했다.
       면은 옅게, 테두리는 진하게 — 검은 배경에서는 면적보다 윤곽이 먼저 읽힌다. */
    const op   = th ? th.opacityDark : (cv.opacity ?? 0.10);
    const lop  = th ? Math.min(1, op*1.6) : (cv.lineOpacity ?? Math.min(1, op*2.4));
    const lw   = cv.lineWidth ?? 1;
    map.addSource(id, {type:"geojson", data:fc});
    map.addLayer({id:id+"-f", type:"fill", source:id,
      layout:{visibility:"none"},
      paint:{"fill-color":col, "fill-opacity":op}}, "seg-l");
    map.addLayer({id:id+"-l", type:"line", source:id,
      layout:{visibility:"none"},
      paint:{"line-color":col, "line-opacity":lop, "line-width":lw,
             ...(cv.style==="dashed" ? {"line-dasharray":[2,2]} : {})}}, "seg-l");
  }
}
