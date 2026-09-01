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
import { initVehicleSelect } from "./vehicle.js";

/* ── CCTV 표지판은 평시에 끈다 ────────────────────────────────
   기여: @marscoolcat · 2026-09-01

   ★ 왜 끄나. CCTV 지점이 104곳이라 표지판이 상시로 켜져 있으면 노랑 아이콘
     104개가 판정 4색 위를 덮는다. 평시 화면의 주인공은 구간 판정이다.
     반면 출동 모드에서는 CCTV 가 "이 구간 판정을 무엇으로 했는가"의 근거라
     그때는 보이는 편이 낫다.
   ★ 3D 지주는 그대로 둔다. 끄는 것은 꼭대기 표지판뿐이다. 시설이 거기
     있다는 사실 자체는 평시에도 알아야 한다.
   ★ 마커 토글과 출동 모드가 둘 다 이 레이어를 건드리므로 한 함수로 모은다.
     양쪽에서 setLayoutProperty 를 따로 부르면 "출동 모드인데 표지판이 없는"
     상태가 생긴다 — 실제로 그렇게 짰다가 되돌렸다.
   ★ 다른 마커의 표지판(소화전·119)은 평시에도 켜 둔다. 개수가 적고
     인터뷰에서 직접 요청받은 시설이다.
   ──────────────────────────────────────────────────────────── */
export function syncCctvSign(){
  const l = "m-cctv-sign";
  if (!S.map || !S.map.getLayer(l)) return;
  const on = S.dispatchMode && !S.markerOff.has("m-cctv");
  S.map.setLayoutProperty(l, "visibility", on ? "visible" : "none");
}

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

  /* 기준 차량 선택. 패널 DOM 만 쓰므로 지도 로드를 기다리지 않는다.
     ★ 원래 자리는 main.js 다 — 그 파일 머리말이 "새 기능은 layers/ 나 ui/ 에
       모듈을 만들고 여기에는 호출 한 줄만 추가한다"고 스스로 규정하고 있다.
       main.js 는 GIS 담당 파일이라 여기서 부르고 있다. 한 줄 옮길 수 있게
       되면 옮길 것. */
  initVehicleSelect();

  /* CCTV 표지판 초기 상태(평시 = 꺼짐).
     ★ main.js 의 map.on("load") 가 먼저 등록돼 있으므로 addSigns() 다음에
       실행된다. 등록 순서가 곧 실행 순서다. 이 줄을 위로 옮기면 아직 없는
       레이어를 건드려 아무 일도 안 일어난다. */
  map.on("load", syncCctvSign);
/* 토글 */
document.querySelectorAll(".row").forEach(r => r.onclick = () => {
  const t = r.dataset.t, tg = r.querySelector(".tg");
  const on = !tg.classList.contains("on");
  tg.classList.toggle("on", on);
  if(t==="buildings") S.map.setLayoutProperty("bld-3d","visibility",on?"visible":"none");
  /* ★ 가로등 폴은 마커(3D)가 아니라 점 레이어다. 두 레이어를 같이 끈다. */
  if(t==="poles") ["pole-dot","pole-glow"].forEach(l=>{
    if(S.map.getLayer(l)) S.map.setLayoutProperty(l,"visibility",on?"visible":"none"); });
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
    /* ★ 위 forEach 가 표지판을 마커와 같이 켜 버린다. CCTV 만 평시 규칙으로
       다시 덮는다. 순서가 중요하다 — 앞에 두면 forEach 가 도로 켠다. */
    syncCctvSign();
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
    /* CCTV 표지판을 함께 켠다. 출동 모드에서는 판정 근거가 보여야 한다. */
    syncCctvSign();
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
