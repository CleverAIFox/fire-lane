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

/* ★ 2026-08-23. 팝업이 `p.name` · `p.sub` · `p.addr` 을 읽고 있었다.
   그 세 이름은 **어느 마커 데이터에도 없다.** 실제 속성은 이렇다.

     cctv        카메라대수 · 카메라화소 · 촬영방면 · 최초설치 · 소재지도로명주소
     hydrants    시설번호 · 상세위치 · 설치연도 · 보호틀유무
     stations    소방서 및 안전센터명 · 전화번호 · 주소
     streetlights n_lights · pos_accuracy_m · mgmt_no_sample · addr

   그래서 3D 마커를 누르면 **제목이 전부 "undefined"** 로 떴다.
   app.js 를 web/js 로 쪼갤 때 POPUP 딕셔너리를 안 옮기면서 생겼고,
   `test_marker_spec_self_contained` 는 손딕셔너리가 **없는지**만 보고
   선언이 **쓰이는지**는 안 봐서 초록불이었다. 이 저장소가 반복해 겪은
   그 병이다 — 측정은 하는데 대조가 없다.

   정본은 config.js 의 `spec.popup` 이다(결정 83 · MASTER §11-2).
   선언이 이미 정확한 HTML 을 만들고 있었으므로 그것을 부르기만 하면 된다.
   `properties.kind` 에는 buildMarkers() 가 spec.id 를 넣는다. */
export function bindMarkerPopups(){
  const byId = Object.fromEntries(CONFIG.markers.map(m => [m.id, m]));

  /* ★ 2026-08-31. 종전에는 `mk-3d` 에만 걸었다. 그런데 **사용자가 클릭하는
     것은 표지판이다** — 마커 본체는 실물 비례(소화전 0.2m)라 5배 과장해도
     1m 남짓이라 화면에서 픽셀 몇 개다. 눈에 보이는 빨간 아이콘은
     `m-hyd-sign` 이고 top 10.9m 위에 크게 떠 있다.

     실측: 소화전 지점에서 queryRenderedFeatures 가
       m-hyd-sign 2건 · mk-3d 0건.
     즉 팝업 코드는 처음부터 멀쩡했고 **닿지 않는 레이어에 걸려 있었다.**
     클릭해도 아무 반응이 없으니 "데이터가 없다" 로 오독된다. */
  /* ★ getLayer() 로 거르지 않는다. `main.js` 는 addMarkers → bindMarkerPopups
     → addSigns 순이라 **여기서는 sign 레이어가 아직 없다.** 존재 검사를
     안전장치로 넣었더니 네 레이어를 전부 걸러 팝업이 하나도 안 붙었다.
     MapLibre 는 나중에 생기는 레이어에도 핸들러가 붙는다. */
  const LAYERS = ["mk-3d", ...CONFIG.markers
    .filter(m => m.sign).map(m => `${m.id}-sign`)];

  LAYERS.forEach(lid => S.map.on("click", lid, e => {
    const p = e.features[0].properties;
    /* ★ `kind` 로 찾지 않는다. sign 레이어는 원본 GeoJSON 을 그대로 소스로
       쓰므로 `markers.js` 가 넣는 `kind` 가 없다(실측: 속성 9종에 kind 없음).
       **어느 레이어를 눌렀는지는 이미 알고 있다.** 그것으로 찾는다. */
    const spec = byId[p.kind] || byId[lid.replace(/-sign$/, "")];
    /* 선언이 없거나 팝업이 없는 마커는 라벨만 띄운다. 조용히 넘어가지 않는다 —
       빈 팝업이 뜨면 "데이터가 없다" 로 오독된다. */
    const html = (spec && spec.popup)
      ? spec.popup(p)
      : `<b>${p.label || p.kind}</b><br><span class="a">표시할 속성 선언 없음</span>`;
    new maplibregl.Popup({closeButton:false,maxWidth:"270px"})
      .setLngLat(e.lngLat)
      .setHTML(`<div class="pop">${html}</div>`).addTo(S.map);
  }));

  LAYERS.forEach(lid => {
    S.map.on("mouseenter", lid, ()=>S.map.getCanvas().style.cursor="pointer");
    S.map.on("mouseleave", lid, ()=>S.map.getCanvas().style.cursor="");
  });
}
