/* Fire-Lane · 가로등 폴
   ════════════════════════════════════════════════════════════
   수치지형도 1:1,000 의 가로등 폴(C0220000) 1,143점. 실제 위치다.

   ★ 왜 가로등이 두 개인가.

       streetlights    46지점 · 573등    공공데이터포털(광주 동구).
                                         **지번 대표점이라 ±50m 오차.**
                                         등 수 · 관리번호는 이쪽이 정본이다
       lightpoles   1,143점              수치지형도. **실제 폴 위치.**
                                         구분만 있고 등 수는 없다

     둘은 같은 것의 다른 판이 아니라 **다른 데이터**다. 위치를 보려면
     이쪽, 등 수를 보려면 저쪽이다. 그래서 46지점 마커를 지우지 않는다.
     대신 그쪽에는 `cover`(위치 오차 원)가 달려 있어 ±50m 를 화면에서
     말해준다.

   ★ 왜 3D 마커가 아닌가.
     `markers.js` 는 시설을 fill-extrusion 으로 세운다. 1,143개를 그렇게
     하면 무겁고, 무엇보다 소화전 11개 · CCTV 104지점과 **위계가 같아진다.**
     가로등은 배경 정보다. `poi.js` 처럼 점으로 깐다.

   ★ 줌 16 아래에서는 그리지 않는다.
     1,143개가 한 화면에 깔리면 그 자체가 소음이 되어 판정선을 가린다.
     이 지도의 결론은 판정이고 가로등은 맥락이다.

   기여 요청: @marscoolcat — 야간 연출의 재료가 여기 있다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";

/* 구분별 색. 정본은 CONFIG.poles.color 다.
   ★ 손딕셔너리를 두지 않는다(결정 83과 같은 이유). */
export const poleColorExpr = () => {
  const t = CONFIG.poles.color;
  return ["match", ["get", "pole_kind"],
    ...Object.entries(t).filter(([k]) => k !== "other").flat(), t.other];
};

export function addPoles(poles) {
  const map = S.map;
  if (!poles || !poles.features || !poles.features.length) return;

  map.addSource("poles", { type: "geojson", data: poles });

  /* 발광 — 야간 테마에서 가로등처럼 보이게. 반투명 큰 원을 아래 깔고
     그 위에 작은 실점을 얹는다. blur 를 쓰지 않는 이유는 MapLibre 의
     circle-blur 가 줌에 따라 크기가 흔들리기 때문이다. */
  map.addLayer({
    id: "pole-glow", type: "circle", source: "poles",
    minzoom: CONFIG.poles.fromZoom,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 16, 3, 20, 11],
      "circle-color": poleColorExpr(),
      "circle-opacity": 0.18,
      "circle-blur": 0.6,
    },
  });

  map.addLayer({
    id: "pole-dot", type: "circle", source: "poles",
    minzoom: CONFIG.poles.fromZoom,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 16, 1.2, 20, 2.8],
      "circle-color": poleColorExpr(),
      "circle-stroke-color": CONFIG.poles.haloColor,
      "circle-stroke-width": 0.5,
      "circle-opacity": 0.95,
    },
  });
}

/* 팝업. 속성이 `pole_kind` 하나뿐이라 짧다 —
   ★ 없는 값을 지어내지 않는다. 등 수는 이 데이터에 없다. */
export function bindPolePopups() {
  const map = S.map;
  map.on("click", "pole-dot", e => {
    const p = e.features[0].properties;
    new maplibregl.Popup({ closeButton: false, maxWidth: "220px" })
      .setLngLat(e.lngLat)
      .setHTML(`<div class="pop"><b>${p.pole_kind || "가로등 폴"}</b><br>` +
               `<span class="a">수치지형도 1:1,000 · 실제 폴 위치</span></div>`)
      .addTo(map);
  });
  map.on("mouseenter", "pole-dot", () => map.getCanvas().style.cursor = "pointer");
  map.on("mouseleave", "pole-dot", () => map.getCanvas().style.cursor = "");
}
