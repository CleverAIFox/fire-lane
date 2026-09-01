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

/* ── 통과 여유 줄 ────────────────────────────────────────────
   기여: @marscoolcat · 2026-09-01

   ★ 이 줄은 지도 색을 바꾸지 않는다. 색이 바뀌는 것은 이 숫자뿐이다.
     설계 원칙 6 — 판정은 파이프라인이 낸 verdict 가 정본이고 화면은
     재판정하지 않는다. 여기서 하는 일은 "네가 고른 차 기준으로 얼마나
     남는가"를 따로 답하는 것이지 판정을 다시 내리는 것이 아니다.

   ★ 왜 필요한가. 설계 원칙 4 — "판정 색만 주지 않는다. 폭 수치와 여유를
     함께 준다." 인터뷰(2026-08-24)에서 현장은 여유 8cm 에도 진입하고
     수치를 안 보고 내려서 판단한다고 했다. 색만 주면 화면을 안 믿는다.

   ★ 여유의 정의가 두 개다(인수인계 §2-3). 여기는 통과선 대비다.
       GIS 툴팁 종전 = 전폭 대비   = 유효폭 − 2.5
       여기          = 통과선 대비 = 유효폭 − (전폭 + 안전여유)
     같은 골목이 화면마다 다른 숫자로 보이므로 라벨에 "통과 여유"라고
     적고 기준 차량과 통과선을 바로 아래 줄에 함께 밝힌다.
     ★ 라벨을 그냥 "여유"로 줄이지 말 것. 그 순간 두 정의가 섞인다.

   ★ 단위는 m 로 통일한다. 종전 계획의 cm 표기(+70cm)와 섞이면 두 숫자가
     같은 축인지조차 안 읽힌다.

   ★ 3색의 기준. 판정 4색을 쓰지 않는다 — 이 줄은 판정이 아니다.
       여유 < 0        통과선에 못 미친다
       0 ≤ 여유 < 0.3  들어가지만 여유가 없다. 8cm 진입 사례가 여기다
       0.3 ≤ 여유      여유 있음
     0.3m 는 사이드미러 접고 서행하는 폭이 아니라 그냥 눈금이다.
     현장 근거가 생기면 바꿀 것.

   ★ 모르면 모른다고 쓴다. 폭이 없거나(회색 2건) 차량 제원이 없으면
     (조연차) 숫자를 만들지 않고 "—" 를 낸다. 0 으로 채우면 모르는 것이
     아는 것처럼 계산에 들어간다.
   ──────────────────────────────────────────────────────────── */
export function marginRow(widthM){
  const v = S.vehicle;
  if (!v || v.passLine == null) return "";      // 차량 제원 미확인
  const w = (widthM == null || widthM === "") ? null : Number(widthM);
  const base = `<dt title="선택한 기준 차량의 통과선(전폭+안전여유) 대비 남는 폭">통과 여유</dt>`;
  if (w == null || !isFinite(w))
    return `${base}<dd class="mgn none">—</dd>`;
  const m = w - v.passLine;
  const cls = m < 0 ? "bad" : m < 0.3 ? "tight" : "ok";
  const sign = m >= 0 ? "+" : "\u2212";
  return `${base}<dd class="mgn ${cls}">${sign}${Math.abs(m).toFixed(2)} m</dd>`;
}

/* 기준 차량 줄. 설계 원칙 5 — 기준을 안 밝힌 수치는 뜻을 잃는다. */
function basisRow(){
  const v = S.vehicle;
  if (!v) return "";
  const pl = v.passLine == null ? "제원 미확인" : `통과선 ${v.passLine.toFixed(2)} m`;
  const warn = v.match && v.match !== "확정" ? ` · 제원 ${v.match}` : "";
  return `<div class="basis-v">기준 ${v.label} · ${pl}${warn}</div>`;
}

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
       <dl><dt title="포장된 도로 노면만 잰 폭. 화면의 선 굵기가 이 값이다">도로 폭</dt><dd>${n(p.width_min_m)}</dd>
         ${marginRow(p.width_min_m)}</dl>
       ${basisRow()}
       ${isNfa?`<div class="nfa">소방청 지정 기준 충족 · 연속 ${p.run_length_m} m</div>`:""}`;
    tip.style.display="block";
    tip.style.left = Math.min(e.point.x+14, innerWidth-210)+"px";
    tip.style.top  = (e.point.y+14)+"px";
  });
  S.map.on("mouseleave","seg-l", () => { tip.style.display="none"; });
}
