/* Fire-Lane · 검색
   ════════════════════════════════════════════════════════════
   관제사는 "동명로 25번길 화재" 같은 말을 듣고 시작한다. 지도를 눈으로
   뒤지게 두면 관제 화면이 아니다.

   색인은 이미 있는 데이터로만 만든다. 새 파일을 받지 않는다.
     상호 2,077 · 주소 1,260 · 건물명 189 · 도로명 94
   ★ 건물은 3%만 이름이 있다. 나머지는 검색으로 못 찾는다 —
     그래서 상호와 도로명이 실질적인 진입로다.
   ★ 도로명은 세그먼트가 여러 개라 대표점 하나로 접는다. 신고는 보통
     "○○로 몇번길"로 오므로 도로 전체로 날아가면 충분하다.

   ★ S.DATA.poiRaw / bldRaw / segRaw 는 이미 읽은 피처의 별칭이다.
     data.js 가 캐시하므로 네트워크를 다시 타지 않는다.
   ════════════════════════════════════════════════════════════ */
import { S } from "../state.js";
import { $ } from "../dom.js";

export function initSearch(){
  const map = S.map;
  const DATA = S.DATA;

  const SEARCH = (() => {
    const idx = [], seen = new Set();
    const push = (kind, name, addr, lnglat) => {
      if(!name) return;
      const k = kind + "|" + name + "|" + addr;
      if(seen.has(k)) return;
      seen.add(k);
      idx.push({kind, name, addr: addr || "", c: lnglat,
                key: (name + " " + (addr||"")).toLowerCase().replace(/\s+/g,"")});
    };
    /* 상가 — 상호와 주소 둘 다 검색어에 들어간다 */
    (DATA.poiRaw||[]).forEach(f =>
      push("상가", f.properties.name, f.properties.addr, f.geometry.coordinates));
    /* 건물 — 이름 있는 것만. 폴리곤이라 첫 좌표를 대표점으로 쓴다 */
    (DATA.bldRaw||[]).forEach(f => {
      const nm = f.properties.BULD_NM; if(!nm) return;
      let c = f.geometry.coordinates;
      while(Array.isArray(c[0])) c = c[0];
      push("건물", nm, "", c);
    });
    /* 도로명 — 같은 이름의 세그먼트를 모아 길이 가중 중심점을 잡는다.
       단순 평균을 쓰면 짧은 파편이 많은 쪽으로 중심이 끌려간다. */
    const roads = {};
    (DATA.segRaw||[]).forEach(f => {
      const rn = f.properties.road_name; if(!rn) return;
      const w = f.properties.length_m || 1;
      let c = f.geometry.coordinates;
      if(Array.isArray(c[0][0])) c = c[0];
      const mid = c[Math.floor(c.length/2)];
      const r = roads[rn] || (roads[rn] = {x:0, y:0, w:0, n:0});
      r.x += mid[0]*w; r.y += mid[1]*w; r.w += w; r.n++;
    });
    Object.entries(roads).forEach(([rn, r]) =>
      push("도로", rn, `${r.n}구간`, [r.x/r.w, r.y/r.w]));
    return idx;
  })();

  /* 검색 실행. 공백을 지운 부분일치이고, 앞에서 일치할수록 위로 올린다. */
  function runSearch(raw){
    const q = (raw||"").trim().toLowerCase().replace(/\s+/g,"");
    if(q.length < 1) return [];
    const hit = [];
    for(const it of SEARCH){
      const at = it.key.indexOf(q);
      if(at < 0) continue;
      /* 정렬 점수 — 앞에서 걸릴수록, 이름이 짧을수록(=정확할수록) 위로.
         도로명은 신고 접수 어휘라 살짝 가산한다. */
      hit.push([at * 4 + it.name.length - (it.kind === "도로" ? 12 : 0), it]);
      if(hit.length > 400) break;
    }
    hit.sort((a,b) => a[0] - b[0]);
    return hit.slice(0, 12).map(h => h[1]);
  }

  /* 고른 지점 표시. 붉은 링을 지면에 찍고 지도를 옮긴다. */
  map.addSource("q-pin", {type:"geojson", data:{type:"FeatureCollection", features:[]}});
  map.addLayer({id:"q-pin-l", type:"circle", source:"q-pin",
    paint:{"circle-radius":["interpolate",["linear"],["zoom"],14,7,20,26],
      "circle-color":"#ff4d3d", "circle-opacity":.18,
      "circle-stroke-color":"#ff4d3d", "circle-stroke-width":2.4,
      "circle-pitch-alignment":"map"}});

  function gotoHit(it){
    map.getSource("q-pin").setData({type:"Feature",
      geometry:{type:"Point", coordinates:it.c}, properties:{}});
    /* 도로는 전체를 봐야 하므로 덜 당긴다. 지점은 골목이 보이게 바짝 당긴다. */
    map.flyTo({center:it.c, zoom: it.kind === "도로" ? 16.6 : 18.2, duration:900});
    $("#q-list").classList.remove("show");
  }
  /* ── 검색 UI 배선 ── */
  {
    const inp = $("#q"), list = $("#q-list"), clr = $("#q-clear"), box = $("#search");
    let cur = [], sel = -1;
    const render = () => {
      /* 입력이 있으면 돋보기를 지우기 버튼으로 바꾼다. 같은 자리를 나눠 쓴다. */
      box.classList.toggle("filled", !!inp.value);
      if(!cur.length){
        list.innerHTML = inp.value.trim()
          ? '<div class="none">일치하는 곳이 없습니다</div>' : "";
        list.classList.toggle("show", !!inp.value.trim());
        return;
      }
      list.innerHTML = cur.map((it,i) =>
        `<div class="qi${i===sel?" sel":""}" data-i="${i}">
           <span class="k">${it.kind}</span>
           <span class="nm">${it.name}</span>
           <span class="ad">${it.addr}</span>
         </div>`).join("");
      list.classList.add("show");
    };
    inp.addEventListener("input", () => { cur = runSearch(inp.value); sel = -1; render(); });
    inp.addEventListener("keydown", e => {
      if(e.key === "ArrowDown" || e.key === "ArrowUp"){
        e.preventDefault();
        if(!cur.length) return;
        sel = (sel + (e.key === "ArrowDown" ? 1 : cur.length-1)) % cur.length;
        render();
      } else if(e.key === "Enter"){
        if(cur.length) gotoHit(cur[sel < 0 ? 0 : sel]);
      } else if(e.key === "Escape"){
        inp.value = ""; cur = []; sel = -1; render(); inp.blur();
      }
    });
    list.addEventListener("click", e => {
      const row = e.target.closest(".qi");
      if(row) gotoHit(cur[+row.dataset.i]);
    });
    clr.addEventListener("click", () => {
      inp.value = ""; cur = []; sel = -1; render();
      map.getSource("q-pin").setData({type:"FeatureCollection", features:[]});
      inp.focus();
    });
    /* 지도를 누르면 목록을 접는다. 입력값은 남긴다 — 다시 고를 수 있게. */
    map.on("click", () => list.classList.remove("show"));
  }
}
