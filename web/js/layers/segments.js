/* Fire-Lane · 세그먼트 레이어 (판정 색·실폭 굵기)
   ────────────────────────────────────────────────────────────
   ★ deck.gl interleaved 레이어는 map.setTerrain() 을 켜면 지형 아래로 묻힌다.
     피킹은 살아 있어 툴팁은 뜨지만 선이 안 보인다. 네이티브 line 은 지형을 따라간다.
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";
import { vColor } from "../verdict.js";

/* 세그먼트 색상 표현식. MapLibre 네이티브 line 으로 그린다.
   ★ deck.gl interleaved 레이어는 map.setTerrain() 을 켜면 지형 아래로 묻힌다.
     피킹은 살아 있어 툴팁은 뜨지만 선이 안 보인다. 네이티브 line 은 지형을 따라간다. */
export const segColor = () => {
  const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
  /* no_cctv 갈색 분기는 제거했다(2025-08 팀 결정).
     회색(unknown)의 정의 자체가 "CCTV 없음 / 25m 밖"이라 하위 색이 필요 없다.
     범례에 없는 색이 지도에만 남는 상태가 제일 나쁘다는 판단.
     사유 구분은 구간 툴팁(.rsn)과 #warn 문장이 담당한다. */
  return ["match",["get","verdict"],
    "blocked", rgb(vColor("blocked")), "needs_cv", rgb(vColor("needs_cv")),
    "clear",   rgb(vColor("clear")),   rgb(vColor("unknown"))];
};
export const segOpacity = () => S.dispatchMode
  ? ["case",["==",["get","verdict"],"clear"], 1, CONFIG.dispatch.dimAlpha/255]
  : 0.92;

/* 선 굵기 = 실제 도로 폭(m).
   MapLibre line-width 는 픽셀이므로 줌별 미터당 픽셀로 환산한다.
   위도 35도 기준 px/m = 256 * 2^z / (40075016 * cos35°) */
export const PXM = z => 256 * Math.pow(2, z) / (40075016 * Math.cos(35.15 * Math.PI/180));
export const segWidth = () => {
  const sc = S.dispatchMode ? CONFIG.dispatch.clearWidthScale : 1;
  const f = ["case",["==",["get","verdict"],"clear"], sc, 1];
  return ["interpolate",["exponential",2],["zoom"],
    12, ["max", 0.8, ["*",["coalesce",["get","width_min_m"],1], f, PXM(12)]],
    20, ["max", 1.2, ["*",["coalesce",["get","width_min_m"],1], f, PXM(20)]]];
};
export function restyleSegments(){
  if(!S.map.getLayer("seg-l")) return;
  S.map.setPaintProperty("seg-l","line-opacity", segOpacity());
  S.map.setPaintProperty("seg-l","line-width",   segWidth());
}

/* ★ 여기 있던 `width(f)` 는 삭제했다. 원본 app.js 에 정의만 있고 호출부가
   0곳이었다 — deck.gl 로 선을 그리던 시절의 잔해다. 지금은 MapLibre
   네이티브 line 이라 굵기를 segWidth() 표현식이 정한다.
   같은 이유로 `zOf()` 와 `POPUP` 도 옮기지 않았다(둘 다 호출부 0곳).
   죽은 코드를 모듈로 옮기면 "쓰이나 보다" 하고 다음 사람이 유지한다. */

/* 세그먼트 — 판정 색상. 지형을 따라간다. */
export function addSegments(seg){
  S.map.addSource("seg",{type:"geojson",data:seg});
  S.map.addLayer({id:"seg-l",type:"line",source:"seg",
    layout:{"line-cap":"round","line-join":"round"},
    paint:{"line-color":segColor(),"line-opacity":segOpacity(),"line-width":segWidth()}});
}
