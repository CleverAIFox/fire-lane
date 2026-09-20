/* Fire-Lane · 좌측 통계
   ────────────────────────────────────────────────────────────
   ★ 소화전은 동명동 안에 있는 것만 센다. 스코프 전체에는 11개가 있지만
     정작 동명동 안은 1개뿐이라는 게 이 프로젝트의 논거다.
     관할 588개 중 공개된 것이 31개(5%)이고 그중 동명동이 1개다.
   ──────────────────────────────────────────────────────────── */
import { S } from "../state.js";
import { $ } from "../dom.js";

export function renderStats({seg, bld, hyd, cctv, poi}){
  const VIEW = S.VIEW;
  /* ★ 2026-09-20 (PLAN §1 #62). 총수 하나만 찍으면 1,281 중 동명동이
     416 이라는 사실이 안 보인다. 세 층을 그대로 찍는다 — 문장을 늘리지
     않고 숫자만 늘린다. 기준은 지도 진하기(scopeTier)와 같다. */
  const tier = seg.features.reduce((a, f) => {
    const p = f.properties;
    a[p.in_emd ? 0 : (p.route_usage > 0 ? 1 : 2)]++;
    return a;
  }, [0, 0, 0]);
  $("#s-seg").textContent = tier.join(" · ");
  $("#s-seg").title = `대상지 ${tier[0]} · 회랑 ${tier[1]} · 참고 ${tier[2]}`
    + ` (합 ${seg.features.length})`;
  $("#s-bld").textContent = bld.features.length.toLocaleString();
  const inEmd = hyd.features.filter(f => {
    const [x, y] = f.geometry.coordinates;
    const [[a, b2], [c, d]] = VIEW.emdBounds;
    return x >= a && x <= c && y >= b2 && y <= d;
  }).length;
  $("#s-hyd").textContent = `${inEmd} / ${hyd.features.length}`;
  const cams = cctv.features.reduce((a,f)=>a+(f.properties.카메라대수||0),0);
  $("#s-cctv").textContent = `${cctv.features.length} / ${cams}`;
  $("#s-poi").textContent = poi.features.length.toLocaleString();
  const feas = seg.features.filter(f=>f.properties.cv_feasible).length;
  $("#s-cv").textContent = `${feas} / ${seg.features.length} (${(feas/seg.features.length*100).toFixed(0)}%)`;
  /* 폭 밴드(#band)는 화면에서 내렸다(2026-08-18). 갱신 코드도 함께 제거했다. */
}
