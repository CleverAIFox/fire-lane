/* Fire-Lane · 기준 차량 선택 (좌측 패널)
   ════════════════════════════════════════════════════════════
   기여: @marscoolcat

   화면설계서 FRLN_DISP_02 의 관제 화면판이다. 출동 화면이 아직 없으므로
   기준 차량만 먼저 고를 수 있게 한다.

   ★ 두 갈래를 합쳐서 보여준다.
       무엇이 있는가   CONFIG.fleet — 동부소방서 보유 대장(동명동 관할)
       얼마나 큰가     web/assets/vehicles/profiles.json — 제원 정본
     대수는 대장이, 치수는 제원표가 정본이다. 한쪽에 둘을 같이 적으면
     실측으로 제원이 바뀔 때 대수까지 흔들린다.

   ★ 이 모듈은 지도를 다시 칠하지 않는다.
     설계 원칙 6 — "차종을 바꿔도 지도 색은 바뀌지 않는다. 색은 데이터의
     verdict 문자열이 정한다. 화면이 재판정하면 스키마 위반."
     그래서 여기에는 restyleSegments() 호출이 없다. 없는 게 맞다.
     실수로 넣지 말 것 — 넣는 순간 3.0m 골목이 구급차를 고르면 초록이 되고,
     그건 파이프라인이 낸 판정과 다른 색이다.

   ★ 그러면 선택은 무엇을 바꾸나. 통과선과 여유 표기다.
       통과선 = 차량 전폭 + CONFIG.vehicleClearance
       여유   = 유효폭 − 통과선
     지금은 S.vehicle 에 실어 두기만 한다. 툴팁의 여유 줄(marginRow)이
     들어오면 그 값을 읽는다.

   ★ 설계 원칙 5 — "기준 차량을 항상 밝힌다. 기준을 안 밝힌 수치는 뜻을
     잃는다." 그래서 선택 결과를 접었다 펴는 곳에 숨기지 않고 패널에
     상시 노출한다.

   ★ match 를 화면에 그대로 띄운다. 제원표 항목과 보유 차종이 다른 축으로
     분류돼 있는 경우가 있어서다(굴절형 사다리차). 회전반경은 7.3 과 11.9
     사이가 세 배 차이 나는 자리라, 추정을 확정처럼 보이게 하면 그게 곧
     사고다. 인터뷰(2026-08-24)에서 "물탱크차는 커서 못 들어갈 때가 있다"는
     말이 나왔는데 실제 원인도 폭이 아니라 회전반경이었다.

   ★ 제원표를 못 받아도 화면은 뜬다. fetch 가 실패하면 대수와 배치만
     보여주고 치수 자리에 "제원 미확인"을 넣는다. 지도가 통째로 안 뜨는
     것보다 낫고, 무엇이 없는지가 화면에 남는다.

   ★ S.vehicle 을 state.js 에 선언하지 않고 여기서 얹는다.
     state.js 는 GIS 쪽 파일 계통이라 UI 사정으로 건드리지 않는다.
     JS 객체는 확장 가능하므로 동작에 차이가 없다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "../config-access.js";
import { S } from "../state.js";

/* profiles.json 은 mm 단위다(파일 머리의 "units":"mm"). 화면은 m 로 쓴다. */
const mm2m = v => (v == null ? null : v / 1000);

/* 등급 색. 판정 4색과 겹치지 않게 고른다 —
   차량 등급은 구간 판정이 아니므로 같은 색을 쓰면 오독된다. */
const GRADE_CLASS = { "여유":"g-ok", "주의":"g-warn", "미판정":"g-none" };
const MATCH_CLASS = { "확정":"m-fix", "추정":"m-guess", "없음":"m-none" };

let PROFILES = null;   // id → profile. fetch 실패 시 null 로 남는다

/* #veh 컨테이너. 안쪽 요소는 전부 여기서 찾는다.
   ★ document.getElementById 로 찾지 않는다. 안쪽 요소(select · 요약 카드)는
     이 모듈이 실행 중에 만드는 것이라 index.html 에 없다.
     tests/test_contract.py::test_web_dom_refs_exist 가 "js 가 참조하는 id 는
     index.html 에 전부 있어야 한다"를 검사하므로 전역 id 조회를 쓰면 걸린다.
     검사를 피하려는 우회가 아니라 원래 이쪽이 맞다 — 지역 요소를 문서 전체에서
     찾을 이유가 없고, id 를 안 쓰면 이름 충돌도 안 난다.
   ★ index.html 에 실제로 있는 id 는 "veh" 하나뿐이다. */
let HOST = null;

export const passLine = width =>
  width == null ? null : width + (CONFIG.vehicleClearance ?? 0.5);

function profileOf(entry){
  if (!PROFILES || !entry.profile) return null;
  return PROFILES[entry.profile] || null;
}

/* 회전반경. entry.turnUnknown 이면 제원표 값이 있어도 안 가져온다.
   ★ 사다리차가 그 경우다. 광주 규격서(2025-06)에 회전반경 규정이 없고,
     차대가 6x4 3축인데 profiles.json 의 대표값은 2축 기준으로 보인다.
     실제보다 작은 값을 띄우면 오차가 안전과 반대 방향으로 난다.
     빈칸이 틀린 숫자보다 낫다. */
export const turnOf = entry => {
  if (entry.turnUnknown) return null;
  const pr = profileOf(entry);
  return pr ? mm2m(pr.turningRadius) : null;
};

