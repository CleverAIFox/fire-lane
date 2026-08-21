/* Fire-Lane · 지도 인스턴스 생성
   ════════════════════════════════════════════════════════════
   스타일 정의(소스 5종 + 배경 레이어)와 카메라 제약이 여기 모인다.

   ★ 스코프 좌표를 코드에 하드코딩하지 않는다. view.json 이 정본이다.
     동명동 bbox 는 약 1.04 x 1.04 km. 이 밖으로는 카메라가 나가지 못한다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "./config-access.js";
import { S } from "./state.js";
import { vw, CARTO, USE_VWORLD } from "./basemap.js";

export function createMap(VIEW){
  /* 타일 소스의 bounds. 이 밖의 타일은 아예 요청하지 않는다
     (네트워크 절약 + 화면 비움) */
  const TB = [VIEW.maxBounds[0][0], VIEW.maxBounds[0][1],
              VIEW.maxBounds[1][0], VIEW.maxBounds[1][1]];
  S.VIEW = VIEW; S.TB = TB;

  const map = new maplibregl.Map({
    container:"map", antialias:true, maxPitch:CONFIG.camera.maxPitch,
    center:VIEW.center, zoom:CONFIG.camera.zoom,
    pitch:CONFIG.camera.pitch, bearing:CONFIG.camera.bearing,
    maxBounds:VIEW.maxBounds,          // 팬 한계. 서울까지 끌고 갈 수 없다
    minZoom:VIEW.minZoom,              // 축소 한계. 지구본이 안 나온다
    maxZoom:VIEW.maxZoom,
    style:{ version:8, glyphs:"https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      sources:{
        base:{type:"raster",tiles:USE_VWORLD?[vw("Base")]:CARTO("dark"),tileSize:256,maxzoom:19,bounds:TB,
          attribution:USE_VWORLD?"공간정보 오픈플랫폼(브이월드)":"© OpenStreetMap · CARTO"},
        sat :{type:"raster",tiles:[vw("Satellite")],tileSize:256,maxzoom:19,bounds:TB,
          attribution:"공간정보 오픈플랫폼(브이월드)"},
        /* 항공정사영상 25cm. ortho.py 가 구운 배경 타일이다.
           원본 TIF 에 좌표가 없어 도엽 격자로 역산해 붙였다.
           V-World 위성보다 훨씬 선명하다. 판정에는 쓰지 않는다. */
        /* bounds 는 실제로 구운 타일 범위다(view.json). 없으면 브라우저가
           범위 밖 타일을 요청해 404 가 뜬다. */
        ortho:{type:"raster",tiles:["./data/ortho/{z}/{x}/{y}.jpg"],
          tileSize:256, minzoom:15, maxzoom:18, bounds:VIEW.orthoBounds || TB,
          attribution:"항공정사영상 국토지리정보원"},
        /* 지형. terrain.py 가 구운 Terrain-RGB 타일이다.
           이 소스를 setTerrain 에 물려야 지면이 실제로 휜다.
           건물·선에 z 를 더하는 방식은 지면이 평면이라 공중에 뜬다. */
        dem :{type:"raster-dem",tiles:["./data/terrain/{z}/{x}/{y}.png"],
          tileSize:256, minzoom:12, maxzoom:15, encoding:"mapbox",
          bounds:VIEW.terrainBounds || TB}
      },
      layers:[
        {id:"bg",type:"background",paint:{"background-color":"#0a0d13"}},
        {id:"base",type:"raster",source:"base",paint:{"raster-opacity":.82,"raster-saturation":-.35}},
        /* 지면 색조. 배경(bg)은 타일 아래라 화면에 안 보인다. 색을 실제로 입히려면
           타일 위를 덮어야 한다. 다크에서는 opacity 0 이라 없는 것과 같다. */
        {id:"base-tint",type:"background",
         paint:{"background-color":CONFIG.lightTint.color,"background-opacity":0}},
        {id:"sat", type:"raster",source:"sat", layout:{visibility:"none"},paint:{"raster-opacity":.9}},
        {id:"ortho",type:"raster",source:"ortho",layout:{visibility:"none"},
          paint:{"raster-opacity":.95,"raster-fade-duration":200}}
      ]}
  });
  map.on("style.load", () => {
    if(!CONFIG.terrain.enabled) return;
    try {
      map.setTerrain({source:"dem", exaggeration:CONFIG.terrain.exaggeration});
    } catch(e) { console.warn("지형 적용 실패 — 평면으로 표시합니다.", e); }
  });

  map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),"bottom-right");

  S.map = map;
  return map;
}
