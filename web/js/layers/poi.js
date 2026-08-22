/* Fire-Lane · 상가 POI
   ────────────────────────────────────────────────────────────
   네이버 지도처럼 상호를 띄운다. 지상 1층만 남겨서(간판이 골목에서 보이는 것)
   2,077개. 줌 17 이상에서만 라벨을 그린다. 그 아래는 점만.

   ★ 상가 2,077개 중 1,242개가 좌표를 공유한다(겹치는 지점 430곳, 한 건물에
     최대 47개). 한 건물에 입주한 점포들이라 대표점이 같기 때문이다.

     그래서 점과 라벨이 서로 다른 상가의 것이 되는 일이 생겼다. 맨 위에 그려진
     점은 A 의 것인데 자리를 차지한 라벨은 B 의 것이면, 업종이 다를 때 색이
     어긋나 보인다. 색 표현식이 틀린 게 아니라 두 레이어가 고른 피처가 달랐다.

     정렬 키를 하나로 묶어 해결한다. si = 데이터 순서 번호.
       라벨(symbol)  : sort-key 가 작을수록 먼저 배치되어 자리를 얻는다
       점(circle)    : sort-key 가 클수록 위에 그려진다 → 부호를 뒤집는다
     이러면 겹친 자리에서 "위에 보이는 점"과 "표시된 라벨"이 항상 같은 상가다.

   ★ 예전 symbol-sort-key 는 ["get","name"] 이었다. 문자열은 정렬 키로 쓸 수
     없어 사실상 무작위였고, 이것이 어긋남을 더 눈에 띄게 만들었다.
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";

/* 업종 색 — 점과 상호 글자가 같은 표를 쓴다. 정본은 CONFIG.poi.color 다.
   ★ 한 곳에서 만들어 두 레이어에 같이 물린다. 예전처럼 점만 칠하고 글자는
     흰색으로 두면 "이 라벨이 어느 점의 것인가"가 안 읽힌다.
   ★ 검은 테두리가 두 테마 모두를 감당한다. 밝은 지면에서도 글자가 배경에서
     떨어지므로 색을 테마별로 나눌 필요가 없다. */
export const poiColorExpr = () => {
  const t = CONFIG.poi.color;
  return ["match",["get","cat"],
    ...Object.entries(t).filter(([k])=>k!=="other").flat(), t.other];
};

export function addPoi(poi){
  const map = S.map;
  /* si = 데이터 순서 번호. 점 레이어와 라벨 레이어가 같은 피처를 고르게 하는
     공통 정렬 키다. */
  poi.features.forEach((f,i)=>{ f.properties.si = i; });
  map.addSource("poi",{type:"geojson",data:poi});
  map.addLayer({id:"poi-dot",type:"circle",source:"poi",minzoom:16,
    layout:{"circle-sort-key":["-",0,["get","si"]]},
    paint:{"circle-radius":["interpolate",["linear"],["zoom"],16,1.6,20,3.4],
      "circle-color":poiColorExpr(),
      "circle-stroke-color":CONFIG.poi.haloColor,"circle-stroke-width":.6,
      "circle-opacity":.95}});
  map.addLayer({id:"poi-label",type:"symbol",source:"poi",minzoom:CONFIG.poi.labelFromZoom,
    layout:{"text-field":["get","name"],"text-size":11,
      "text-offset":[0,.9],"text-anchor":"top","text-allow-overlap":false,
      "text-padding":3,"symbol-sort-key":["get","si"]},
    paint:{"text-color":poiColorExpr(),
      "text-halo-color":CONFIG.poi.haloColor,
      "text-halo-width":CONFIG.poi.haloWidth}});

  map.on("click","poi-dot", e => {
    const p=e.features[0].properties;
    new maplibregl.Popup({closeButton:false,maxWidth:"250px"})
      .setLngLat(e.features[0].geometry.coordinates)
      .setHTML(`<div class="pop"><b>${p.name}</b><br>${p.cat} · ${p.sub||""}
                <br><span class="a">${p.addr||""}</span></div>`).addTo(map);
  });
  map.on("mouseenter","poi-dot",()=>map.getCanvas().style.cursor="pointer");
  map.on("mouseleave","poi-dot",()=>map.getCanvas().style.cursor="");
}
