/* Fire-Lane · 차량 경로 도달성 조인
   ────────────────────────────────────────────────────────────
   route_vehicle.json(`seg_uid → {use, cost, passable, reachable}`)의 `reachable` 을
   구간 속성에 붙인다. 브라우저 전역을 안 쓰는 순수 함수라 테스트할 수 있다.

   ★ 2026-09-16. 도달 불가 구간(1,101 중 413)이 지도에 **없었다.** 데이터는
     발행돼 있었고 조인 키도 맞았다. 판정 색이 아니라 **오버레이**로 얹는다 —
     판정 4종(MASTER §10-2)은 그대로다(DECISIONS §166).
   ★ 조인이 빗나간 구간은 `reachable = null` 로 둔다. 0 으로 두면 "도달 불가" 로
     그려져 거짓 경고가 된다. 빗나간 수는 돌려줘서 부르는 쪽이 본다.
   ──────────────────────────────────────────────────────────── */

export const UNREACH_FILTER = ["==", ["get", "reachable"], 0];

export function joinReach(features, route) {
  let unreach = 0, missing = 0;
  for (const f of features) {
    const r = route ? route[f.properties.seg_uid] : undefined;
    if (!r || (r.reachable !== 0 && r.reachable !== 1)) {
      f.properties.reachable = null;
      missing++;
      continue;
    }
    f.properties.reachable = r.reachable;
    if (r.reachable === 0) unreach++;
  }
  return { unreach, missing, total: features.length };
}
