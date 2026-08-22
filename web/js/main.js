/* Fire-Lane · 부트스트랩
   ════════════════════════════════════════════════════════════
   ★ 이 파일은 순서만 정한다. 로직을 여기 쓰지 마라.
     한 줄이라도 "무엇을 어떻게 그리는가"가 들어오면 그 순간부터
     app.js 1,260줄로 돌아가는 길이 열린다. 새 기능은 layers/ 나 ui/ 에
     모듈을 만들고 여기에는 호출 한 줄만 추가한다.

   순서가 중요한 것 네 가지 — 바꾸면 조용히 깨진다:

     1. 데이터를 먼저 받는다. createMap 은 view.json 의 bounds 를 쓴다.
     2. addSegments 는 addCoverage 보다 먼저다. 커버리지 원이
        "seg-l" 을 기준 레이어로 삼아 그 아래에 끼어든다.
     3. buildToggleRows 가 bindToggles 보다 먼저다. 행을 만든 뒤에
        바인딩해야 onclick 이 붙는다(원본 app.js 주석).
     4. syncCctv 를 시작 시점에 한 번 부른다. setTheme 안에만 두면
        테마를 토글하기 전까지 범례 점이 index.html 의 옛 색으로 남는다.
   ════════════════════════════════════════════════════════════ */
import { S } from "./state.js";
import { CONFIG } from "./config-access.js";
import { loadInitial } from "./data.js";
import { createMap } from "./map.js";

import { addMask, addBoundary, addBuildings } from "./layers/mask.js";
import { addHydrantPulse } from "./layers/hydrants.js";
import { addSegments } from "./layers/segments.js";
import { addCoverage } from "./layers/coverage.js";
import { addMarkers, bindMarkerPopups } from "./layers/markers.js";
import { addSigns, placeSigns } from "./layers/signs.js";
import { addPoi } from "./layers/poi.js";

import { bindTooltip } from "./ui/tooltip.js";
import { initSearch } from "./ui/search.js";
import { buildPoiLegend, buildVerdictLegend } from "./ui/legend.js";
import { renderStats } from "./ui/stats.js";
import { initMiniMap } from "./ui/minimap.js";
import { syncCctv } from "./ui/theme.js";
import { buildToggleRows, bindToggles, bindDispatchFab } from "./ui/toggles.js";

const D = await loadInitial();
const map = createMap(D.view);

/* 마커 데이터를 공유 상태에 얹는다. 레이어 갱신 시 재사용한다. */
Object.assign(S.DATA, Object.fromEntries(
  CONFIG.markers.map(m => m.data).filter(Boolean).map(k => [k, D[k]])));
/* 검색 색인용 원본. 새 파일을 받지 않고 이미 읽은 것을 그대로 쓴다. */
S.DATA.poiRaw = D.poi.features;
S.DATA.bldRaw = D.buildings.features;
S.DATA.segRaw = D.segments.features;
S.SEG = D.segments;

map.on("load", () => {
  addMask(D.mask, D.maskSoft);
  addHydrantPulse(D.hyd);
  addBoundary(D.boundary);
  addBuildings(D.buildings);

  addSegments(D.segments);          // ← addCoverage 의 기준 레이어
  addCoverage();

  addMarkers();
  bindMarkerPopups();
  addSigns();
  placeSigns();
  map.on("move", placeSigns);

  /* 소화전 물결을 건물 위로 — 건물에 가리지 않게(seg-l 아래·건물 위).
     기여: @marscoolcat */
  syncCctv(S.lightTheme);           // 시작 시 CCTV 색 맞추기(범례 점 포함)
  ["hyd-pulse2","hyd-pulse"].forEach(l=>{ if(map.getLayer(l)) map.moveLayer(l, "seg-l"); });

  bindTooltip();
  addPoi(D.poi);
  initSearch();

  buildPoiLegend(D.poi);
  buildVerdictLegend(D.segments);
  renderStats({seg:D.segments, bld:D.buildings, hyd:D.hyd,
               cctv:D.cctv, poi:D.poi});

  initMiniMap(D.segments, D.boundary);
});

buildToggleRows();                  // ← bindToggles 보다 먼저
bindToggles();
bindDispatchFab();
