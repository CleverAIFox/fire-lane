/* Fire-Lane · 로직 계층
   ─────────────────────────────────────────────────────────────
   이 파일은 GIS 담당(@AIMasterFox)의 영역이다.
   데이터 로딩, 레이어 구성, 판정 렌더링, 상호작용.

   UI 담당이 바꿀 값은 여기가 아니라 config.js 에 있다.
   ───────────────────────────────────────────────────────────── */
(async () => {
/* ════════════════════════════════════════════════════════════
   V-World 인증키. sources.yaml 의 basemap.key 와 같은 값이다.
   ★ 브라우저 호출은 &domain= 파라미터가 등록 URL과 문자열까지 정확히
     일치해야 타일이 나온다. 로컬은 V-World에 http://localhost:8000 을
     등록한 뒤 VW_DOMAIN 을 그 값으로 맞출 것.
   ★ WMTS 축 순서는 {z}/{y}/{x} 다. {z}/{x}/{y} 로 쓰면 타일이 어긋난다.
   키가 아직 안 풀렸으면 USE_VWORLD=false 로 두면 CARTO 다크 배경으로 뜬다.
   ════════════════════════════════════════════════════════════ */
const VW_KEY = CONFIG.vworld.key;
const VW_DOMAIN = location.origin;
const USE_VWORLD = CONFIG.vworld.enabled;

const vw = t => `https://api.vworld.kr/req/wmts/1.0.0/${VW_KEY}/${t}/{z}/{y}/{x}.${t==="Satellite"?"jpeg":"png"}?domain=${encodeURIComponent(VW_DOMAIN)}`;
const CARTO = t => ["a","b","c","d"].map(s=>
  `https://${s}.basemaps.cartocdn.com/${t==="light"?"light_all":"dark_all"}/{z}/{x}/{y}@2x.png`);

/* 판정 4종. 런타임에 호모그래피를 돌릴지가 유일한 분기라
   '통과 확실'과 '통과 유력'을 나눌 실익이 없어 하나로 합쳤다.
   세부 구분이 필요하면 툴팁의 width_min_m 을 보면 된다. */
/* 현재는 1단계(도면 프루닝) 결과다. 최종 판정이 아니다.
   라벨에서 "도면상"은 뺐다(2025-08 팀 요청). 대신 좌측 #warn 이
   "도면 기반 1차 분류"라는 단서를 계속 진다. #warn 문구를 지우면
   화면에 단서가 하나도 안 남으니 지우지 말 것. */
const VERDICT = Object.fromEntries(Object.entries(CONFIG.verdict)
  .map(([k,v])=>[k,{c:v.color, cl:v.lightColor||v.color, nm:v.label, d:v.desc}]));
/* 지금 테마에서 쓸 판정 색. setTheme() 이 이 값을 뒤집으면
   지도 선·범례가 함께 따라온다. */
let lightTheme = false;
const vColor = k => (lightTheme ? VERDICT[k].cl : VERDICT[k].c);
/* unknown 의 사유. 회색의 정의는 no_cctv 하나다.
   width(폭 산출 실패)는 설계에 없던 버그 상태이며 0 으로 수렴시키는 중이다.
   그 값이 0 이 아닌 동안에는 툴팁에 사유가 그대로 노출된다. */
const REASON = CONFIG.reason;
const off = new Set();

/* 스코프. web/data/view.json 에서 온다 — 좌표를 여기 하드코딩하지 않는다.
   동명동 bbox 는 약 1.04 x 1.04 km 다. 이 밖으로는 카메라가 나가지 못한다. */
const VIEW = await (await fetch("./data/view.json")).json();
/* 타일 소스의 bounds. 이 밖의 타일은 아예 요청하지 않는다(네트워크 절약 + 화면 비움) */
const TB = [VIEW.maxBounds[0][0], VIEW.maxBounds[0][1], VIEW.maxBounds[1][0], VIEW.maxBounds[1][1]];

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
map.addControl(new maplibregl.ScaleControl({maxWidth:110,unit:"metric"}),"bottom-right");

/* ★ 없는 요소를 참조하면 여기서 죽고 그 뒤 코드가 전부 안 돈다.
   더미를 돌려주고 콘솔에 남긴다. 화면 일부가 비는 건 봐도 알지만
   지도 절반이 안 뜨는 건 원인 찾기가 어렵다. */
const $ = sel => document.querySelector(sel) || (
  console.warn("DOM 없음:", sel), {style:{}, classList:{toggle(){},add(){},remove(){}},
                                   set textContent(v){}, set innerHTML(v){}});
const tip=$("#tip");
  let SEG=null;
/* 출동 모드 · 미니맵. 기여: @marscoolcat (faf9774) */
let dispatchMode=false, miniMap=null;
const DATA={};                 // 마커 데이터. 레이어 갱신 시 재사용
const markerOff=new Set();     // 꺼진 마커 레이어

const POPUP={
  "m-cctv": p=>`<b>CCTV</b> ${p.카메라대수}대<br>${p.카메라화소||"—"} · ${p.촬영방면||""}
                <br>설치 ${p.최초설치}${p.최근설치!==p.최초설치?`~${p.최근설치}`:""} (${p.설치회차}회 증설)
                <br><span class="a">${p.소재지도로명주소||""}</span>`,
  "m-hyd":  p=>`<b>소화전</b> ${p.시설번호||""}<br>${p.상세위치||""}
                <br>설치 ${p.설치연도||"—"} · 보호틀 ${p.보호틀유무||"—"}
                <br><span class="a">${p.소재지도로명주소||""}</span>`,
  "m-sta":  p=>`<b>${p["소방서 및 안전센터명"]}</b><br>출동 시작점
                <br>${p.전화번호||""}<br><span class="a">${p.주소||""}</span>`,
  "m-fs":   p=>`<b>${p["소방서 및 안전센터명"]}</b><br>관할 본서
                <br>${p.전화번호||""}<br><span class="a">${p.주소||""}</span>`,
};

/* 선 굵기 = 실제 노면폭(m). lineWidthUnits:"meters" 라 지도 축척에 맞춰
   그려진다. 즉 화면의 선 두께가 곧 그 골목의 실제 폭이다.
   폭을 못 잰 구간(unknown)은 최소값으로 가늘게 그린다. */
const width = f => {
  let w = f.properties.width_min_m || 1.0;
  if(dispatchMode && f.properties.verdict === "clear") w *= CONFIG.dispatch.clearWidthScale;
  return w;
};

/* 지형은 raster-dem + setTerrain 이 지면 자체를 휘게 해서 처리한다.
   그래서 개별 객체에 z 를 더하면 안 된다. 이중 적용이 되어 공중에 뜬다.
   데이터의 z 컬럼은 분석·검증용으로 남겨둔다. */
const zOf = () => 0;

/* 3D 마커. 건물과 같은 공간에 기둥으로 세운다.
   2D 점은 기울인 화면에서 지면에 붙어 안 보인다. 높이가 있어야 읽힌다.
   높이는 중요도 순서다: 안전센터 > 소방서 > 소화전 > CCTV */

/* 세그먼트 색상 표현식. MapLibre 네이티브 line 으로 그린다.
   ★ deck.gl interleaved 레이어는 map.setTerrain() 을 켜면 지형 아래로 묻힌다.
     피킹은 살아 있어 툴팁은 뜨지만 선이 안 보인다. 네이티브 line 은 지형을 따라간다. */
const segColor = () => {
  const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
  /* no_cctv 갈색 분기는 제거했다(2025-08 팀 결정).
     회색(unknown)의 정의 자체가 "CCTV 없음 / 25m 밖"이라 하위 색이 필요 없다.
     범례에 없는 색이 지도에만 남는 상태가 제일 나쁘다는 판단.
     사유 구분은 구간 툴팁(.rsn)과 #warn 문장이 담당한다. */
  return ["match",["get","verdict"],
    "blocked", rgb(vColor("blocked")), "needs_cv", rgb(vColor("needs_cv")),
    "clear",   rgb(vColor("clear")),   rgb(vColor("unknown"))];
};
const segOpacity = () => dispatchMode
  ? ["case",["==",["get","verdict"],"clear"], 1, CONFIG.dispatch.dimAlpha/255]
  : 0.92;

/* 선 굵기 = 실제 도로 폭(m).
   MapLibre line-width 는 픽셀이므로 줌별 미터당 픽셀로 환산한다.
   위도 35도 기준 px/m = 256 * 2^z / (40075016 * cos35°) */
const PXM = z => 256 * Math.pow(2, z) / (40075016 * Math.cos(35.15 * Math.PI/180));
const segWidth = () => {
  const sc = dispatchMode ? CONFIG.dispatch.clearWidthScale : 1;
  const f = ["case",["==",["get","verdict"],"clear"], sc, 1];
  return ["interpolate",["exponential",2],["zoom"],
    12, ["max", 0.8, ["*",["coalesce",["get","width_min_m"],1], f, PXM(12)]],
    20, ["max", 1.2, ["*",["coalesce",["get","width_min_m"],1], f, PXM(20)]]];
};
function restyleSegments(){
  if(!map.getLayer("seg-l")) return;
  map.setPaintProperty("seg-l","line-opacity", segOpacity());
  map.setPaintProperty("seg-l","line-width",   segWidth());
}

map.on("load", async () => {
  const j = async p => (await fetch(p)).json();
  const [seg,bld,bnd,hyd,sta,cctv,poi] = await Promise.all(
    ["segments","buildings","boundary","hydrants","stations","cctv","poi"]
      .map(n=>j(`./data/${n}.geojson`)));
  SEG = seg;
  Object.assign(DATA, {cctv, hyd, sta});

  /* 마스크 — 세계에서 동명동을 도려낸 폴리곤. 동 밖을 덮어 스코프를 눈으로 못박는다.
     UI 작업 범위가 동명동을 넘지 않는다는 걸 화면 자체가 말해준다. */
  /* 3단 마스크
       동명동      원본 밝기      — 판정 대상
       접근 회랑   살짝 어둡게    — 119안전센터에서 오는 길. 보이되 주역은 아니다
       그 밖       덮는다         — 스코프 밖
     안전센터는 동명동 밖에 있다(대인 서 1.0km / 지산 동 1.2km).
     동 경계만 잠그면 출동 경로가 화면에서 잘린다. */
  const [mask, maskSoft] = await Promise.all([j("./data/mask.geojson"), j("./data/mask_soft.geojson")]);
  map.addSource("mask-soft",{type:"geojson",data:maskSoft});
  map.addLayer({id:"mask-soft-l",type:"fill",source:"mask-soft",
    paint:{"fill-color":"#05070b","fill-opacity":.42}});
  map.addSource("mask",{type:"geojson",data:mask});
  map.addLayer({id:"mask-l",type:"fill",source:"mask",
    paint:{"fill-color":"#05070b","fill-opacity":.9}});

  /* 소화전 물결. 지면에 링이 퍼지고 그 위에 3D 기둥이 선다.
     출동 모드에서만 움직인다. 기여: @marscoolcat */
  map.addSource("hyd",{type:"geojson",data:hyd});
  /* ★ 채운 원 → 테두리 링(2025-08).
     지면에 눕는 원(pitch-alignment:map)은 기울여 보면 타원으로 눌려 면적이 크게
     줄고, 반투명 얼룩처럼 흐려진다. 같은 크기라도 선으로 된 링이 훨씬 잘 잡힌다.
     그래서 circle-opacity(면)는 0 으로 고정하고 circle-stroke-*(선)만 애니메이션한다.
     색은 하늘색 유지 — 소화전 몸통이 빨강으로 바뀌어도 물결은 그대로 간다. */
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
      if(dispatchMode && CONFIG.dispatch.hydPulse){
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

  /* 동 경계 */
  map.addSource("bnd",{type:"geojson",data:bnd});
  map.addLayer({id:"bnd-l",type:"line",source:"bnd",
    paint:{"line-color":"#5c6b82","line-width":1.4,"line-dasharray":[3,2],"line-opacity":.75}});

  /* 건물 3D — MapLibre 자체 fill-extrusion */
  map.addSource("bld",{type:"geojson",data:bld});
  map.addLayer({id:"bld-3d",type:"fill-extrusion",source:"bld",
    paint:{
      "fill-extrusion-color":["interpolate",["linear"],["get","flo"],
        1,"#1d2430", 3,"#2b3545", 6,"#3b4759", 12,"#4d5a6f"],
      "fill-extrusion-height":["interpolate",["linear"],["zoom"],13.6,0,14.4,["get","h"]],
      "fill-extrusion-opacity":.88,
      "fill-extrusion-vertical-gradient":true}});

  /* ── 시설 마커 ───────────────────────────────────────────
     CCTV → 소화전 → 소방서 → 안전센터 순으로 쌓는다.
     중요한 것이 위로 온다. 안전센터가 출동 시작점이라 최상단이다. */

  /* CCTV. 177지점 312대. 야간 답사 대체 근거이자 시간대 분석의 출구다.
     원 크기 = 카메라 대수 */
  /* CCTV 는 지주 + 커버리지 원기둥으로 세운다.
     촬영방면이 전부 360도라 방향 콘이 아니라 원이면 된다.
     커버리지가 안 닿는 골목이 눈에 보이는 것이 요점이다.
     가로등·보안등 공개 데이터가 없어 야간 시인성 논거를 이걸로 대체한다. */


  /* 세그먼트 — 판정 색상. 지형을 따라간다. */
  map.addSource("seg",{type:"geojson",data:seg});
  map.addLayer({id:"seg-l",type:"line",source:"seg",
    layout:{"line-cap":"round","line-join":"round"},
    paint:{"line-color":segColor(),"line-opacity":segOpacity(),"line-width":segWidth()}});

  /* CCTV 커버리지 25m 원 — 지면에 반투명으로. 사각지대가 눈에 보이게. 기여: @marscoolcat */
  const _circle = (lng,lat,m,steps=44) => {
    const dLat=m/111320, dLng=m/(111320*Math.cos(lat*Math.PI/180)), c=[];
    for(let i=0;i<=steps;i++){ const a=2*Math.PI*i/steps; c.push([lng+dLng*Math.cos(a), lat+dLat*Math.sin(a)]); }
    return c;
  };
  const cctvCov = { type:"FeatureCollection", features:
    ((DATA.cctv&&DATA.cctv.features)||[]).filter(f=>f.geometry&&f.geometry.type==="Point").map(f=>({
      type:"Feature", properties:{},
      geometry:{type:"Polygon", coordinates:[ _circle(f.geometry.coordinates[0], f.geometry.coordinates[1], 25) ]} })) };
  map.addSource("cctv-cov",{type:"geojson",data:cctvCov});
  map.addLayer({id:"cctv-cov-f",type:"fill",source:"cctv-cov",
    layout:{visibility:"none"},
    /* 하늘색 — CCTV 마커와 같은 색이라 "이 원이 무엇의 범위인지"가 바로 읽힌다.
       ★ 이 레이어는 "seg-l" 앞에 꽂혀 있어 판정 구간 선이 원 위에 그려진다.
         그래서 원을 밝게 깔아도 도로 색(초록·주황·빨강)은 가려지지 않는다.
       ★ 흰색 때 쓰던 0.5 를 그대로 두면 하늘색은 더 무겁게 깔린다. 진하면 낮출 것. */
    paint:{"fill-color":CONFIG.cctvCov.colorDark,
           "fill-opacity":CONFIG.cctvCov.opacityDark}}, "seg-l");
  map.addLayer({id:"cctv-cov-l",type:"line",source:"cctv-cov",
    layout:{visibility:"none"},
    /* 테두리는 강조하지 않는다. 면과 같은 색·같은 농도로 경계만 잡아준다. */
    paint:{"line-color":CONFIG.cctvCov.colorDark,
           "line-opacity":CONFIG.cctvCov.opacityDark*0.7,"line-width":1}}, "seg-l");

  /* 소화전 물결을 건물 위로 — 건물에 가리지 않게(seg-l 아래·건물 위). 기여: @marscoolcat */
  syncCctv(lightTheme);   // 시작 시 CCTV 색 맞추기(범례 점 포함)
  ["hyd-pulse2","hyd-pulse"].forEach(l=>{ if(map.getLayer(l)) map.moveLayer(l, "seg-l"); });


  map.on("mousemove","seg-l", e => {
    const p = e.features[0].properties;
    const v = VERDICT[p.verdict] || VERDICT.unknown;
    const n = x => (x==null||x==="") ? "—" : Number(x).toFixed(2)+" m";
    const flags = [ p.midpoint_fallback==="true"||p.midpoint_fallback===true ? "중점 폴백으로 측정" : null,
                    p.inherited==="true"||p.inherited===true ? "인접 구간에서 상속" : null ].filter(Boolean);
    tip.innerHTML =
      `<div class="id">${p.seg_id}</div>
       <div class="vd" style="color:rgb(${vColor(p.verdict in VERDICT ? p.verdict : "unknown")})">${v.nm}</div>
       ${p.unknown_reason?`<div class="rsn">${REASON[p.unknown_reason]||""}</div>`:""}
       <dl><dt title="포장된 도로 노면만 잰 폭. 화면의 선 굵기가 이 값이다">도로 폭</dt><dd>${n(p.width_min_m)}</dd>
           <dt title="양쪽 건물 벽에서 벽까지의 거리">벽 사이 폭</dt><dd>${n(p.width_max_m)}</dd>
           <dt>길이</dt><dd>${p.length_m} m</dd>
           <dt title="같은 판정이 끊기지 않고 이어지는 총 길이. 소방청은 100m 이상일 때 지정">같은 상태로 이어진 길이</dt><dd>${p.run_length_m?p.run_length_m+" m":"—"}</dd>
           <dt title="가장 가까운 CCTV 까지의 거리. 25m 초과면 영상판정이 성립하지 않는다">CCTV 거리</dt><dd>${p.cctv_dist_m} m</dd></dl>
       ${(p.nfa_designated==="true"||p.nfa_designated===true)?`<div class="nfa">소방청 지정 기준 충족 · 연속 100m 이상</div>`:""}
       <div class="hint">${v.d}</div>
       ${flags.length?`<div class="flag">${flags.join(" · ")}</div>`:""}`;
    tip.style.display="block";
    tip.style.left = Math.min(e.point.x+14, innerWidth-210)+"px";
    tip.style.top  = (e.point.y+14)+"px";
  });
  map.on("mouseleave","seg-l", () => { tip.style.display="none"; });

  /* 시설 마커 — 건물과 같은 fill-extrusion 으로 그린다.
     ★ deck.gl 레이어는 map.setTerrain() 을 켜면 지형 아래로 묻힌다.
       세그먼트와 같은 문제다. 네이티브 레이어는 지형을 따라간다.
     publish_web.py 가 포인트를 시설 형상의 폴리곤 조각으로 만들어 둔다.
     비율은 실물, 크기는 과장. 소화전 실물 지름 0.2m 로는 안 보인다. */
  /* 마커를 config.js(CONFIG.markers) 스펙으로 런타임 생성. 원기둥(r) + 박스(hw/hl) 지원.
     이제 config.js만 고치면 재발행 없이 바로 반영된다. 기여: @marscoolcat + @AIMasterFox */
  const MK_SRC = {cctv, hyd, sta};
  function buildMarkers(){
    const feats = [];
    for (const spec of CONFIG.markers){
      const src = MK_SRC[spec.source];
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
        spec.parts.forEach((s, i) => {
          let ring;
          if (s.hw != null){            // 박스(직사각형): half-width, half-length
            ring = [[lon-s.hw*mLon, lat-s.hl*mLat],[lon+s.hw*mLon, lat-s.hl*mLat],
                    [lon+s.hw*mLon, lat+s.hl*mLat],[lon-s.hw*mLon, lat+s.hl*mLat],
                    [lon-s.hw*mLon, lat-s.hl*mLat]];
          } else {                      // 원기둥
            const n = s.r < 1 ? 24 : 16;
            ring = Array.from({length:n+1}, (_,k) => { const t = k*2*Math.PI/n;
              return [lon + s.r*Math.cos(t)*mLon, lat + s.r*Math.sin(t)*mLat]; });
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
  map.addSource("markers",{type:"geojson",data:buildMarkers()});
  /* 예전에 있던 idle 재스냅(queryTerrainElevation 으로 z 를 다시 넣던 코드)은 제거했다.
     지형 위 배치는 MapLibre 가 알아서 하므로 재스냅이 곧 이중 가산이었다. */
  map.addLayer({id:"mk-3d",type:"fill-extrusion",source:"markers",
    paint:{
      /* setTheme() 이 "mcolor"(다크) ↔ "mcolorL"(라이트) 로 갈아끼운다 */
      "fill-extrusion-color":["get","mcolor"],
      "fill-extrusion-base":  ["get","base"],   /* 지면 기준 상대 높이. 지형 보정은 MapLibre 담당 */
      "fill-extrusion-height":["get","top"],
      "fill-extrusion-opacity":.95}});

  /* 소방서·안전센터 119 표지 — 텍스트 대신 '이미지'로 찍는다. 기여: @marscoolcat
     ─────────────────────────────────────────────────────────────
     ★ 왜 박스 면에 직접 프린팅하지 않았나
       MapLibre 의 fill-extrusion 은 면 텍스처를 지원하지 않는다.
       fill-extrusion-pattern 이 있긴 하지만 '반복 타일'용이라 119 가 면마다
       여러 번 잘려서 찍힌다. 한 면에 한 번만 정확히 붙이려면 커스텀
       WebGL 레이어(three.js)로 지도 렌더링을 직접 짜야 한다 — 큰 작업이다.
       그래서 캔버스로 만든 표지판 이미지를 symbol 로 띄워 기둥 위에 세운다.
       화면상 결과는 "빨간 기둥 + 119 표지판"이고, 항상 카메라를 향해
       어느 각도에서 봐도 119 가 읽힌다는 장점이 있다. */
  /* 간판을 올릴 높이. config.js 의 각 마커 총높이와 같게 유지할 것.
     소방서(15m)와 안전센터(42m)는 높이가 달라서 값을 따로 둔다. */
  const STA_TOP_M  = 42;          // m-sta  119안전센터 기둥
  const FS_TOP_M   = 15;          // m-fs   소방서 박스
  /* 간판을 꼭대기보다 더/덜 올리고 싶을 때 쓰는 배수. 1.0 = 정확히 꼭대기.
     화면에서 간판이 낮아 보이면 1.1~1.2 로, 떠 보이면 0.9 로 조정한다. */
  const SIGN_LIFT  = 1.0;
  const SIGN_PX    = 192;         // 아이콘 원본 크기(px). 확대해도 안 뭉개지게 크게 굽는다

  /* 표지판 이미지를 캔버스로 그려 지도에 등록한다.
     빨간 판 + 흰 테두리 + 흰 119. 손그림 시안과 같은 구성이다. */
  function makeTruckImage(){
    const W = SIGN_PX, c = document.createElement("canvas");
    c.width = c.height = W;
    const g = c.getContext("2d");
    const RED = "#e2221c";

    /* 빨간 둥근 사각 판 + 흰 테두리.
       소화전 간판은 '원'이라 멀리서도 형태만으로 둘이 구분된다. */
    const r = 30, pad = 10;
    g.beginPath();
    g.moveTo(pad+r, pad);
    g.arcTo(W-pad, pad,   W-pad, W-pad, r); g.arcTo(W-pad, W-pad, pad, W-pad, r);
    g.arcTo(pad,   W-pad, pad,   pad,   r); g.arcTo(pad,   pad,   W-pad, pad,   r);
    g.closePath();
    g.fillStyle = RED; g.fill();
    g.lineWidth = 9; g.strokeStyle = "#ffffff"; g.stroke();

    /* 소방차(사다리차) 픽토그램 — 흰색.
       칸을 나누는 선은 배경과 같은 빨강으로 그어야 덩어리로 안 뭉친다. */
    g.fillStyle = "#ffffff";
    const box = (x,y,w,h,rr=4)=>{ g.beginPath();
      g.moveTo(x+rr,y); g.arcTo(x+w,y,x+w,y+h,rr); g.arcTo(x+w,y+h,x,y+h,rr);
      g.arcTo(x,y+h,x,y,rr); g.arcTo(x,y,x+w,y,rr); g.closePath(); g.fill(); };

    /* 사다리 — 기울여 얹는다 */
    g.save();
    g.translate(70, 60); g.rotate(-0.33);
    box(-44, -7, 88, 14, 4);
    g.fillStyle = RED;
    [-33,-19,-5,9,23].forEach(x => g.fillRect(x, -7, 4, 14));
    g.restore();

    g.fillStyle = "#ffffff";
    box(28, 82, 84, 46, 5);          // 적재함
    box(112, 74, 48, 54, 6);         // 운전석
    box(126, 62, 16, 10, 3);         // 경광등
    g.strokeStyle = "#ffffff"; g.lineWidth = 5; g.lineCap = "round";
    [[134,58,134,44],[124,60,116,50],[144,60,152,50]].forEach(([a,b,cc,d])=>{
      g.beginPath(); g.moveTo(a,b); g.lineTo(cc,d); g.stroke(); });

    g.fillStyle = RED;               // 창문 · 적재함 칸막이
    box(121, 82, 28, 24, 4);
    [46, 64, 82].forEach(x => g.fillRect(x, 100, 14, 5));

    [[58,128],[136,128]].forEach(([x,y])=>{        // 바퀴
      g.beginPath(); g.arc(x, y, 17, 0, Math.PI*2); g.fillStyle="#ffffff"; g.fill();
      g.beginPath(); g.arc(x, y,  7, 0, Math.PI*2); g.fillStyle=RED;       g.fill(); });

    return c;                      // 캔버스를 돌려준다 — 지도와 범례가 같이 쓴다
  }
  /* 소방서용 '119' 텍스트 간판. 안전센터(소방차)와 그림이 달라야
     화면에서 '출동 시작점'과 '관할 본서'가 구분된다. 판 모양·색은 같게 간다. */
  function make119Image(){
    const W = SIGN_PX, c = document.createElement("canvas");
    c.width = c.height = W;
    const g = c.getContext("2d");
    const RED = "#e2221c";

    /* 판 모양·색은 안전센터와 같게 간다. 안의 그림으로만 구분한다. */
    const r = 30, pad = 10;
    g.beginPath();
    g.moveTo(pad+r, pad);
    g.arcTo(W-pad, pad,   W-pad, W-pad, r); g.arcTo(W-pad, W-pad, pad, W-pad, r);
    g.arcTo(pad,   W-pad, pad,   pad,   r); g.arcTo(pad,   pad,   W-pad, pad,   r);
    g.closePath();
    g.fillStyle = RED; g.fill();
    g.lineWidth = 9; g.strokeStyle = "#ffffff"; g.stroke();

    /* 헤드셋 쓴 상황실 요원 — 흰색.
       ★ 그리는 순서가 중요하다. 헤드밴드·마이크를 먼저 깔고 머리·어깨를 나중에
         덮어야 밴드가 머리 뒤로 지나가는 것처럼 보인다.
       ★ 칸을 나누는 선은 배경과 같은 빨강으로 긋는다. 전부 흰색이면 뭉친다. */
    g.lineJoin = "round"; g.lineCap = "round";

    g.beginPath();                       // 헤드밴드(머리 위 아치)
    g.arc(96, 86, 40, Math.PI, 2*Math.PI);
    g.strokeStyle = "#ffffff"; g.lineWidth = 11; g.stroke();

    g.beginPath();                       // 마이크 붐
    g.moveTo(133, 104); g.quadraticCurveTo(130, 128, 108, 132);
    g.strokeStyle = "#ffffff"; g.lineWidth = 8; g.stroke();
    g.beginPath(); g.arc(104, 133, 8, 0, Math.PI*2);
    g.fillStyle = "#ffffff"; g.fill();

    const cup = (x)=>{ g.beginPath();    // 좌·우 이어컵
      g.moveTo(x+6, 74); g.arcTo(x+18, 74, x+18, 104, 6);
      g.arcTo(x+18, 104, x, 104, 6); g.arcTo(x, 104, x, 74, 6);
      g.arcTo(x, 74, x+18, 74, 6); g.closePath();
      g.fillStyle = "#ffffff"; g.fill();
      g.strokeStyle = RED; g.lineWidth = 5; g.stroke(); };
    cup(50); cup(124);

    g.beginPath();                       // 머리
    g.arc(96, 86, 26, 0, Math.PI*2);
    g.fillStyle = "#ffffff"; g.fill();
    g.strokeStyle = RED; g.lineWidth = 5; g.stroke();

    g.beginPath();                       // 어깨(반원 몸통)
    g.arc(96, 162, 40, Math.PI, 2*Math.PI); g.closePath();
    g.fillStyle = "#ffffff"; g.fill();
    g.strokeStyle = RED; g.lineWidth = 5; g.stroke();

    return c;
  }

  const truckCanvas = makeTruckImage();
  const s119Canvas  = make119Image();
  const bake = cv => cv.getContext("2d").getImageData(0,0,SIGN_PX,SIGN_PX);
  if (!map.hasImage("sign-truck")) map.addImage("sign-truck", bake(truckCanvas), {pixelRatio:2});
  if (!map.hasImage("sign-119"))   map.addImage("sign-119",   bake(s119Canvas),  {pixelRatio:2});

  /* 소화전 표지판. 119 와 같은 방식이지만 훨씬 작게 단다.
     소화전은 '어디에 있는지'가 정보의 전부라, 간판이 크면 그 위치를 가린다.
     흰 원판 + 하늘색 테두리(물결과 같은 계열) + 빨간 소화전 픽토그램. */
  const HYD_TOP_M = 10.9;         // config.js m-hyd 총높이와 같게 유지할 것

  function makeHydrantImage(){
    const W = 192, c = document.createElement("canvas");
    c.width = c.height = W;
    const g = c.getContext("2d");
    const RED = "#e2221c";

    /* 빨간 원판 + 흰 테두리 */
    g.beginPath(); g.arc(W/2, W/2, 84, 0, Math.PI*2);
    g.fillStyle = RED; g.fill();
    g.lineWidth = 9; g.strokeStyle = "#ffffff"; g.stroke();

    /* 소화전 픽토그램 — 흰색.
       선까지 흰색으로 두면 몸통·플랜지·방수구가 한 덩어리로 뭉친다.
       그래서 테두리는 배경과 같은 빨강으로 그어 형태를 갈라 놓는다. */
    g.fillStyle = "#ffffff"; g.strokeStyle = RED;
    g.lineWidth = 5; g.lineJoin = "round";
    const box = (x,y,w,h,r=3)=>{ g.beginPath();
      g.moveTo(x+r,y); g.arcTo(x+w,y,x+w,y+h,r); g.arcTo(x+w,y+h,x,y+h,r);
      g.arcTo(x,y+h,x,y,r); g.arcTo(x,y,x+w,y,r); g.closePath(); g.fill(); g.stroke(); };

    box(52, 92, 15, 20, 3);          // 좌측 방수구
    box(125,92, 15, 20, 3);          // 우측 방수구
    box(58, 136, 76, 15, 4);         // 베이스 플랜지
    g.beginPath();                   // 몸통 + 돔
    g.moveTo(72, 136); g.lineTo(72, 70);
    g.arc(96, 70, 24, Math.PI, 0);
    g.lineTo(120, 136); g.closePath();
    g.fill(); g.stroke();
    box(60, 60, 72, 13, 3);          // 어깨 플랜지
    box(89, 30, 14, 12, 3);          // 상단 캡
    g.beginPath();                   // 중앙 밸브 — 빨강으로 반전
    g.arc(96, 104, 13, 0, Math.PI*2);
    g.fillStyle = RED; g.fill();
    g.strokeStyle = "#ffffff"; g.lineWidth = 4; g.stroke();

    return c;
  }
  const hydCanvas = makeHydrantImage();
  if (!map.hasImage("sign-hyd"))
    map.addImage("sign-hyd",
      hydCanvas.getContext("2d").getImageData(0,0,192,192), {pixelRatio:2});


  map.addLayer({id:"hyd-sign",type:"symbol",source:"hyd",
    layout:{
      "icon-image":"sign-hyd", "icon-anchor":"bottom",
      "icon-allow-overlap":true, "icon-ignore-placement":true,
      /* 119(0.30~1.70)의 약 60%. 위치를 가리지 않을 만큼만 키운다. */
      "icon-size":["interpolate",["linear"],["zoom"],
        14,0.18, 16,0.30, 18,0.55, 20,0.90, 22,0.90]},
    paint:{"icon-translate":[0,0], "icon-translate-anchor":"viewport"}});

  map.addSource("sta-pt",{type:"geojson",data:sta});
  /* 안전센터 = 소방차 간판, 소방서 = 119 간판. 같은 sta 소스를 kind 로 가른다. */
  const staSign = (id, img, kind, dx) => map.addLayer({
    id, type:"symbol", source:"sta-pt",
    filter:["==",["get","kind"],kind],
    layout:{
      "icon-image":img, "icon-anchor":"bottom",
      "icon-allow-overlap":true, "icon-ignore-placement":true,
      /* ★ 좌우로 벌린다. 소방서 본서 부지 안에 안전센터가 함께 있는 경우가 많아
         두 간판이 같은 자리에 겹쳐 뒤엣것이 안 보였다.
         icon-offset 단위는 icon-size 가 곱해지므로 확대·축소해도 간격이 유지된다.
         아이콘 폭이 96 단위라 ±52(=104 간격)면 서로 안 닿는다. */
      "icon-offset":[dx, 0],
      /* 기존 값의 약 2/3. 지도를 덮지 않는 선까지 줄였다. */
      "icon-size":["interpolate",["linear"],["zoom"],
        14,0.20, 16,0.36, 18,0.68, 20,1.10, 22,1.10]},
    paint:{"icon-translate":[0,0], "icon-translate-anchor":"viewport"}});

  staSign("sta-truck", "sign-truck", "center",  -52);   // 119안전센터 — 왼쪽
  staSign("sta-119",   "sign-119",   "station",  52);   // 소방서 — 오른쪽

  /* 표지판을 기둥 꼭대기에 붙이기.
     ─────────────────────────────────────────────────────────────
     기준점은 지면이므로 그대로 두면 기둥 발치에 붙는다. 꼭대기(SIGN_TOP_M)가
     화면에서 몇 px 위인지 매 프레임 계산해 icon-translate 로 밀어 올린다.

     ★ 줌 스톱을 미리 박아두는 방식에서 실시간 계산으로 바꿨다(2025-08). 이유 둘:
       1) MapLibre 는 512px 타일이라 줌 z 의 해상도가 78271.5·cosφ/2^z 다.
          256px 기준(156543)으로 계산하면 정확히 절반만 올라간다.
       2) 세로로 선 기둥이 화면에서 차지하는 길이는 sin(pitch) 에 비례한다.
          위에서 내려다보면(pitch 0) 기둥은 점으로 보여 올릴 필요가 없고,
          눕힐수록 길어진다. cos 을 쓰면 정반대로 움직인다.
     이제 기울이거나 위도가 달라져도 따라붙는다. */
  /* 화면 1px 이 실제 몇 m 인지 지도에 직접 물어본다.
     ★ 화면 '가로 방향'으로만 잰다. 앞서 경도 +100m 를 재던 방식은 지도를 회전하면
       그 100m 가 화면 세로 성분을 갖게 되고, 세로는 기울기 때문에 눌려 보여서
       측정값이 실제보다 짧게 나온다 → m/px 가 과대평가되고 간판이 덜 올라간다.
       화면 중앙의 가로선 위 두 점을 unproject 하면 회전·기울기와 무관하다. */
  function metersPerPixel(){
    const cv = map.getCanvas();
    const cx = cv.clientWidth / 2, cy = cv.clientHeight / 2;
    const a = map.unproject([cx - 50, cy]), b = map.unproject([cx + 50, cy]);
    const d = a.distanceTo(b);
    return d > 0 ? d / 100 : 1;
  }

  function placeSigns(){
    const mPerPx = metersPerPixel();
    const th   = map.getPitch() * Math.PI/180;
    const sinP = Math.sin(th), cosP = Math.cos(th);
    /* 카메라~화면중심 거리(px). MapLibre 기본 fov 에서 캔버스 높이의 1.5배다. */
    const camD = (map.transform && map.transform.cameraToCenterDistance)
               || map.getCanvas().clientHeight * 1.5;

    [["sta-truck", STA_TOP_M], ["sta-119", FS_TOP_M],
     ["hyd-sign",  HYD_TOP_M]].forEach(([id, topM]) => {
      if(!map.getLayer(id)) return;
      const hPx = topM / mPerPx;                 // 기울이지 않았을 때의 높이(px)
      /* 원근 보정. 기둥 꼭대기는 지면보다 카메라에 가까워서 실제로는 더 크게
         잡힌다. 이 항을 빼면 높은 마커일수록 간판이 눈에 띄게 덜 올라간다. */
      const persp = 1 / Math.max(0.35, 1 - (hPx * cosP) / camD);
      map.setPaintProperty(id, "icon-translate",
        [0, -Math.round(SIGN_LIFT * hPx * sinP * persp)]);
    });
  }
  placeSigns();
  map.on("move", placeSigns);

  /* ★ 표지판을 맨 위로. 물결만 건물 위로 올리고 표지판을 안 올리면
     '링은 있는데 소화전이 없는' 칸이 생긴다 — 3D 마커(mk-3d)는 건물에 가려지는데
     물결은 건물 위에 강제로 그려지기 때문이다. 표지판은 그 어긋남을 메운다. */
  ["hyd-sign","sta-119","sta-truck"].forEach(l=>{ if(map.getLayer(l)) map.moveLayer(l); });

  map.on("click","mk-3d", e => {
    const p=e.features[0].properties;
    new maplibregl.Popup({closeButton:false,maxWidth:"270px"})
      .setLngLat(e.lngLat)
      .setHTML(`<div class="pop"><b>${p.name}</b><br>${p.sub||""}
                <br><span class="a">${p.addr||""}</span></div>`).addTo(map);
  });
  map.on("mouseenter","mk-3d",()=>map.getCanvas().style.cursor="pointer");
  map.on("mouseleave","mk-3d",()=>map.getCanvas().style.cursor="");

  /* 상가 POI — 네이버 지도처럼 상호를 띄운다.
     지상 1층만 남겨서(간판이 골목에서 보이는 것) 2,077개.
     줌 17 이상에서만 라벨을 그린다. 그 아래는 점만. */
  map.addSource("poi",{type:"geojson",data:poi});
  map.addLayer({id:"poi-dot",type:"circle",source:"poi",minzoom:16,
    paint:{"circle-radius":["interpolate",["linear"],["zoom"],16,1.6,20,3.4],
      "circle-color":["match",["get","cat"],
        "음식","#ff9f6b", "소매","#7fd4ff", "생활서비스","#c9a0ff",
        "숙박","#ffd166", "교육","#8ee6a8", "#8b94a3"],
      "circle-opacity":.85}});
  map.addLayer({id:"poi-label",type:"symbol",source:"poi",minzoom:CONFIG.poi.labelFromZoom,
    layout:{"text-field":["get","name"],"text-size":11,
      "text-offset":[0,.9],"text-anchor":"top","text-allow-overlap":false,
      "text-padding":3,"symbol-sort-key":["get","name"]},
    paint:{"text-color":"#e6ebf2","text-halo-color":"#0a0d13","text-halo-width":1.4}});

  map.on("click","poi-dot", e => {
    const p=e.features[0].properties;
    new maplibregl.Popup({closeButton:false,maxWidth:"250px"})
      .setLngLat(e.features[0].geometry.coordinates)
      .setHTML(`<div class="pop"><b>${p.name}</b><br>${p.cat} · ${p.sub||""}
                <br><span class="a">${p.addr||""}</span></div>`).addTo(map);
  });
  map.on("mouseenter","poi-dot",()=>map.getCanvas().style.cursor="pointer");
  map.on("mouseleave","poi-dot",()=>map.getCanvas().style.cursor="");


  /* 범례 */
  const cnt = {};
  seg.features.forEach(f=>{ const v=f.properties.verdict; cnt[v]=(cnt[v]||0)+1; });
  $("#legend").innerHTML = Object.entries(VERDICT).map(([k,v])=>
    `<div class="lg" data-v="${k}" title="${v.d}">
       <i class="sw" style="background:rgb(${vColor(k)})"></i>
       <span class="nm">${v.nm}</span><span class="ct">${cnt[k]||0}</span></div>`).join("");
  /* 숫자는 전부 데이터에서 계산한다. 본문에 박아두면 재산출할 때마다 썩는다. */
  const nNoCctv = seg.features.filter(f=>f.properties.unknown_reason==="no_cctv").length;
  const nCv     = cnt.needs_cv || 0;
  /* 'CCTV 없어 보류' 범례 줄은 내렸다. unknown 의 하위 구분이라 4색 체계가
     5색으로 보이고 합계도 안 맞아 보인다는 지적. 사유는 구간 툴팁(.rsn)과
     아래 #warn 문장에 남는다. nNoCctv 는 그 문장에서 계속 쓴다. */
  $("#warn").innerHTML =
    `현재 색상은 <b>도면 기반 1차 분류</b>입니다. 최종 판정이 아닙니다.<br>
     주황 <b>${nCv}개</b>만 영상판정으로 갈립니다.
     <b>${nNoCctv}개는 CCTV 유효범위 25m 밖이라 영상판정 자체가 불가능</b>합니다.<br>
     폭 값은 미검증(<span style="font-family:var(--mono)">width_verified: false</span>)입니다.`;
  {
    const q = seg.features.map(f=>f.properties)
      .filter(p=>p.verdict==="needs_cv" && p.width_min_m && p.width_max_m);
    const md = a => a.sort((x,y)=>x-y)[a.length>>1] || 0;
    const lo2 = md(q.map(p=>p.width_min_m)), hi2 = md(q.map(p=>p.width_max_m));
    $("#crit-msg").innerHTML =
      `<b>판정 보류</b> 구간은 벽 사이로는 넓어 보이지만(중앙 ${hi2.toFixed(2)}m)
       실제 도로는 좁습니다(중앙 ${lo2.toFixed(2)}m).
       그 <b>${(hi2-lo2).toFixed(2)}m</b> 차이를 메우는 것이 영상판정의 역할입니다.`;
  }
  document.querySelectorAll(".lg").forEach(el=>el.onclick=()=>{
    const k=el.dataset.v;
    off.has(k) ? off.delete(k) : off.add(k);
    el.classList.toggle("off", off.has(k));
    map.setFilter("seg-l", off.size
      ? ["!",["in",["get","verdict"],["literal",[...off]]]] : null);
  });

  /* 통계 */
  $("#s-seg").textContent = seg.features.length;
  $("#s-bld").textContent = bld.features.length.toLocaleString();
  /* 동명동 안에 있는 것만 센다. 스코프 전체에는 11개가 있지만
     정작 동명동 안은 1개뿐이라는 게 이 프로젝트의 논거다.
     관할 588개 중 공개된 것이 31개(5%)이고 그중 동명동이 1개다. */
  const inEmd = hyd.features.filter(f => {
    const [x, y] = f.geometry.coordinates;
    const [[a, b2], [c, d]] = VIEW.emdBounds;
    return x >= a && x <= c && y >= b2 && y <= d;
  }).length;
  $("#s-hyd").textContent = `${inEmd} / ${hyd.features.length}`;
  const cams = cctv.features.reduce((a,f)=>a+(f.properties.카메라대수||0),0);
  $("#s-cctv").textContent = `${cctv.features.length} / ${cams}`;
  $("#s-poi").textContent = poi.features.length.toLocaleString();
  const feas = seg.features.filter(f=>f.properties.cv_feasible).length;
  $("#s-cv").textContent = `${feas} / ${seg.features.length} (${(feas/seg.features.length*100).toFixed(0)}%)`;


  /* 폭 밴드 */
  const w = seg.features.map(f=>f.properties).filter(p=>p.width_min_m&&p.width_max_m);
  const med = a => a.sort((x,y)=>x-y)[a.length>>1];
  const lo = med(w.map(p=>p.width_min_m)), hi = med(w.map(p=>p.width_max_m));
  $("#b-lo").textContent = lo.toFixed(2)+" m";
  $("#b-hi").textContent = hi.toFixed(2)+" m";
  $("#bar-fill").style.cssText = `left:${lo/12*100}%;right:${100-hi/12*100}%`;
  const amb = w.filter(p=>p.width_min_m<3 && p.width_max_m>=3).length;
  $("#b-msg").innerHTML =
    `중앙값 기준 밴드 폭 <b>${(hi-lo).toFixed(2)}m</b>. 이 폭 안에서 판정이 갈리는 구간이
     <b>${amb}개</b>이고, 그만큼이 영상판정과 현장 실측의 몫입니다.`;

  /* ── 미니맵: 확대(줌 16 이상)하면 우측에 현재 보는 영역을 표시 ──
     기여: @marscoolcat (faf9774). 원본을 그대로 쓴다. */
  miniMap = new maplibregl.Map({
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
    const rv = miniMap.getSource("mview"); if(rv) rv.setData(viewRect());
    /* mpos(파란 점) 레이어를 뺐으므로 갱신할 것이 없다. 되살릴 때 함께 복구할 것.
       const pv = miniMap.getSource("mpos");  if(pv) pv.setData(posPoint()); */
    document.getElementById("minimap").classList.toggle("show", map.getZoom() >= CONFIG.minimap.showFromZoom);
  }
  miniMap.on("load", () => {
    miniMap.addSource("mbnd",{type:"geojson",data:bnd});
    miniMap.addLayer({id:"mbnd-l",type:"line",source:"mbnd",
      paint:{"line-color":"#5c6b82","line-width":1,"line-dasharray":[2,1.5]}});
    /* 루트 — 일반: 판정 4색 / 출동: 초록 강조·나머지 흐림 (styleMiniRoute가 조정) */
    miniMap.addSource("mroute",{type:"geojson",data:seg});
    miniMap.addLayer({id:"mroute-l",type:"line",source:"mroute",
      paint:{"line-color":["match",["get","verdict"],
        "blocked","#ff4d3d","needs_cv","#ffab2e","clear","#4ad18f","#5a6272"],
        "line-width":1.3,"line-opacity":.9}});
    styleMiniRoute();
    /* 현재 보는 영역 */
    miniMap.addSource("mview",{type:"geojson",data:viewRect()});
    miniMap.addLayer({id:"mview-f",type:"fill",source:"mview",
      paint:{"fill-color":"#ff4d3d","fill-opacity":.20}});
    /* 어두운 배경 위 얇은 빨강은 도로망에 묻힌다. 검은 테두리를 먼저 깔아
       주변과 떼어놓고 그 위에 굵은 빨강을 얹는다. */
    miniMap.addLayer({id:"mview-halo",type:"line",source:"mview",
      paint:{"line-color":"#000000","line-width":5,"line-opacity":.55,"line-blur":1}});
    miniMap.addLayer({id:"mview-l",type:"line",source:"mview",
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
  miniMap.on("error", e => console.error("미니맵 오류", e && e.error));
  map.on("move", syncMini);
  map.on("zoom", syncMini);
  syncMini();

});

/* 미니맵 루트 스타일을 메인 지도 모드와 맞춘다. 기여: @marscoolcat */
/* 미니맵 테마. 큰 지도만 밝아지고 미니맵이 검게 남으면 그 자체가 튄다.
   ★ 판정 4색은 큰 지도와 같은 값을 써야 한다. 미니맵 도로가 큰 지도와
     다른 색이면 "같은 구간인데 왜 색이 다르지"가 된다. vColor() 로 맞춘다. */
function styleMiniTheme(){
  if(!miniMap || !miniMap.getLayer || !miniMap.getLayer("mbase")) return;
  const light = lightTheme, rgb = k => `rgb(${vColor(k)})`;
  miniMap.getSource("mbase").setTiles(CARTO(light ? "light" : "dark"));
  miniMap.setPaintProperty("mbg","background-color", light ? "#e8ebef" : "#0a0d13");
  miniMap.setPaintProperty("mbase","raster-opacity",   light ? .9  : .8);
  miniMap.setPaintProperty("mbase","raster-saturation",light ? -.15 : -.4);
  if(miniMap.getLayer("mroute-l"))
    miniMap.setPaintProperty("mroute-l","line-color",["match",["get","verdict"],
      "blocked",rgb("blocked"),"needs_cv",rgb("needs_cv"),"clear",rgb("clear"),rgb("unknown")]);
  if(miniMap.getLayer("mbnd-l"))
    miniMap.setPaintProperty("mbnd-l","line-color", light ? "#4a5568" : "#5c6b82");
  /* 사각형 밑선: 어두운 배경에선 검정, 밝은 배경에선 흰색이라야 떼어 놓인다 */
  if(miniMap.getLayer("mview-halo"))
    miniMap.setPaintProperty("mview-halo","line-color", light ? "#ffffff" : "#000000");
}

function styleMiniRoute(){
  if(!miniMap || !miniMap.getLayer || !miniMap.getLayer("mroute-l")) return;
  if(dispatchMode){
    miniMap.setPaintProperty("mroute-l","line-opacity",["match",["get","verdict"],"clear",1,0.4]);
    miniMap.setPaintProperty("mroute-l","line-width",["match",["get","verdict"],"clear",2,1]);
  } else {
    miniMap.setPaintProperty("mroute-l","line-opacity",0.9);
    miniMap.setPaintProperty("mroute-l","line-width",1.3);
  }
}

/* 다크/라이트 전환. CSS 변수·배경타일·건물색·마스크를 한 번에 바꾼다. */
/* CCTV 색 전환 — 3D 마커·커버리지 원·범례 점을 한 번에 맞춘다.
   ★ 시작 시점에도 호출한다. setTheme() 안에만 두면 테마를 한 번이라도
     토글하기 전까지 범례 점이 index.html 에 박힌 옛 색으로 남는다. */
function syncCctv(light){
  const cc = CONFIG.cctvCov;
  const color = light ? cc.colorLight : cc.colorDark;
  const op    = light ? cc.opacityLight : cc.opacityDark;
  if(map.getLayer("mk-3d"))
    map.setPaintProperty("mk-3d","fill-extrusion-color",["get", light ? "mcolorL" : "mcolor"]);
  if(map.getLayer("cctv-cov-f")){
    map.setPaintProperty("cctv-cov-f","fill-color", color);
    map.setPaintProperty("cctv-cov-f","fill-opacity", op);
  }
  if(map.getLayer("cctv-cov-l")){
    map.setPaintProperty("cctv-cov-l","line-color", color);
    map.setPaintProperty("cctv-cov-l","line-opacity", Math.min(1, op*1.6));
    map.setPaintProperty("cctv-cov-l","line-width", light ? 1.6 : 1);
  }
  const lgc = document.getElementById("lgi-cctv");
  if(lgc) lgc.style.background = color;
}

function setTheme(mode){
  const light = mode === "light";
  lightTheme = light;
  document.documentElement.dataset.theme = light ? "light" : "";
  /* 판정 색을 테마에 맞춰 다시 칠한다. 화면 면적을 제일 많이 차지하는 것이
     구간 선이라, 여기만 바꿔도 라이트 모드의 눈부심이 크게 줄어든다. */
  if(map.getLayer("seg-l")) map.setPaintProperty("seg-l","line-color", segColor());
  syncCctv(light);
  styleMiniTheme();
  if(map.getLayer("base-tint"))
    map.setPaintProperty("base-tint","background-opacity", light ? CONFIG.lightTint.opacity : 0);
  /* 범례 스와치도 같은 색으로. 지도와 범례가 다른 색이면 범례가 거짓말이 된다. */
  document.querySelectorAll("#legend .lg").forEach(el=>{
    const sw = el.querySelector(".sw");
    if(sw) sw.style.background = `rgb(${vColor(el.dataset.v)})`;
  });
  if(!USE_VWORLD) map.getSource("base").setTiles(CARTO(mode));
  map.setPaintProperty("base","raster-opacity", light ? .95 : .82);
  map.setPaintProperty("base","raster-saturation", light ? -.1 : -.35);
  /* 눈부심은 색이 아니라 '배경 밝기'로 잡는다. 사무실 모니터 기준.
     ★ raster-brightness-max 로 타일의 흰 부분만 눌렀다. 불투명도를 낮추면
       도로명·지명 라벨까지 흐려지지만, 밝기 상한은 라벨 대비를 유지한다. */
  map.setPaintProperty("base","raster-brightness-max", light ? .88 : 1);
  map.setPaintProperty("bg","background-color", light ? "#dfe3ea" : "#0a0d13");
  map.setPaintProperty("bld-3d","fill-extrusion-color",
    light ? ["interpolate",["linear"],["get","flo"],1,"#d3d9e2",3,"#c3cad6",6,"#b2bbc9",12,"#9fa9ba"]
          : ["interpolate",["linear"],["get","flo"],1,"#1d2430",3,"#2b3545",6,"#3b4759",12,"#4d5a6f"]);
  map.setPaintProperty("bld-3d","fill-extrusion-opacity", light ? .95 : .88);
  /* 스코프 밖 가리개.
     ★ 라이트에서 흰색(#eef1f5)을 쓰면 지면보다 '밝아서' 죽은 영역으로 안 읽힌다.
       패널 흰색 → 밖 흰색 → 지면 베이지가 이어져 경계가 사라진다.
       다크에서 밖이 더 어두운 것과 같은 논리를 라이트에도 적용해, 지면보다
       한 단계 어두운 회색으로 간다. 색을 더하지 않는 이유는 '관심 밖'이라는
       뜻이라 시선을 끌면 안 되기 때문이다. */
  ["mask-l","mask-soft-l"].forEach((l,i)=>{
    /* 지면(CARTO 베이지)보다는 어둡되 너무 무겁지 않은 지점.
       #b8c0cc(대비 1.36)는 밖이 무거워 시선을 뺏었고, #d8dce2(1.08)는
       티가 안 났다. 그 사이에서 한 칸 밝은 쪽으로 잡는다. */
    map.setPaintProperty(l,"fill-color", light ? "#ccd2da" : "#05070b");
    map.setPaintProperty(l,"fill-opacity", light ? (i===0?.82:.38) : (i===0?.9:.42));
  });
  /* 동명동 경계. 안과 밖을 가르는 유일한 선이라 라이트에서 더 진하고 굵게 간다. */
  map.setPaintProperty("bnd-l","line-color",   light ? "#4a5568" : "#5c6b82");
  map.setPaintProperty("bnd-l","line-width",   light ? 2.0 : 1.4);
  map.setPaintProperty("bnd-l","line-opacity", light ? .95 : .75);
}

/* 토글 */
document.querySelectorAll(".row").forEach(r => r.onclick = () => {
  const t = r.dataset.t, tg = r.querySelector(".tg");
  const on = !tg.classList.contains("on");
  tg.classList.toggle("on", on);
  if(t==="buildings") map.setLayoutProperty("bld-3d","visibility",on?"visible":"none");
  if(t.startsWith("m-")){
    /* ★ buildMarkers() 가 properties.kind 에 넣는 값은 spec.id("m-sta" 등)다.
       예전 코드는 이걸 "center"/"station"/"hydrant"/"cctv" 로 바꿔서 필터에 넣었는데,
       그런 값은 데이터에 없으므로 필터가 아무것도 못 걸렀다. 그래서 토글을 꺼도
       3D 마커가 그대로 남고 간판만 사라졌다. t 를 그대로 쓰는 것이 맞다. */
    on ? markerOff.delete(t) : markerOff.add(t);
    map.setFilter("mk-3d", markerOff.size
      ? ["!",["in",["get","kind"],["literal",[...markerOff]]]] : null);
    /* 마커를 끄면 그 간판도 같이 숨긴다. 안 그러면 간판만 공중에 남는다. */
    const signOf = {"m-hyd":["hyd-pulse","hyd-pulse2","hyd-sign"],
                    "m-sta":["sta-truck"], "m-fs":["sta-119"]}[t];
    if(signOf) signOf.forEach(l=>{
      if(map.getLayer(l)) map.setLayoutProperty(l,"visibility",on?"visible":"none"); });
  }
  if(t==="ortho"){
    map.setLayoutProperty("ortho","visibility",on?"visible":"none");
    /* 항공영상을 켜면 배경 타일을 죽인다. 겹쳐 봐야 지저분하기만 하다. */
    map.setPaintProperty("base","raster-opacity", on ? 0 : .82);
    /* 건물은 영상 위에 반투명으로 얹어 형상만 보이게 한다 */
    map.setPaintProperty("bld-3d","fill-extrusion-opacity", on ? .45 : .88);
  }
  if(t==="poi"){ ["poi-dot","poi-label"].forEach(l=>map.setLayoutProperty(l,"visibility",on?"visible":"none")); }
  if(t==="mask"){ ["mask-l","mask-soft-l"].forEach(l=>map.setLayoutProperty(l,"visibility",on?"visible":"none")); }
  if(t==="theme"){ setTheme(on?"light":"dark"); }
  if(t==="terrain"){
    try {
      map.setTerrain(on ? {source:"dem", exaggeration:CONFIG.terrain.exaggeration} : null);
      /* 지형을 켜고 끄면 MapLibre 가 레이어를 다시 올린다.
         그 과정에서 페인트 표현식이 초기화될 수 있어 다시 칠한다. */
      restyleSegments();
    } catch(e){ console.warn("지형 전환 실패", e); }
  }
  if(t==="dispatch"){
    dispatchMode = on;
    document.getElementById("dispatch-fab")?.classList.toggle("on", on);
    ["cctv-cov-f","cctv-cov-l"].forEach(l=>{ if(map.getLayer(l)) map.setLayoutProperty(l,"visibility",on?"visible":"none"); });
    restyleSegments();
    styleMiniRoute();
  }
});

/* 우하단 플로팅 버튼 — 좌측 출동 모드 토글과 연동. 기여: @marscoolcat */
document.getElementById("dispatch-fab")?.addEventListener("click",
  () => document.querySelector(".row.dispatch")?.click());
})();
