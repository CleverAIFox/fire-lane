/* Fire-Lane · 구간 툴팁
   ════════════════════════════════════════════════════════════
   사용자는 119 상황실 관제사다. 신고를 받고 지도를 보는 몇 초 안에
   무전으로 뭐라고 부를지와 들어갈 수 있는지를 알아야 한다.
   그 둘에 기여하지 않는 값은 띄우지 않는다.

   ★ 2026-08-22. 8줄에서 3줄로 줄였다. 뺀 것과 이유:

     건물 사이 폭    판정 근거이지 관제사의 판단 재료가 아니다.
                    "7.65m" 를 보고 관제사가 할 수 있는 일이 없다.
     이 구간 길이    같은 이유.
     가장 가까운 CCTV  판정 사유에 이미 "CCTV 25m 밖" 이 들어간다. 중복.
     판정 설명문      unknown_reason 을 넷으로 쪼갠 뒤로 사유 줄이 더
                    구체적이다. 두 줄이 같은 말을 한다.
     측정 플래그      중점 폴백 · 인접 상속. 값의 신뢰도 경고인데
                    관제사가 그것으로 취할 조치가 없다.
     seg_uid        ★ 현장 대조 · 향후 DB 기본키용이다. 데이터에는
                    그대로 두고 화면에만 안 띄운다. 관제사에게는
                    의미 없는 문자열이고, 화면에서 제일 눈에 띄는
                    자리를 차지하고 있었다.

   ★ 남긴 것 넷.
     seg_label      "동명로25번길 9-14". 도로명주소법 기초번호이고
                    119 가 무전에서 쓰는 언어와 같다. 종전에는
                    "동명로25번길 7구간" 이었는데, seg_no 는 정렬
                    순번이라 노딩이 바뀌면 흔들린다. 기초번호는 기하
                    유도라 안정적이다(§5-1).
     판정            색과 같은 정보지만 색맹 대비 · 확인용.
     사유            회색일 때만. 왜 판정이 안 되는지가 곧 다음 행동이다.
     도로 폭         화면의 선 굵기가 이 값이다. 유일한 수치.
     소방청 지정      외부 기관이 지정한 사실. 값이 아니라 근거라 남긴다.
   ════════════════════════════════════════════════════════════ */
import { S } from "../state.js";
import { $ } from "../dom.js";
import { VERDICT, REASON, vColor } from "../verdict.js";

export function bindTooltip(){
  const tip = $("#tip");
  S.map.on("mousemove","seg-l", e => {
    const p = e.features[0].properties;
    const v = VERDICT[p.verdict] || VERDICT.unknown;
    const n = x => (x==null||x==="") ? "—" : Number(x).toFixed(2)+" m";
    /* seg_label 이 없으면 도로명으로 떨어진다. 기초번호가 없는 구간은
       10,334개 중 0건이지만, 산출물이 낡았을 때를 위해 남긴다. */
    const name = p.seg_label || p.road_name || "도로명 없음";
    const isNfa = p.nfa_designated==="true" || p.nfa_designated===true;
    tip.innerHTML =
      `<div class="id">${name}</div>
       <div class="vd" style="color:rgb(${vColor(p.verdict in VERDICT ? p.verdict : "unknown")})">${v.nm}</div>
       ${p.unknown_reason?`<div class="rsn">${REASON[p.unknown_reason]||""}</div>`:""}
       <dl><dt title="포장된 도로 노면만 잰 폭. 화면의 선 굵기가 이 값이다">도로 폭</dt><dd>${n(p.width_min_m)}</dd></dl>
       ${isNfa?`<div class="nfa">소방청 지정 기준 충족 · 연속 ${p.run_length_m} m</div>`:""}`;
    tip.style.display="block";
    tip.style.left = Math.min(e.point.x+14, innerWidth-210)+"px";
    tip.style.top  = (e.point.y+14)+"px";
  });
  S.map.on("mouseleave","seg-l", () => { tip.style.display="none"; });
}
