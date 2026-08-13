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
  .map(([k,v])=>[k,{c:v.color, nm:v.label, d:v.desc}]));
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
    "blocked", rgb(VERDICT.blocked.c), "needs_cv", rgb(VERDICT.needs_cv.c),
    "clear",   rgb(VERDICT.clear.c),   rgb(VERDICT.unknown.c)];
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
      if(dispatchMode){
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
    paint:{"fill-color":"#ffe680","fill-opacity":0.4}}, "seg-l");
  map.addLayer({id:"cctv-cov-l",type:"line",source:"cctv-cov",
    layout:{visibility:"none"},
    paint:{"line-color":"#ffd84d","line-opacity":0.5,"line-width":1}}, "seg-l");

  /* 소화전 물결을 건물 위로 — 건물에 가리지 않게(seg-l 아래·건물 위). 기여: @marscoolcat */
  ["hyd-pulse2","hyd-pulse"].forEach(l=>{ if(map.getLayer(l)) map.moveLayer(l, "seg-l"); });


  map.on("mousemove","seg-l", e => {
    const p = e.features[0].properties;
    const v = VERDICT[p.verdict] || VERDICT.unknown;
    const n = x => (x==null||x==="") ? "—" : Number(x).toFixed(2)+" m";
    const flags = [ p.midpoint_fallback==="true"||p.midpoint_fallback===true ? "중점 폴백으로 측정" : null,
                    p.inherited==="true"||p.inherited===true ? "인접 구간에서 상속" : null ].filter(Boolean);
    tip.innerHTML =
      `<div class="id">${p.seg_id}</div>
       <div class="vd" style="color:rgb(${v.c})">${v.nm}</div>
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
              base:s.z, top:s.z+s.h, mcolor:`rgb(${s.c[0]},${s.c[1]},${s.c[2]})`}});
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
  const SIGN_TOP_M = 42;          // config.js m-sta 의 h 와 같게 유지할 것
  const SIGN_PX    = 192;         // 아이콘 원본 크기(px). 확대해도 안 뭉개지게 크게 굽는다

  /* 표지판 이미지를 캔버스로 그려 지도에 등록한다.
     빨간 판 + 흰 테두리 + 흰 119. 손그림 시안과 같은 구성이다. */
  function makeSignImage(){
    const c = document.createElement("canvas");
    c.width = c.height = SIGN_PX;
    const g = c.getContext("2d");
    const r = 26, w = SIGN_PX, pad = 9;
    g.beginPath();
    g.moveTo(pad+r, pad);
    g.arcTo(w-pad, pad,     w-pad, w-pad, r);
    g.arcTo(w-pad, w-pad,   pad,   w-pad, r);
    g.arcTo(pad,   w-pad,   pad,   pad,   r);
    g.arcTo(pad,   pad,     w-pad, pad,   r);
    g.closePath();
    g.fillStyle = "#e2221c"; g.fill();
    g.lineWidth = 9; g.strokeStyle = "#ffffff"; g.stroke();
    g.fillStyle = "#ffffff";
    g.textAlign = "center"; g.textBaseline = "middle";
    g.font = "800 78px Pretendard, system-ui, sans-serif";
    g.fillText("119", w/2, w/2 + 3);
    return c;                      // 캔버스를 돌려준다 — 지도와 범례가 같이 쓴다
  }
  const signCanvas = makeSignImage();
  if (!map.hasImage("sign-119"))
    map.addImage("sign-119",
      signCanvas.getContext("2d").getImageData(0,0,SIGN_PX,SIGN_PX), {pixelRatio:2});

  /* 소화전 표지판. 119 와 같은 방식이지만 훨씬 작게 단다.
     소화전은 '어디에 있는지'가 정보의 전부라, 간판이 크면 그 위치를 가린다.
     흰 원판 + 하늘색 테두리(물결과 같은 계열) + 빨간 소화전 픽토그램. */
  const HYD_TOP_M = 16.8;         // config.js m-hyd 총높이와 같게 유지할 것

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

  /* 범례 아이콘. 지도에 쓴 캔버스를 그대로 재사용한다 —
     간판 디자인을 고치면 범례도 자동으로 따라온다. 두 곳에 그리지 말 것. */
  const legendIcon = (elId, canvas) => {
    const el = document.getElementById(elId);
    if(!el) return;
    el.classList.add("sign");
    el.style.background = `url(${canvas.toDataURL()}) center/contain no-repeat`;
  };
  legendIcon("lgi-sta", signCanvas);
  legendIcon("lgi-hyd", hydCanvas);

  map.addLayer({id:"hyd-sign",type:"symbol",source:"hyd",
    layout:{
      "icon-image":"sign-hyd", "icon-anchor":"bottom",
      "icon-allow-overlap":true, "icon-ignore-placement":true,
      /* 119(0.30~1.70)의 약 60%. 위치를 가리지 않을 만큼만 키운다. */
      "icon-size":["interpolate",["linear"],["zoom"],
        14,0.18, 16,0.30, 18,0.55, 20,0.90, 22,0.90]},
    paint:{"icon-translate":[0,0], "icon-translate-anchor":"viewport"}});

  map.addSource("sta-pt",{type:"geojson",data:sta});
  map.addLayer({id:"sta-119",type:"symbol",source:"sta-pt",
    layout:{
      "icon-image":"sign-119",
      "icon-anchor":"bottom",           // 표지판 밑변이 기준점에 온다
      "icon-allow-overlap":true, "icon-ignore-placement":true,
      /* 확대하면 간판도 커진다. 20 이상은 더 키우지 않는다(화면을 다 덮는다). */
      "icon-size":["interpolate",["linear"],["zoom"],
        14,0.30, 16,0.55, 18,1.05, 20,1.70, 22,1.70]},
    paint:{"icon-translate":[0,0], "icon-translate-anchor":"viewport"}});

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
  function placeSigns(){
    const mPerPx = 78271.5170 * Math.cos(map.getCenter().lat * Math.PI/180)
                 / Math.pow(2, map.getZoom());
    const sinP = Math.sin(map.getPitch() * Math.PI/180);
    [["sta-119", SIGN_TOP_M], ["hyd-sign", HYD_TOP_M]].forEach(([id, topM]) => {
      if(!map.getLayer(id)) return;
      map.setPaintProperty(id, "icon-translate", [0, -Math.round(topM*sinP/mPerPx)]);
    });
  }
  placeSigns();
  map.on("move", placeSigns);

  /* ★ 표지판을 맨 위로. 물결만 건물 위로 올리고 표지판을 안 올리면
     '링은 있는데 소화전이 없는' 칸이 생긴다 — 3D 마커(mk-3d)는 건물에 가려지는데
     물결은 건물 위에 강제로 그려지기 때문이다. 표지판은 그 어긋남을 메운다. */
  ["hyd-sign","sta-119"].forEach(l=>{ if(map.getLayer(l)) map.moveLayer(l); });

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
       <i class="sw" style="background:rgb(${v.c})"></i>
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
    bounds:VIEW.emdBounds, fitBoundsOptions:{padding:4},
    style:{version:8, sources:{ mbase:{type:"raster",tiles:CARTO("dark"),tileSize:256,maxzoom:19} },
      layers:[ {id:"mbg",type:"background",paint:{"background-color":"#0a0d13"}},
        {id:"mbase",type:"raster",source:"mbase",paint:{"raster-opacity":.8,"raster-saturation":-.4}} ]}
  });
  const viewRect = () => {
    const b=map.getBounds(), c=map.getCenter(), k=0.4;   // k<1이면 빨간 상자가 작아진다
    const w=c.lng-(c.lng-b.getWest())*k, e=c.lng+(b.getEast()-c.lng)*k;
    const so=c.lat-(c.lat-b.getSouth())*k, no=c.lat+(b.getNorth()-c.lat)*k;
    return {type:"Feature",geometry:{type:"Polygon",coordinates:[[[w,so],[e,so],[e,no],[w,no],[w,so]]]}};
  };
  const posPoint = () => { const c=map.getCenter(); return {type:"Feature",geometry:{type:"Point",coordinates:[c.lng,c.lat]}}; };
  function syncMini(){
    const rv = miniMap.getSource("mview"); if(rv) rv.setData(viewRect());
    const pv = miniMap.getSource("mpos");  if(pv) pv.setData(posPoint());
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
    miniMap.addLayer({id:"mview-f",type:"fill",source:"mview",paint:{"fill-color":"#ff4d3d","fill-opacity":.14}});
    miniMap.addLayer({id:"mview-l",type:"line",source:"mview",paint:{"line-color":"#ff4d3d","line-width":1.6}});
    /* 현위치 — 현재 보는 화면의 중심 */
    miniMap.addSource("mpos",{type:"geojson",data:posPoint()});
    miniMap.addLayer({id:"mpos-halo",type:"circle",source:"mpos",
      paint:{"circle-radius":8,"circle-color":"#4fc3f7","circle-opacity":.22}});
    miniMap.addLayer({id:"mpos-l",type:"circle",source:"mpos",
      paint:{"circle-radius":4,"circle-color":"#4fc3f7","circle-stroke-color":"#fff","circle-stroke-width":1.6}});
    syncMini();
  });
  miniMap.on("error", e => console.error("미니맵 오류", e && e.error));
  map.on("move", syncMini);
  map.on("zoom", syncMini);
  syncMini();

});

/* 미니맵 루트 스타일을 메인 지도 모드와 맞춘다. 기여: @marscoolcat */
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
function setTheme(mode){
  const light = mode === "light";
  document.documentElement.dataset.theme = light ? "light" : "";
  if(!USE_VWORLD) map.getSource("base").setTiles(CARTO(mode));
  map.setPaintProperty("base","raster-opacity", light ? .95 : .82);
  map.setPaintProperty("base","raster-saturation", light ? -.1 : -.35);
  map.setPaintProperty("bg","background-color", light ? "#eef1f5" : "#0a0d13");
  map.setPaintProperty("bld-3d","fill-extrusion-color",
    light ? ["interpolate",["linear"],["get","flo"],1,"#d3d9e2",3,"#c3cad6",6,"#b2bbc9",12,"#9fa9ba"]
          : ["interpolate",["linear"],["get","flo"],1,"#1d2430",3,"#2b3545",6,"#3b4759",12,"#4d5a6f"]);
  map.setPaintProperty("bld-3d","fill-extrusion-opacity", light ? .95 : .88);
  ["mask-l","mask-soft-l"].forEach((l,i)=>{
    map.setPaintProperty(l,"fill-color", light ? "#f4f6f9" : "#05070b");
    map.setPaintProperty(l,"fill-opacity", light ? (i===0?.86:.4) : (i===0?.9:.42));
  });
  map.setPaintProperty("bnd-l","line-color", light ? "#6b7686" : "#5c6b82");
}

/* 토글 */
document.querySelectorAll(".row").forEach(r => r.onclick = () => {
  const t = r.dataset.t, tg = r.querySelector(".tg");
  const on = !tg.classList.contains("on");
  tg.classList.toggle("on", on);
  if(t==="buildings") map.setLayoutProperty("bld-3d","visibility",on?"visible":"none");
  if(t.startsWith("m-")){
    const kind = {"m-sta":"center","m-fs":"station","m-hyd":"hydrant","m-cctv":"cctv"}[t];
    on ? markerOff.delete(kind) : markerOff.add(kind);
    map.setFilter("mk-3d", markerOff.size
      ? ["!",["in",["get","kind"],["literal",[...markerOff]]]] : null);
    if(t==="m-hyd") ["hyd-pulse","hyd-pulse2","hyd-sign"]
      .forEach(l=>{ if(map.getLayer(l)) map.setLayoutProperty(l,"visibility",on?"visible":"none"); });
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