function rowsFor(entry){
  const pr = profileOf(entry);
  const w  = pr ? mm2m(pr.width) : null;
  const t  = turnOf(entry);
  const pl = passLine(w);
  const dash = "—";
  /* 아우트리거는 전폭과 다른 축이라 별도 줄로 낸다. 같은 dl 안에 있지만
     "들어갈 수 있나"가 아니라 "세울 수 있나"를 묻는 값이다. */
  const out = entry.outrigger == null ? "" :
    `<dt title="붐을 세우려면 좌우로 받침대를 펴야 한다. 그때 필요한 폭이며 전폭과 다른 값이다">아우트리거</dt>
     <dd>${entry.outrigger.toFixed(1)} m 이상</dd>`;
  return `
    <dl>
      <dt>보유</dt><dd>${entry.count}대 · ${entry.at}</dd>
      <dt>전폭</dt><dd>${w == null ? dash : w.toFixed(3) + " m"}</dd>
      <dt>통과선</dt><dd>${pl == null ? dash : pl.toFixed(2) + " m"}</dd>
      ${out}
      <dt>최소회전반경</dt><dd>${t == null ? dash : t.toFixed(2) + " m"}
        <i class="veh-grade ${GRADE_CLASS[entry.grade] || "g-none"}">${entry.grade}</i></dd>
    </dl>`;
}

/* 묶음 순서대로 [묶음명, 항목들] 을 낸다.
   ★ fleetGroups 에 없는 group 은 버리지 않고 맨 뒤 "그 외"로 모은다.
     목록에 차를 추가하고 group 을 안 적으면 조용히 사라지는 것이 제일 나쁘다. */
function grouped(list){
  const order = CONFIG.fleetGroups || [];
  const out = order
    .map(g => [g, list.filter(e => e.group === g)])
    .filter(([, xs]) => xs.length);
  const rest = list.filter(e => !order.includes(e.group));
  if (rest.length) out.push(["그 외", rest]);
  return out;
}

export function setVehicle(id){
  const list = CONFIG.fleet || [];
  const e = list.find(x => x.id === id) || list[0];
  if (!e) return;

  const pr = profileOf(e);
  /* 툴팁의 여유 줄이 읽을 값. 제원이 없으면 width 를 null 로 둔다 —
     0 이나 2.5 로 채우면 모르는 것이 아는 것처럼 계산에 들어간다. */
  S.vehicle = {
    id: e.id, label: e.label,
    width: pr ? mm2m(pr.width) : null,
    turn : turnOf(e),
    outrigger: e.outrigger ?? null,
    passLine: passLine(pr ? mm2m(pr.width) : null),
    match: e.match, grade: e.grade,
  };

  const sel = HOST && HOST.querySelector("select");
  if (sel && sel.value !== e.id) sel.value = e.id;

  const sum = HOST && HOST.querySelector(".veh-sum");
  if (!sum) return;
  const warn = !PROFILES
    ? `<div class="veh-warn">제원 미확인 — profiles.json 을 못 읽었다</div>`
    : e.match === "확정" ? ""
    : `<div class="veh-warn"><b>제원 ${e.match}</b>${e.note ? " · " + e.note : ""}</div>`;
  sum.innerHTML =
    `<div class="veh-name">${e.label}
       <i class="veh-match ${MATCH_CLASS[e.match] || "m-none"}">${e.match}</i></div>
     ${rowsFor(e)}${warn}`;
}

export async function initVehicleSelect(){
  const host = document.getElementById("veh");
  if (!host) return;
  HOST = host;
  const list = CONFIG.fleet || [];
  if (!list.length){ host.style.display = "none"; return; }

  /* ★ 버튼 격자에서 드롭다운으로 바꿨다(2026-09-01). 패널 폭이 288px 인데
     차종 이름이 길어("굴절형 사다리차 27m") 버튼이 2~3줄로 접히면서, 여덟 개가
     판정 범례보다 넓은 자리를 차지했다. 차량 선택은 한 번 고르고 마는 값이라
     상시 펼쳐 둘 이유가 없다 — 고른 결과만 아래 요약에 남으면 된다.
   ★ 네이티브 <select> 를 쓴다. optgroup 을 직접 만든 목록으로 흉내 내면
     키보드 이동·모바일 휠 선택을 전부 다시 짜야 한다. */
  host.innerHTML =
    `<div class="veh-pick">
       <select aria-label="기준 차량 선택">
         ${grouped(list).map(([g, xs]) =>
           `<optgroup label="${g}">${xs.map(e =>
             `<option value="${e.id}">${e.label} · ${e.count}대</option>`
           ).join("")}</optgroup>`).join("")}
       </select>
     </div>
     <div class="veh-sum"></div>
     <div class="veh-note">${CONFIG.turnNote || ""}</div>
     <div class="veh-src">${CONFIG.fleetSource || ""}</div>`;

  host.querySelector("select")
      ?.addEventListener("change", ev => setVehicle(ev.target.value));

  /* 먼저 대수·배치로 한 번 그린다. 제원표가 늦거나 실패해도 화면은 선다. */
  setVehicle(CONFIG.fleetDefault || list[0].id);

  try {
    const r = await fetch(CONFIG.vehicleProfiles || "./assets/vehicles/profiles.json");
    if (!r.ok) throw new Error(String(r.status));
    const j = await r.json();
    PROFILES = Object.fromEntries((j.profiles || []).map(p => [p.id, p]));
    /* 제원이 붙었으니 현재 선택을 다시 그린다. */
    setVehicle(S.vehicle ? S.vehicle.id : (CONFIG.fleetDefault || list[0].id));
  } catch (err) {
    console.warn("차량 제원(profiles.json) 로드 실패 — 대수만 표시한다", err);
  }
}
