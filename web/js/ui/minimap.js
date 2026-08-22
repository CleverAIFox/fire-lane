/* Fire-Lane · 미니맵
   ════════════════════════════════════════════════════════════
   확대(줌 16 이상)하면 우측에 현재 보는 영역을 표시한다.
   기여: @marscoolcat (faf9774)

   ★ 북쪽 고정. 큰 지도를 돌려도 미니맵은 따라 돌지 않는다.
     미니맵의 역할이 "전체에서 지금 어디인가"라, 기준이 흔들리면 쓸모가 없다.
     syncMini() 는 사각형만 갱신하고 bearing 은 건드리지 않는다.

   ★ 판정 4색은 큰 지도와 같은 값을 써야 한다. 미니맵 도로가 큰 지도와
     다른 색이면 "같은 구간인데 왜 색이 다르지"가 된다. vColor() 로 맞춘다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";
import { CARTO } from "../basemap.js";
import { vColor } from "../verdict.js";

export function initMiniMap(seg, bnd){
  const map = S.map, VIEW = S.VIEW;
  S.miniMap = new maplibregl.Map({
    container:"minimap", interactive:false, attributionControl:false,
    /* ★ 북쪽 고정. 큰 지도를 돌려도 미니맵은 따라 돌지 않는다.
       미니맵의 역할이 "전체에서 지금 어디인가"라, 기준이 흔들리면 쓸모가 없다.
       syncMini() 는 사각형만 갱신하고 bearing 은 건드리지 않는다. */
    bearing:0, pitch:0,
    bounds:VIEW.emdBounds, fitBoundsOptions:{padding:4},
    style:{version:8, sources:{ mbase:{type:"raster",tiles:CARTO("dark"),tileSize:256,maxzoom:19} },
      layers:[ {id:"mbg",type:"background",paint:{"background-color":"#0a0d13"}},
        {id:"mbase",type:"raster",source:"mbase",paint:{"raster-opacity":.8,"raster-saturation":-.4}} ]}
  });
  /* 지금 보는 영역을 미니맵에 그릴 사각형.
     ─────────────────────────────────────────────────────────────
     ★ 예전에는 map.getBounds() 를 썼다. 그건 화면을 감싸는 '북향 최소 사각형'이라,
       지도를 돌리면 실제로 보는 영역보다 커지고 방향도 사라진다(초기 bearing 이
       -18 도라 항상 어긋나 있었다). 화면 좌표를 직접 지리 좌표로 바꿔서
       bearing 만큼 기울어진 진짜 사각형을 그린다.
     ★ 세로 크기는 화면 '아래쪽' 절반으로 잰다. 기울인 상태에서 위쪽 끝은
       지평선에 가까워 좌표가 발산할 수 있기 때문이다.
     ★ k 는 사각형 크기 배수다. 1 이면 화면 그대로, 작을수록 사각형이 작아진다. */
  const viewRect = () => {
    const cv = map.getCanvas(), W = cv.clientWidth, H = cv.clientHeight, k = 0.9;
    const c = map.getCenter();
    const halfW = c.distanceTo(map.unproject([W/2 + W*k/2, H/2]));   // m
    const halfH = c.distanceTo(map.unproject([W/2, H/2 + H*k/2]));   // m
    const b = map.getBearing() * Math.PI/180;
    const mLat = 111320, mLng = 111320 * Math.cos(c.lat * Math.PI/180);
    const ring = [[-halfW,-halfH],[halfW,-halfH],[halfW,halfH],[-halfW,halfH]]
      .map(([x,y]) => {           // x=화면 오른쪽, y=화면 아래
        const e =  x*Math.cos(b) - y*Math.sin(b);
        const n = -x*Math.sin(b) - y*Math.cos(b);
        return [c.lng + e/mLng, c.lat + n/mLat];
      });
    ring.push(ring[0]);
    return {type:"Feature",geometry:{type:"Polygon",coordinates:[ring]}};
  };

  function syncMini(){
    const rv = S.miniMap.getSource("mview"); if(rv) rv.setData(viewRect());
    /* mpos(파란 점) 레이어를 뺐으므로 갱신할 것이 없다. 되살릴 때 함께 복구할 것.
       const pv = S.miniMap.getSource("mpos");  if(pv) pv.setData(posPoint()); */
    document.getElementById("minimap").classList.toggle("show", map.getZoom() >= CONFIG.minimap.showFromZoom);
  }
  S.miniMap.on("load", () => {
    S.miniMap.addSource("mbnd",{type:"geojson",data:bnd});
    S.miniMap.addLayer({id:"mbnd-l",type:"line",source:"mbnd",
      paint:{"line-color":"#5c6b82","line-width":1,"line-dasharray":[2,1.5]}});
    /* 루트 — 일반: 판정 4색 / 출동: 초록 강조·나머지 흐림 (styleMiniRoute가 조정) */
    S.miniMap.addSource("mroute",{type:"geojson",data:seg});
    S.miniMap.addLayer({id:"mroute-l",type:"line",source:"mroute",
      paint:{"line-color":["match",["get","verdict"],
        "blocked","#ff4d3d","needs_cv","#ffab2e","clear","#4ad18f","#5a6272"],
        "line-width":1.3,"line-opacity":.9}});
    styleMiniRoute();
    /* 현재 보는 영역 */
    S.miniMap.addSource("mview",{type:"geojson",data:viewRect()});
    S.miniMap.addLayer({id:"mview-f",type:"fill",source:"mview",
      paint:{"fill-color":"#ff4d3d","fill-opacity":.20}});
    /* 어두운 배경 위 얇은 빨강은 도로망에 묻힌다. 검은 테두리를 먼저 깔아
       주변과 떼어놓고 그 위에 굵은 빨강을 얹는다. */
    S.miniMap.addLayer({id:"mview-halo",type:"line",source:"mview",
      paint:{"line-color":"#000000","line-width":5,"line-opacity":.55,"line-blur":1}});
    S.miniMap.addLayer({id:"mview-l",type:"line",source:"mview",
      paint:{"line-color":"#ff4d3d","line-width":2.6}});
    /* 파란 점(화면 중심 표시)은 제거했다(2025-08).
       ★ 빨간 사각형이 이미 "지금 보는 영역"을 보여주므로 중심점은 정보가 겹친다.
       ★ 지도에서 파란 점은 보통 GPS 내 위치로 읽힌다. 실제로는 카메라가 향한
         지점일 뿐이라 오해를 부른다. 나중에 실제 출동 차량 위치를 찍을 때
         그 자리를 비워두는 편이 낫다.
       posPoint() 함수와 syncMini() 의 갱신 줄은 그대로 두었으니
       되살리려면 아래 세 줄만 복구하면 된다. */
    styleMiniTheme();
    syncMini();
  });
  S.miniMap.on("error", e => console.error("미니맵 오류", e && e.error));
  map.on("move", syncMini);
  map.on("zoom", syncMini);
  syncMini();
}

