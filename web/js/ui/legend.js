/* Fire-Lane · 범례
   ────────────────────────────────────────────────────────────
   ★ 색표와 건수를 데이터에서 직접 센다 — 패널에 손으로 적어두면
     데이터가 바뀔 때 조용히 어긋난다.
   ★ 지도와 범례가 다른 색이면 범례가 거짓말이 된다. vColor() 하나를 본다.
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";
import { $ } from "../dom.js";
import { VERDICT, vColor } from "../verdict.js";

export function buildPoiLegend(poi){
  {
    const host = $("#poi-legend");
    if(host){
      const n = {};
      poi.features.forEach(f=>{ const c=f.properties.cat; n[c]=(n[c]||0)+1; });
      const named = Object.keys(CONFIG.poi.color).filter(k=>k!=="other");
      const rest  = Object.entries(n).filter(([k])=>!named.includes(k))
                          .reduce((a,[,v])=>a+v, 0);
      host.innerHTML =
        named.map(k=>`<div class="mk"><i style="background:${CONFIG.poi.color[k]}"></i>${k}
                      <span>${n[k]||0}</span></div>`).join("") +
        `<div class="mk"><i style="background:${CONFIG.poi.color.other}"></i>${CONFIG.poi.otherLabel}
         <span>${rest}</span></div>`;
    }
  }
}

export function buildVerdictLegend(seg){
  const cnt = {};
  seg.features.forEach(f=>{ const v=f.properties.verdict; cnt[v]=(cnt[v]||0)+1; });
  $("#legend").innerHTML = Object.entries(VERDICT).map(([k,v])=>
    `<div class="lg" data-v="${k}" title="${v.d}">
       <i class="sw" style="background:rgb(${vColor(k)})"></i>
       <span class="nm">${v.nm}</span><span class="ct">${cnt[k]||0}</span></div>`).join("");
  /* #warn(도면 기반 1차 분류 단서)과 #crit-msg(판정 보류 폭 차이 문구)는
     패널에서 내렸다(2026-08-18). 채울 자리가 없어 계산도 함께 걷어냈다.
     ★ 되살리려면 index.html 에 자리를 만들고 이 블록을 복구할 것. git 이력에 있다. */

  document.querySelectorAll(".lg").forEach(el=>el.onclick=()=>{
    const k=el.dataset.v;
    S.off.has(k) ? S.off.delete(k) : S.off.add(k);
    el.classList.toggle("off", S.off.has(k));
    S.map.setFilter("seg-l", S.off.size
      ? ["!",["in",["get","verdict"],["literal",[...S.off]]]] : null);
  });
}
