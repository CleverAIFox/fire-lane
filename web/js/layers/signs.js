/* Fire-Lane · 표지판 (기둥 꼭대기 아이콘)
   ════════════════════════════════════════════════════════════
   기여: @marscoolcat

   ★ 왜 박스 면에 직접 프린팅하지 않았나
     MapLibre 의 fill-extrusion 은 면 텍스처를 지원하지 않는다.
     fill-extrusion-pattern 이 있긴 하지만 '반복 타일'용이라 119 가 면마다
     여러 번 잘려서 찍힌다. 한 면에 한 번만 정확히 붙이려면 커스텀
     WebGL 레이어(three.js)로 지도 렌더링을 직접 짜야 한다 — 큰 작업이다.
     그래서 캔버스로 만든 표지판 이미지를 symbol 로 띄워 기둥 위에 세운다.
     화면상 결과는 "빨간 기둥 + 119 표지판"이고, 항상 카메라를 향해
     어느 각도에서 봐도 119 가 읽힌다는 장점이 있다.

   ★ 마커별로 addLayer 를 손으로 쓰던 것을 선언 구동으로 바꿨다.
     결정 83(마커 스펙이 자기 것을 전부 든다)과 같은 취지다. 간판을 하나 더
     달 때 코드에 분기를 추가하지 않는다 — config.js 에 sign 을 적으면 된다.

     스펙:  sign:{ draw:"cctv", top:13.0, dx:0, size:[[14,0.2],[20,1.1]] }
       draw  SIGN_DRAW 에 등록된 그림 이름
       top   기둥 총높이(m). parts 합계와 같게 유지할 것
       dx    좌우 밀기(아이콘 단위, icon-size 가 곱해진다). 겹칠 때만 쓴다
       size  줌별 크기. 없으면 기본 램프

   ★ 간판 높이는 config.js 의 sign.top 이 정본이다. 여기 상수로 두지 말 것 —
     마커가 늘 때마다 두 파일을 같이 고쳐야 하고 실제로 어긋난 적이 있다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";
import { SIGN_PX }         from "../icons/size.js";
import { makeTruckImage }   from "../icons/truck.js";
import { make119Image }     from "../icons/ops119.js";
import { makeHydrantImage } from "../icons/hydrant.js";
import { makeCctvImage }    from "../icons/cctv.js";

/* 간판을 꼭대기보다 더/덜 올리고 싶을 때 쓰는 배수. 1.0 = 정확히 꼭대기.
   화면에서 간판이 낮아 보이면 1.1~1.2 로, 떠 보이면 0.9 로 조정한다. */
const SIGN_LIFT = 1.0;

const bake = cv => cv.getContext("2d").getImageData(0,0,SIGN_PX,SIGN_PX);

const SIGN_DRAW = { truck:makeTruckImage, "119":make119Image,
                    hydrant:makeHydrantImage, cctv:makeCctvImage };
const SIGN_SIZE_DEFAULT = [[14,0.18],[16,0.30],[18,0.55],[20,0.90],[22,0.90]];

export function addSigns(){
  const map = S.map;

  for (const spec of CONFIG.markers){
    const sg = spec.sign, painter = sg && SIGN_DRAW[sg.draw], src = S.DATA[spec.data];
    if (!sg || !painter || !src) continue;
    const img = "sign-" + sg.draw;
    if (!map.hasImage(img)) map.addImage(img, bake(painter()), {pixelRatio:2});
    const ptId = "pt-" + spec.data;
    if (!map.getSource(ptId)) map.addSource(ptId, {type:"geojson", data:src});
    map.addLayer({
      id: spec.id + "-sign", type:"symbol", source: ptId,
      ...(spec.kind ? {filter:["==",["get","kind"],spec.kind]} : {}),
      layout:{
        "icon-image":img, "icon-anchor":"bottom",
        "icon-allow-overlap":true, "icon-ignore-placement":true,
        "icon-offset":[sg.dx || 0, 0],
        "icon-size":["interpolate",["linear"],["zoom"],
          ...(sg.size || SIGN_SIZE_DEFAULT).flat()]},
      paint:{"icon-translate":[0,0], "icon-translate-anchor":"viewport"}});
  }

  /* ★ 표지판을 맨 위로. 물결만 건물 위로 올리고 표지판을 안 올리면
     '링은 있는데 소화전이 없는' 칸이 생긴다 — 3D 마커(mk-3d)는 건물에 가려지는데
     물결은 건물 위에 강제로 그려지기 때문이다. 표지판은 그 어긋남을 메운다. */
  CONFIG.markers.filter(m=>m.sign).forEach(m=>{
    if(map.getLayer(m.id+"-sign")) map.moveLayer(m.id+"-sign"); });
}

