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
   라벨에 "도면상"을 붙여 확정처럼 읽히지 않게 한다.
   2단계(영상판정)가 붙으면 needs_cv 268개가 갈리고 라벨에서 "도면상"이 빠진다. */
const VERDICT = Object.fromEntries(Object.entries(CONFIG.verdict)
  .map(([k,v])=>[k,{c:v.color, nm:v.label, d:v.desc}]));
/* CCTV 사각으로 죽은 구간은 순수 회색이 아니라 주황을 섞는다.
   "원래 영상판정 대상이었는데 CCTV가 없어서 못 한다"가 색으로 읽혀야 한다. */
const NO_CCTV_COLOR = CONFIG.noCctvColor;
/* unknown 의 이유. 둘 다 회색이지만 성격이 다르다. */
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
      /* 지형. terrain.py 가 구운 Terrain-RGB 타일이다.
         이 소스를 setTerrain 에 물려야 지면이 실제로 휜다.
         건물·선에 z 를 더하는 방식은 지면이 평면이라 공중에 뜬다. */
      dem :{type:"raster-dem",tiles:["./data/terrain/{z}/{x}/{y}.png"],
        tileSize:256, minzoom:12, maxzoom:15, encoding:"mapbox"}
    },
    layers:[
      {id:"bg",type:"background",paint:{"background-color":"#0a0d13"}},
      {id:"base",type:"raster",source:"base",paint:{"raster-opacity":.82,"raster-saturation":-.35}},
      {id:"sat", type:"raster",source:"sat", layout:{visibility:"none"},paint:{"raster-opacity":.9}}
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

const $=s=>document.querySelector(s);
const tip=$("#tip");
let SEG=null, overlay=null;
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
/* 마커는 실제 시설의 실루엣을 원기둥 몇 개로 쌓아 근사한다.
   비율은 실물을 따르되 크기는 약 5배 과장한다. 실물 치수(소화전 0.9m)로 그리면
   1km 시야에서 점 하나가 되어 안 보인다.

   parts = [{r: 반지름m, z: 바닥높이m, h: 높이m, c: 색}] 아래에서 위로.  */
const MARKERS = CONFIG.markers.map(m=>({
  ...m,
  src: () => m.kind ? (DATA[m.source]?.features||[]).filter(f=>f.properties.kind===m.kind)
                    : DATA[m.source],
}));

function markerLayers(){
  const out=[];
  for(const m of MARKERS){
    if(markerOff.has(m.id)) continue;
    const data = m.src();
    m.parts.forEach((pt,i)=>out.push(new deck.ColumnLayer({
      id:`${m.id}-${i}`, data, diskResolution:20, radius:pt.r, extruded:true,
      pickable:i===0, opacity:.95, radiusUnits:"meters",
      getPosition:f=>[...f.geometry.coordinates.slice(0,2), pt.z + zOf(f)],
      getFillColor:pt.c,
      getElevation:()=>pt.h,
      material:{ambient:.5, diffuse:.75, shininess:48, specularColor:[255,255,255]},
      onClick:info=>{
        if(!info.object) return;
        new maplibregl.Popup({closeButton:false,maxWidth:"270px"})
          .setLngLat(info.object.geometry.coordinates)
          .setHTML(`<div class="pop">${POPUP[m.id](info.object.properties)}</div>`)
          .addTo(map);
      },
    })));
  }
  return out;
}

function layers(){
  return [ ...markerLayers(), new deck.GeoJsonLayer({
    id:"segments", data:SEG, pickable:true, stroked:false, filled:false,
    lineWidthUnits:"meters", lineWidthMinPixels:1.2, lineWidthMaxPixels:60,
    getLineColor: f => {
      const p = f.properties;
      const v = VERDICT[p.verdict] || VERDICT.unknown;
      const c = p.unknown_reason === "no_cctv" ? NO_CCTV_COLOR : v.c;
      if(off.has(p.verdict)) return [...c, 26];            // 범례로 끈 판정
      if(dispatchMode)                                      // 갈 수 있는 길만 살린다
        return p.verdict === "clear" ? [...c, 255] : [...c, CONFIG.dispatch.dimAlpha];
      return [...c, 232];
    },
    getLineWidth: width,
    getElevation: zOf, extruded:false,
    updateTriggers:{ getLineColor:[...off, dispatchMode], getLineWidth:[dispatchMode] },
    onHover: info => {
      if(!info.object){ tip.style.display="none"; return; }
      const p = info.object.properties, v = VERDICT[p.verdict]||VERDICT.unknown;
      const n = x => x==null ? "—" : x.toFixed(2)+" m";
      const flags = [ p.midpoint_fallback && "중점 폴백으로 측정",
                      p.inherited && "인접 구간에서 상속" ].filter(Boolean);
      tip.innerHTML =
        `<div class="id">${p.seg_id}</div>
         <div class="vd" style="color:rgb(${v.c})">${v.nm}</div>
         ${p.unknown_reason?`<div class="rsn">${REASON[p.unknown_reason]}</div>`:""}
         <dl><dt title="포장된 도로 노면만 잰 폭. 장애물이 없을 때 확실히 비어 있다. 화면의 선 굵기가 이 값이다">도로 폭</dt><dd>${n(p.width_min_m)}</dd>
             <dt title="양쪽 건물 벽에서 벽까지의 거리. 물리적으로 가능한 최대치">벽 사이 폭</dt><dd>${n(p.width_max_m)}</dd>
             <dt title="이 구간의 길이">길이</dt><dd>${p.length_m} m</dd>
             <dt title="같은 판정이 끊기지 않고 이어지는 총 길이. 소방청은 100m 이상일 때 지정한다">같은 상태로 이어진 길이</dt><dd>${p.run_length_m ? p.run_length_m+" m" : "—"}</dd>
             <dt title="가장 가까운 CCTV 까지의 거리. 25m 를 넘으면 호모그래피 오차가 급증해 영상판정이 성립하지 않는다">CCTV 거리</dt><dd>${p.cctv_dist_m} m</dd></dl>
         ${p.nfa_designated?`<div class="nfa">소방청 지정 기준 충족 · 연속 100m 이상</div>`:""}
         <div class="hint">${v.d}</div>
         ${flags.length?`<div class="flag">${flags.join(" · ")}</div>`:""}`;
      tip.style.display="block";
      tip.style.left = Math.min(info.x+14, innerWidth-200)+"px";
      tip.style.top  = (info.y+14)+"px";
    }
  })];
}

map.on("load", async () => {
  const j = async p => (await fetch(p)).json();
  const [seg,bld,bnd,hyd,sta,cctv] = await Promise.all(
    ["segments","buildings","boundary","hydrants","stations","cctv"]
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
  map.addLayer({id:"hyd-pulse2",type:"circle",source:"hyd",
    paint:{"circle-color":"#4fc3f7","circle-opacity":0,"circle-radius":6,"circle-stroke-width":0}});
  map.addLayer({id:"hyd-pulse",type:"circle",source:"hyd",
    paint:{"circle-color":"#4fc3f7","circle-opacity":0,"circle-radius":6,"circle-stroke-width":0}});
  const HYD_T0 = performance.now(), HYD_SPEED = CONFIG.dispatch.pulseMs;
  (function ripple(now){
    if(map.getLayer("hyd-pulse")){
      if(dispatchMode){
        const t  = ((now - HYD_T0) % HYD_SPEED) / HYD_SPEED;
        const t2 = (t + 0.5) % 1;
        const zf = Math.max(1, Math.min(4, 1 + (map.getZoom() - 15) * 0.7));  // 확대할수록 넓게
        map.setPaintProperty("hyd-pulse",  "circle-radius", (6 + t*26)*zf);
        map.setPaintProperty("hyd-pulse",  "circle-opacity", 0.5*(1-t));
        map.setPaintProperty("hyd-pulse2", "circle-radius", (6 + t2*26)*zf);
        map.setPaintProperty("hyd-pulse2", "circle-opacity", 0.5*(1-t2));
      } else {
        map.setPaintProperty("hyd-pulse",  "circle-opacity", 0);
        map.setPaintProperty("hyd-pulse2", "circle-opacity", 0);
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


  /* deck.gl interleaved — 건물과 z-오클루전이 맞는다 */
  overlay = new deck.MapboxOverlay({interleaved:true, layers:layers()});
  map.addControl(overlay);

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
  $("#lg-nocctv").textContent = nNoCctv;
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
    overlay.setProps({layers:layers()});
  });

  /* 통계 */
  const used = seg.features.filter(f=>f.properties.route_usage>0).length;
  $("#s-seg").textContent = seg.features.length;
  $("#s-use").textContent = `${used} (${(used/seg.features.length*100).toFixed(0)}%)`;
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

  /* ── 미니맵 ────────────────────────────────────────────
     줌 16 이상으로 확대하면 우하단에 전체 조망이 뜬다.
     빨간 상자가 지금 보고 있는 영역이다. 기여: @marscoolcat */
  try {
  miniMap = new maplibregl.Map({
    container:"minimap", interactive:false, attributionControl:false,
    bounds:VIEW.emdBounds, fitBoundsOptions:{padding:4},
    style:{version:8,
      sources:{ mbase:{type:"raster",tiles:CARTO("dark"),tileSize:256,maxzoom:19} },
      layers:[ {id:"mbg",type:"background",paint:{"background-color":"#0a0d13"}},
               {id:"mbase",type:"raster",source:"mbase",
                paint:{"raster-opacity":.8,"raster-saturation":-.4}} ]}
  });
  const viewRect = () => {
    const b=map.getBounds(), c=map.getCenter(), k=0.4;   // k<1 이면 빨간 상자가 작아진다
    const w=c.lng-(c.lng-b.getWest())*k, e=c.lng+(b.getEast()-c.lng)*k;
    const so=c.lat-(c.lat-b.getSouth())*k, no=c.lat+(b.getNorth()-c.lat)*k;
    return {type:"Feature",geometry:{type:"Polygon",
      coordinates:[[[w,so],[e,so],[e,no],[w,no],[w,so]]]}};
  };
  const posPoint = () => { const c=map.getCenter();
    return {type:"Feature",geometry:{type:"Point",coordinates:[c.lng,c.lat]}}; };
  function syncMini(){
    const rv = miniMap.getSource("mview"); if(rv) rv.setData(viewRect());
    const pv = miniMap.getSource("mpos");  if(pv) pv.setData(posPoint());
    document.getElementById("minimap")
      .classList.toggle("show", map.getZoom() >= CONFIG.minimap.showFromZoom);
  }
  window.syncMini = syncMini;
  miniMap.on("load", () => {
    miniMap.addSource("mbnd",{type:"geojson",data:bnd});
    miniMap.addLayer({id:"mbnd-l",type:"line",source:"mbnd",
      paint:{"line-color":"#5c6b82","line-width":1,"line-dasharray":[2,1.5]}});
    miniMap.addSource("mroute",{type:"geojson",data:seg});
    miniMap.addLayer({id:"mroute-l",type:"line",source:"mroute",
      paint:{"line-color":["match",["get","verdict"],
        "blocked",`rgb(${VERDICT.blocked.c})`, "needs_cv",`rgb(${VERDICT.needs_cv.c})`,
        "clear",`rgb(${VERDICT.clear.c})`, `rgb(${VERDICT.unknown.c})`],
        "line-width":1.3,"line-opacity":.9}});
    styleMiniRoute();
    miniMap.addSource("mview",{type:"geojson",data:viewRect()});
    miniMap.addLayer({id:"mview-f",type:"fill",source:"mview",
      paint:{"fill-color":"#ff4d3d","fill-opacity":.14}});
    miniMap.addLayer({id:"mview-l",type:"line",source:"mview",
      paint:{"line-color":"#ff4d3d","line-width":1.6}});
    miniMap.addSource("mpos",{type:"geojson",data:posPoint()});
    miniMap.addLayer({id:"mpos-halo",type:"circle",source:"mpos",
      paint:{"circle-radius":8,"circle-color":"#4fc3f7","circle-opacity":.22}});
    miniMap.addLayer({id:"mpos-l",type:"circle",source:"mpos",
      paint:{"circle-radius":4,"circle-color":"#4fc3f7",
             "circle-stroke-color":"#fff","circle-stroke-width":1.6}});
    syncMini();
  });
  map.on("move", syncMini);
  } catch(e) { console.error("미니맵 초기화 실패", e); }

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
    on ? markerOff.delete(t) : markerOff.add(t);
    overlay.setProps({layers:layers()});
    if(t==="m-hyd") ["hyd-pulse","hyd-pulse2"]
      .forEach(l=>map.setLayoutProperty(l,"visibility",on?"visible":"none"));
  }
  if(t==="mask"){ ["mask-l","mask-soft-l"].forEach(l=>map.setLayoutProperty(l,"visibility",on?"visible":"none")); }
  if(t==="theme"){ setTheme(on?"light":"dark"); }
  if(t==="terrain"){
    try { map.setTerrain(on ? {source:"dem", exaggeration:CONFIG.terrain.exaggeration} : null); }
    catch(e){ console.warn("지형 전환 실패", e); }
  }
  if(t==="dispatch"){
    dispatchMode = on;
    document.getElementById("dispatch-fab")?.classList.toggle("on", on);
    if(overlay) overlay.setProps({layers:layers()});
    styleMiniRoute();
  }
});

/* 우하단 플로팅 버튼 — 좌측 출동 모드 토글과 연동. 기여: @marscoolcat */
document.getElementById("dispatch-fab")?.addEventListener("click",
  () => document.querySelector(".row.dispatch")?.click());
})();