/* 미니맵 루트 스타일을 메인 지도 모드와 맞춘다. 기여: @marscoolcat */
/* 미니맵 테마. 큰 지도만 밝아지고 미니맵이 검게 남으면 그 자체가 튄다.
   ★ 판정 4색은 큰 지도와 같은 값을 써야 한다. 미니맵 도로가 큰 지도와
     다른 색이면 "같은 구간인데 왜 색이 다르지"가 된다. vColor() 로 맞춘다. */
export function styleMiniTheme(){
  if(!S.miniMap || !S.miniMap.getLayer || !S.miniMap.getLayer("mbase")) return;
  const light = S.lightTheme, rgb = k => `rgb(${vColor(k)})`;
  S.miniMap.getSource("mbase").setTiles(CARTO(light ? "light" : "dark"));
  S.miniMap.setPaintProperty("mbg","background-color", light ? "#e8ebef" : "#0a0d13");
  S.miniMap.setPaintProperty("mbase","raster-opacity",   light ? .9  : .8);
  S.miniMap.setPaintProperty("mbase","raster-saturation",light ? -.15 : -.4);
  if(S.miniMap.getLayer("mroute-l"))
    S.miniMap.setPaintProperty("mroute-l","line-color",["match",["get","verdict"],
      "blocked",rgb("blocked"),"needs_cv",rgb("needs_cv"),"clear",rgb("clear"),rgb("unknown")]);
  if(S.miniMap.getLayer("mbnd-l"))
    S.miniMap.setPaintProperty("mbnd-l","line-color", light ? "#4a5568" : "#5c6b82");
  /* 사각형 밑선: 어두운 배경에선 검정, 밝은 배경에선 흰색이라야 떼어 놓인다 */
  if(S.miniMap.getLayer("mview-halo"))
    S.miniMap.setPaintProperty("mview-halo","line-color", light ? "#ffffff" : "#000000");
}

export function styleMiniRoute(){
  if(!S.miniMap || !S.miniMap.getLayer || !S.miniMap.getLayer("mroute-l")) return;
  if(S.dispatchMode){
    S.miniMap.setPaintProperty("mroute-l","line-opacity",["match",["get","verdict"],"clear",1,0.4]);
    S.miniMap.setPaintProperty("mroute-l","line-width",["match",["get","verdict"],"clear",2,1]);
  } else {
    S.miniMap.setPaintProperty("mroute-l","line-opacity",0.9);
    S.miniMap.setPaintProperty("mroute-l","line-width",1.3);
  }
}
