/* Fire-Lane · 3D 시설 마커
   ────────────────────────────────────────────────────────────
   시설 마커를 건물과 같은 fill-extrusion 으로 그린다.
   ★ deck.gl 레이어는 map.setTerrain() 을 켜면 지형 아래로 묻힌다.
     세그먼트와 같은 문제다. 네이티브 레이어는 지형을 따라간다.
   비율은 실물, 크기는 과장. 소화전 실물 지름 0.2m 로는 안 보인다.

   CONFIG.markers 스펙으로 런타임 생성한다. 원기둥(r) + 박스(hw/hl) 지원.
   config.js 만 고치면 재발행 없이 반영된다.
   기여: @marscoolcat + @AIMasterFox
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";

export function buildMarkers(){
  const feats = [];
  for (const spec of CONFIG.markers){
    const src = S.DATA[spec.data];
    if (!src) continue;
    for (const f of src.features){
      if (spec.kind && f.properties.kind !== spec.kind) continue;
      const lon = +f.geometry.coordinates[0], lat = +f.geometry.coordinates[1];
      const mLat = 1/110540, mLon = 1/(111320*Math.cos(lat*Math.PI/180));
      /* ★ 지면 높이를 여기서 더하지 않는다.
         MapLibre 는 setTerrain() 이 켜져 있으면 fill-extrusion 을 지형 위에
         자동으로 얹는다(건물 bld-3d 가 base 0 으로도 지면에 붙는 이유다).
         여기서 queryTerrainElevation 값을 또 더하면 표고가 두 번 계산되어
         마커가 딱 그 표고만큼 공중에 뜬다. 산 위 지점일수록 더 높이 뜬다.
         base/top 은 '지면 기준 상대 높이'만 담는다. */
      /* 등 수에 따라 지주를 굵게. 136지점을 같은 굵기로 그리면
         1등짜리와 41등짜리가 구분되지 않는다.
         √n 을 쓰는 이유: 면적이 등 수에 비례해 보이려면 반지름은 √n 이다.
         ★ 높이로 표현하지 않는다. "15층짜리 가로등"처럼 보인다. */
      /* 굵기 배수. spec.scale 선언이 있을 때만 적용한다.
         id 로 분기하면 마커가 늘 때마다 if 가 늘어난다. */
      const sc = spec.scale, v = sc ? +f.properties[sc.by] : null;
      const kMul = (sc && v > 0)
        ? 1 + (sc.k ?? 0.28) * ((sc.mode === "sqrt" ? Math.sqrt(v) : v) - 1)
        : 1;
      spec.parts.forEach((s, i) => {
        let ring;
        if (s.hw != null){            // 박스(직사각형): half-width, half-length
          ring = [[lon-s.hw*mLon, lat-s.hl*mLat],[lon+s.hw*mLon, lat-s.hl*mLat],
                  [lon+s.hw*mLon, lat+s.hl*mLat],[lon-s.hw*mLon, lat+s.hl*mLat],
                  [lon-s.hw*mLon, lat-s.hl*mLat]];
        } else {                      // 원기둥
          const n = s.r < 1 ? 24 : 16;
          const rr = s.r * kMul;
          ring = Array.from({length:n+1}, (_,k) => { const t = k*2*Math.PI/n;
            return [lon + rr*Math.cos(t)*mLon, lat + rr*Math.sin(t)*mLat]; });
        }
        feats.push({type:"Feature", geometry:{type:"Polygon", coordinates:[ring]},
          properties:{...f.properties, z:0, kind:spec.id, label:spec.label, part:i,
            base:s.z, top:s.z+s.h,
            mcolor :`rgb(${s.c[0]},${s.c[1]},${s.c[2]})`,
            mcolorL:`rgb(${(s.cl||s.c).join(",")})`}});
      });
    }
  }
  return {type:"FeatureCollection", features:feats};
}

export function addMarkers(){
  S.map.addSource("markers",{type:"geojson",data:buildMarkers()});
  /* 예전에 있던 idle 재스냅(queryTerrainElevation 으로 z 를 다시 넣던 코드)은 제거했다.
     지형 위 배치는 MapLibre 가 알아서 하므로 재스냅이 곧 이중 가산이었다. */
  S.map.addLayer({id:"mk-3d",type:"fill-extrusion",source:"markers",
    paint:{
      /* setTheme() 이 "mcolor"(다크) ↔ "mcolorL"(라이트) 로 갈아끼운다 */
      "fill-extrusion-color":["get","mcolor"],
      "fill-extrusion-base":  ["get","base"],   /* 지면 기준 상대 높이. 지형 보정은 MapLibre 담당 */
      "fill-extrusion-height":["get","top"],
      "fill-extrusion-opacity":.95}});
}

/* ★ 원본에 있던 `POPUP` 딕셔너리(CONFIG.markers 의 spec.popup 수집)는
   옮기지 않았다. 정의만 있고 참조가 0곳이었다 — 팝업 HTML 은 아래에서
   직접 만든다. spec.popup 을 실제로 쓰려면 이 함수를 고쳐야 한다. */
export function bindMarkerPopups(){
  S.map.on("click","mk-3d", e => {
    const p=e.features[0].properties;
    new maplibregl.Popup({closeButton:false,maxWidth:"270px"})
      .setLngLat(e.lngLat)
      .setHTML(`<div class="pop"><b>${p.name}</b><br>${p.sub||""}
                <br><span class="a">${p.addr||""}</span></div>`).addTo(S.map);
  });
  S.map.on("mouseenter","mk-3d",()=>S.map.getCanvas().style.cursor="pointer");
  S.map.on("mouseleave","mk-3d",()=>S.map.getCanvas().style.cursor="");
}
