/* Fire-Lane · 다크/라이트 전환
   ════════════════════════════════════════════════════════════
   CSS 변수·배경타일·건물색·마스크를 한 번에 바꾼다.

   ★ syncCctv 는 시작 시점에도 호출한다. setTheme() 안에만 두면 테마를
     한 번이라도 토글하기 전까지 범례 점이 index.html 에 박힌 옛 색으로 남는다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";
import { vColor } from "../verdict.js";
import { CARTO, USE_VWORLD } from "../basemap.js";
import { segColor } from "../layers/segments.js";
import { styleMiniTheme } from "./minimap.js";

export function syncCctv(light){
  /* 3D 마커 — 파트의 c(다크) / cl(라이트) 를 갈아끼운다. */
  if(S.map.getLayer("mk-3d"))
    S.map.setPaintProperty("mk-3d","fill-extrusion-color",["get", light ? "mcolorL" : "mcolor"]);

  /* 반경 원 — cover 선언이 있는 모든 마커를 돈다.
     ★ 예전에는 "cctv-cov-f" 를 찾았는데 실제 레이어 id 는 spec.id + "-cov-f",
       즉 "m-cctv-cov-f" 다. 이름이 안 맞아 라이트 모드에서 CCTV 원이 다크 색
       그대로 남아 있었다(2026-08-17 수정). 가로등 원은 아예 전환 대상도 아니었다.
     ★ themed 선언이 있으면 CONFIG 의 테마 색표를, 없으면 cover 자신의
       colorLight / opacityLight 를 쓴다. 둘 다 없으면 다크 값을 그대로 쓴다. */
  CONFIG.markers.filter(m=>m.cover).forEach(m=>{
    const cv = m.cover, th = cv.themed ? CONFIG[cv.themed] : null;
    const color = light ? (th ? th.colorLight   : (cv.colorLight   ?? cv.color))
                        : (th ? th.colorDark    : cv.color);
    const op    = light ? (th ? th.opacityLight : (cv.opacityLight ?? cv.opacity ?? 0.10))
                        : (th ? th.opacityDark  : (cv.opacity ?? 0.10));
    const lop   = light ? (cv.lineOpacityLight ?? Math.min(1, op*2.4))
                        : (th ? Math.min(1, op*1.6) : (cv.lineOpacity ?? Math.min(1, op*2.4)));
    const lw    = (light ? (cv.lineWidthLight ?? cv.lineWidth) : cv.lineWidth) ?? 1;
    const f = m.id+"-cov-f", l = m.id+"-cov-l";
    if(S.map.getLayer(f)){
      S.map.setPaintProperty(f,"fill-color", color);
      S.map.setPaintProperty(f,"fill-opacity", op);
    }
    if(S.map.getLayer(l)){
      S.map.setPaintProperty(l,"line-color", color);
      S.map.setPaintProperty(l,"line-opacity", lop);
      S.map.setPaintProperty(l,"line-width", lw);
    }
  });

  const cc = CONFIG.cctvCov;
  const lgc = document.getElementById("lgi-cctv");
  if(lgc) lgc.style.background = light ? cc.colorLight : cc.colorDark;
}

export function setTheme(mode){
  const light = mode === "light";
  S.lightTheme = light;
  document.documentElement.dataset.theme = light ? "light" : "";
  /* 판정 색을 테마에 맞춰 다시 칠한다. 화면 면적을 제일 많이 차지하는 것이
     구간 선이라, 여기만 바꿔도 라이트 모드의 눈부심이 크게 줄어든다. */
  if(S.map.getLayer("seg-l")) S.map.setPaintProperty("seg-l","line-color", segColor());
  syncCctv(light);
  styleMiniTheme();
  if(S.map.getLayer("base-tint"))
    S.map.setPaintProperty("base-tint","background-opacity", light ? CONFIG.lightTint.opacity : 0);
  /* 범례 스와치도 같은 색으로. 지도와 범례가 다른 색이면 범례가 거짓말이 된다. */
  document.querySelectorAll("#legend .lg").forEach(el=>{
    const sw = el.querySelector(".sw");
    if(sw) sw.style.background = `rgb(${vColor(el.dataset.v)})`;
  });
  if(!USE_VWORLD) S.map.getSource("base").setTiles(CARTO(mode));
  S.map.setPaintProperty("base","raster-opacity", light ? .95 : .82);
  S.map.setPaintProperty("base","raster-saturation", light ? -.1 : -.35);
  /* 눈부심은 색이 아니라 '배경 밝기'로 잡는다. 사무실 모니터 기준.
     ★ raster-brightness-max 로 타일의 흰 부분만 눌렀다. 불투명도를 낮추면
       도로명·지명 라벨까지 흐려지지만, 밝기 상한은 라벨 대비를 유지한다. */
  S.map.setPaintProperty("base","raster-brightness-max", light ? .88 : 1);
  S.map.setPaintProperty("bg","background-color", light ? "#dfe3ea" : "#0a0d13");
  S.map.setPaintProperty("bld-3d","fill-extrusion-color",
    light ? ["interpolate",["linear"],["get","flo"],1,"#d3d9e2",3,"#c3cad6",6,"#b2bbc9",12,"#9fa9ba"]
          : ["interpolate",["linear"],["get","flo"],1,"#1d2430",3,"#2b3545",6,"#3b4759",12,"#4d5a6f"]);
  S.map.setPaintProperty("bld-3d","fill-extrusion-opacity", light ? .95 : .88);
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
    S.map.setPaintProperty(l,"fill-color", light ? "#ccd2da" : "#05070b");
    S.map.setPaintProperty(l,"fill-opacity", light ? (i===0?.82:.38) : (i===0?.9:.42));
  });
  /* 동명동 경계. 안과 밖을 가르는 유일한 선이라 라이트에서 더 진하고 굵게 간다. */
  S.map.setPaintProperty("bnd-l","line-color",   light ? "#4a5568" : "#5c6b82");
  S.map.setPaintProperty("bnd-l","line-width",   light ? 2.0 : 1.4);
  S.map.setPaintProperty("bnd-l","line-opacity", light ? .95 : .75);
}

