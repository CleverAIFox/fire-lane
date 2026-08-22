/* Fire-Lane · 좌측 패널 토글
   ════════════════════════════════════════════════════════════
   ★ 마커 토글 행은 CONFIG.markers 가 정본이다. .row 바인딩보다 먼저
     돌아야 한다 — 나중에 넣으면 onclick 이 안 붙는다.
     순서는 config 선언 순서를 뒤집는다(높은 시설이 위로 오게).

   ★ 손딕셔너리를 두지 않는다. 마커를 끌 때 무엇이 딸려 있는지는
     선언(spec.sign / spec.pulse / spec.cover)에서 읽는다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";
import { restyleSegments } from "../layers/segments.js";
import { setTheme } from "./theme.js";
import { styleMiniRoute } from "./minimap.js";

export function buildToggleRows(){
  const host = document.getElementById("mk-toggles");
  if (!host) return;
  [...CONFIG.markers].reverse().forEach(m => {
    const d = document.createElement("div");
    d.className = "row"; d.dataset.t = m.id;
    d.innerHTML = `<span>${m.label}</span><i class="tg on"></i>`;
    host.appendChild(d);
    /* cover 선언이 있으면 반경 원 하위 토글을 같이 만든다.
       ★ 원의 뜻이 마커마다 달라서(CCTV "이 범위를 본다" / 가로등 "이 안에 있다")
         마커와 따로 켜고 끌 수 있어야 한다. */
    if (m.cover){
      const c = document.createElement("div");
      c.className = "row sub"; c.dataset.t = m.id + "-cov";
      const what = m.cover.radius ? `유효범위 ${m.cover.radius}m` : "위치 오차";
      c.innerHTML = `<span>└ ${what} 원</span><i class="tg"></i>`;
      host.appendChild(c);
    }
  });
}

export function bindToggles(){
  const map = S.map;
/* 토글 */
document.querySelectorAll(".row").forEach(r => r.onclick = () => {
  const t = r.dataset.t, tg = r.querySelector(".tg");
  const on = !tg.classList.contains("on");
  tg.classList.toggle("on", on);
  if(t==="buildings") S.map.setLayoutProperty("bld-3d","visibility",on?"visible":"none");
  if(t.startsWith("m-")){
    /* ★ buildMarkers() 가 properties.kind 에 넣는 값은 spec.id("m-sta" 등)다.
       예전 코드는 이걸 "center"/"station"/"hydrant"/"cctv" 로 바꿔서 필터에 넣었는데,
       그런 값은 데이터에 없으므로 필터가 아무것도 못 걸렀다. 그래서 토글을 꺼도
       3D 마커가 그대로 남고 간판만 사라졌다. t 를 그대로 쓰는 것이 맞다. */
    on ? S.markerOff.delete(t) : S.markerOff.add(t);
    S.map.setFilter("mk-3d", S.markerOff.size
      ? ["!",["in",["get","kind"],["literal",[...S.markerOff]]]] : null);
    /* 마커를 끄면 딸린 것들도 같이 숨긴다. 안 그러면 간판만 공중에 남는다.
       ★ 손딕셔너리를 두지 않는다. 무엇이 딸려 있는지는 선언에서 읽는다. */
    const spec = CONFIG.markers.find(m => m.id === t) || {};
    [ ...(spec.sign  ? [t + "-sign"] : []),
      ...(spec.pulse ? ["hyd-pulse","hyd-pulse2"] : []),
      ...(spec.cover ? [t + "-cov-f", t + "-cov-l"] : []) ]
      .forEach(l=>{ if(S.map.getLayer(l)) S.map.setLayoutProperty(l,"visibility",on?"visible":"none"); });
    if(spec.cover && !on)
      document.querySelector(`.row[data-t="${t}-cov"] .tg`)?.classList.remove("on");
  }
  /* 반경 원 하위 토글. m-cctv-cov / m-light-cov 처럼 마커 id + "-cov" 다. */
  if(t.endsWith("-cov")){
    [t+"-f", t+"-l"].forEach(l=>{
      if(S.map.getLayer(l)) S.map.setLayoutProperty(l,"visibility",on?"visible":"none"); });
  }
  if(t==="ortho"){
    S.map.setLayoutProperty("ortho","visibility",on?"visible":"none");
    /* 항공영상을 켜면 배경 타일을 죽인다. 겹쳐 봐야 지저분하기만 하다. */
    S.map.setPaintProperty("base","raster-opacity", on ? 0 : .82);
    /* 건물은 영상 위에 반투명으로 얹어 형상만 보이게 한다 */
    S.map.setPaintProperty("bld-3d","fill-extrusion-opacity", on ? .45 : .88);
  }
  if(t==="poi"){ ["poi-dot","poi-label"].forEach(l=>S.map.setLayoutProperty(l,"visibility",on?"visible":"none")); }
  if(t==="mask"){ ["mask-l","mask-soft-l"].forEach(l=>S.map.setLayoutProperty(l,"visibility",on?"visible":"none")); }
  if(t==="theme"){ setTheme(on?"light":"dark"); }
  if(t==="terrain"){
    try {
      S.map.setTerrain(on ? {source:"dem", exaggeration:CONFIG.terrain.exaggeration} : null);
      /* 지형을 켜고 끄면 MapLibre 가 레이어를 다시 올린다.
         그 과정에서 페인트 표현식이 초기화될 수 있어 다시 칠한다. */
      restyleSegments();
    } catch(e){ console.warn("지형 전환 실패", e); }
  }
  if(t==="dispatch"){
    S.dispatchMode = on;
    document.getElementById("dispatch-fab")?.classList.toggle("on", on);
    CONFIG.markers.filter(m=>m.cover).forEach(m=>{
      [m.id+"-cov-f", m.id+"-cov-l"].forEach(l=>{
        if(S.map.getLayer(l)) S.map.setLayoutProperty(l,"visibility",on?"visible":"none"); });
      /* 패널의 하위 토글 표시도 같이 맞춘다. 화면과 스위치가 어긋나면 안 된다. */
      document.querySelector(`.row[data-t="${m.id}-cov"] .tg`)?.classList.toggle("on", on);
    });
    restyleSegments();
    styleMiniRoute();
  }
});
}

/* 우하단 플로팅 버튼 — 좌측 출동 모드 토글과 연동. 기여: @marscoolcat */
export function bindDispatchFab(){
  document.getElementById("dispatch-fab")?.addEventListener("click",
    () => document.querySelector(".row.dispatch")?.click());
}