/* ── 표지판을 기둥 꼭대기에 붙이기 ────────────────────────────
   기준점은 지면이므로 그대로 두면 기둥 발치에 붙는다. 꼭대기(sign.top)가
   화면에서 몇 px 위인지 매 프레임 계산해 icon-translate 로 밀어 올린다.

   ★ 줌 스톱을 미리 박아두는 방식에서 실시간 계산으로 바꿨다(2025-08). 이유 둘:
     1) MapLibre 는 512px 타일이라 줌 z 의 해상도가 78271.5·cosφ/2^z 다.
        256px 기준(156543)으로 계산하면 정확히 절반만 올라간다.
     2) 세로로 선 기둥이 화면에서 차지하는 길이는 sin(pitch) 에 비례한다.
        위에서 내려다보면(pitch 0) 기둥은 점으로 보여 올릴 필요가 없고,
        눕힐수록 길어진다. cos 을 쓰면 정반대로 움직인다.
   이제 기울이거나 위도가 달라져도 따라붙는다.

   ★ 화면 1px 이 실제 몇 m 인지 지도에 직접 물어본다. '가로 방향'으로만 잰다.
     앞서 경도 +100m 를 재던 방식은 지도를 회전하면 그 100m 가 화면 세로
     성분을 갖게 되고, 세로는 기울기 때문에 눌려 보여서 측정값이 실제보다
     짧게 나온다 → m/px 가 과대평가되고 간판이 덜 올라간다. */
function metersPerPixel(){
  const cv = S.map.getCanvas();
  const cx = cv.clientWidth / 2, cy = cv.clientHeight / 2;
  const a = S.map.unproject([cx - 50, cy]), b = S.map.unproject([cx + 50, cy]);
  const d = a.distanceTo(b);
  return d > 0 ? d / 100 : 1;
}

export function placeSigns(){
  const mPerPx = metersPerPixel();
  const th   = S.map.getPitch() * Math.PI/180;
  const sinP = Math.sin(th), cosP = Math.cos(th);
  /* 카메라~화면중심 거리(px). MapLibre 기본 fov 에서 캔버스 높이의 1.5배다. */
  const camD = (S.map.transform && S.map.transform.cameraToCenterDistance)
             || S.map.getCanvas().clientHeight * 1.5;

  CONFIG.markers.filter(m=>m.sign).forEach(spec => {
    const id = spec.id + "-sign", topM = spec.sign.top;
    if(!S.map.getLayer(id)) return;
    const hPx = topM / mPerPx;                 // 기울이지 않았을 때의 높이(px)
    /* 원근 보정. 기둥 꼭대기는 지면보다 카메라에 가까워서 실제로는 더 크게
       잡힌다. 이 항을 빼면 높은 마커일수록 간판이 눈에 띄게 덜 올라간다. */
    const persp = 1 / Math.max(0.35, 1 - (hPx * cosP) / camD);
    S.map.setPaintProperty(id, "icon-translate",
      [0, -Math.round(SIGN_LIFT * hPx * sinP * persp)]);
  });
}

/* ★ 원본 app.js 에는 여기 `placeSigns();` 한 줄이 있었다. map.on("load")
   본문 안이라 그 시점에 map 이 이미 있었다. 모듈 최상단으로 옮겨오면
   import 시점에 실행되어 S.map 이 아직 null 이다 — 지도가 안 뜬다.
   최초 1회 호출과 "move" 구독은 main.js 가 순서를 알고 한다.
   ★ 모듈 최상단에 부수효과를 두지 마라. 이 파일에서 실제로 겪었다. */
