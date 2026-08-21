/* Fire-Lane · 구간 툴팁
   ────────────────────────────────────────────────────────────
   ★ 건물 사이 폭 결손은 두 가지다. 대로는 건물이 40m 밖이라 잴 수 없고(정상),
     골목은 건물 폴리곤이 없어 못 잰 것이다(결손). 앞은 도로 폭만으로 판정이
     끝나지만 뒤는 blocked 판정 자체가 성립하지 않는다 — verdict() 가
     wmax 로만 blocked 를 낸다. "—" 하나로 뭉개면 화면이 그 차이를 숨긴다.
   ──────────────────────────────────────────────────────────── */
import { S } from "../state.js";
import { $ } from "../dom.js";
import { VERDICT, REASON, vColor } from "../verdict.js";

export function bindTooltip(){
  const tip = $("#tip");
  S.map.on("mousemove","seg-l", e => {
    const p = e.features[0].properties;
    const v = VERDICT[p.verdict] || VERDICT.unknown;
    const n = x => (x==null||x==="") ? "—" : Number(x).toFixed(2)+" m";
    /* 건물 사이 폭 결손은 두 가지다. 대로는 건물이 40m 밖이라 잴 수 없고(정상),
       골목은 건물 폴리곤이 없어 못 잰 것이다(결손). 앞은 도로 폭만으로 판정이
       끝나지만 뒤는 blocked 판정 자체가 성립하지 않는다 — verdict() 가
       wmax 로만 blocked 를 낸다. "—" 하나로 뭉개면 화면이 그 차이를 숨긴다. */
    const wmax = p => {
      if (p.width_max_m!=null && p.width_max_m!=="") return n(p.width_max_m);
      return (Number(p.width_min_m) >= 7.0)
        ? `<span class="na">측정 불필요 · 도로 폭으로 판정</span>`
        : `<span class="na warn">측정 실패 · 판정 근거 부족</span>`;
    };
    const flags = [ p.midpoint_fallback==="true"||p.midpoint_fallback===true ? "중점 폴백으로 측정" : null,
                    p.inherited==="true"||p.inherited===true ? "인접 구간에서 상속" : null ].filter(Boolean);
    tip.innerHTML =
      `<div class="id">${p.road_name||"도로명 없음"} · ${p.seg_no}구간</div>
       <div class="vd" style="color:rgb(${vColor(p.verdict in VERDICT ? p.verdict : "unknown")})">${v.nm}</div>
       ${p.unknown_reason?`<div class="rsn">${REASON[p.unknown_reason]||""}</div>`:""}
       <dl><dt title="포장된 도로 노면만 잰 폭. 화면의 선 굵기가 이 값이다">도로 폭</dt><dd>${n(p.width_min_m)}</dd>
           <dt title="양쪽 건물 벽에서 벽까지의 거리. 못 잰 구간은 판정이 관대해진다(MASTER §11)">건물 사이 폭</dt><dd>${wmax(p)}</dd>
           <dt>이 구간 길이</dt><dd>${p.length_m} m</dd>
           <dt title="가장 가까운 CCTV 까지의 거리. 25m 초과면 영상판정이 성립하지 않는다">가장 가까운 CCTV까지</dt><dd>${p.cctv_dist_m} m</dd></dl>
       ${(p.nfa_designated==="true"||p.nfa_designated===true)?`<div class="nfa">소방청 지정 기준 충족 · 연속 ${p.run_length_m} m</div>`:""}
       <div class="hint">${v.d}</div>
       ${flags.length?`<div class="flag">${flags.join(" · ")}</div>`:""}
       <div class="uid" title="현장 대조·버그 리포트용 키. 실행 간 유지된다">${p.seg_uid}</div>`;
    tip.style.display="block";
    tip.style.left = Math.min(e.point.x+14, innerWidth-210)+"px";
    tip.style.top  = (e.point.y+14)+"px";
  });
  S.map.on("mouseleave","seg-l", () => { tip.style.display="none"; });
}
