/**
 * app/useFleet.ts — 차종 선택. 선택한 차의 제원이 곧 판정 기준이다.
 *
 * ── ★ 왜 데이터를 직접 읽나 ─────────────────────────────────────
 * 2026-09-06. `useNavigation` 이 `fleet.json` 을 적재하고, `useFleet` 이
 * 그것을 받아 `spec` 을 만들고, 그 `spec` 을 다시 `useNavigation` 으로
 * 되먹였다. **순환이다.** `setState` 로 되먹이면 렌더마다 상태가 바뀌어
 * "Too many re-renders" 로 죽는다.
 *
 * 그래서 이 훅이 `fleet.json` 과 `vehicle_spec.json` 을 **직접** 읽는다.
 * 그러면 의존이 한 방향이 된다 —
 *
 *     useFleet ──spec──▶ useNavigation
 *
 * 같은 파일을 두 번 fetch 하지만 브라우저가 캐시한다. **의존이 한
 * 방향인 것이 중복보다 중요하다.**
 *
 * ★ 차종을 바꾸면 **경로가 다시 계산돼야 한다.** 필요폭이 바뀌기
 *   때문이다 — 펌프차 3.0m 대 구급차 2.5m. 폭 2.7m 골목이 한쪽엔
 *   막히고 한쪽엔 뚫린다.
 *
 * ★ 이것이 CV 가 **이진 분류가 아니라 폭**을 반환해야 하는 이유다.
 *   "통과/불가" 로 받으면 어느 차 기준인지가 모델 안에 박히고, 차종을
 *   바꾸는 순간 무효가 된다(contracts/vision.py 가 그렇게 못박는다).
 *
 * ★ `spec` 은 `useMemo` 로 참조를 고정한다. 매 렌더마다 새 객체를 내면
 *   그것을 의존성으로 삼는 쪽에서 다시 무한 루프가 난다.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { loadFleet } from "../infra/dataSource";
import type { Fleet, FleetVehicle, VehicleSpec } from "../domain/types";

export function useFleet() {
  const [fleet, setFleet] = useState<Fleet | null>(null);
  const [base, setBase] = useState<VehicleSpec | null>(null);
  const [id, setId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    loadFleet()
      .then((r) => {
        if (!alive) return;
        setFleet(r.fleet);
        setBase(r.spec);
      })
      .catch(() => {
        // 차종 선택만 못 쓴다. 앱은 기준 차량으로 그대로 돈다.
      });
    return () => { alive = false; };
  }, []);

  const current: FleetVehicle | null = useMemo(() => {
    if (!fleet) return null;
    return fleet.vehicles.find((v) => v.id === (id ?? fleet.default))
      ?? fleet.vehicles[0] ?? null;
  }, [fleet, id]);

  /**
   * 선택한 차의 제원.
   *
   * ★ `wheelbase_verified` · `turn_radius_verified` 는 **기준 차량 것을
   *   그대로 물려받는다.** 차종별로 검증 상태가 다르지 않다 — 대장이
   *   전부 미검증이다. 대장에서 올리면 여기도 같이 올라간다.
   */
  const spec: VehicleSpec | null = useMemo(() => {
    if (!base) return null;
    if (!current) return base;
    return {
      ...base,
      kind: current.label,
      width_m: current.width_m,
      clearance_m: current.clearance_m,
      length_m: current.length_m ?? base.length_m,
    };
  }, [base, current]);

  const select = useCallback((v: string) => setId(v), []);
  return { fleet, vehicleId: current?.id ?? null, current, spec, select };
}
