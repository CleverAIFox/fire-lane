/**
 * infra/dataSource.ts — `web/data` 를 읽는다. 서버는 없다.
 *
 * ★ 사본을 만들지 않는다. 파이프라인이 `web/data` 를 갱신하면 앱이 즉시
 *   그것을 본다. 복사해두면 "지도는 새 판정, 내비는 옛 판정" 이 된다.
 *
 * ★ 판정 색을 여기서 정의하지 않는다. `publish_navi.py` 가
 *   `web/config.js` 에서 뽑아 `navi_graph.json.style` 로 싣는다.
 */
import type {
  Fleet, NaviGraph, RouteVehicle, VehicleSpec, View,
} from "../domain/types";

/** base 가 /<repo>/navi/ 이므로 ../data/ 가 곧 web/data 다. */
const DATA = new URL("../data/", document.baseURI).href;

async function j<T>(name: string): Promise<T> {
  const r = await fetch(DATA + name);
  if (!r.ok) throw new Error(`${name} 를 못 읽었다 (${r.status})`);
  return r.json() as Promise<T>;
}

async function optional<T>(name: string): Promise<T | null> {
  try {
    return await j<T>(name);
  } catch {
    return null;
  }
}

export interface Bundle {
  graph: NaviGraph;
  spec: VehicleSpec;
  view: View;
  poi: GeoJSON.FeatureCollection;
  routeVehicle: RouteVehicle;
}

export async function loadAll(): Promise<Bundle> {
  const [graph, spec, view, poi, routeVehicle] = await Promise.all([
    j<NaviGraph>("navi_graph.json"),
    j<VehicleSpec>("vehicle_spec.json"),
    j<View>("view.json"),
    j<GeoJSON.FeatureCollection>("poi.geojson"),
    j<RouteVehicle>("route_vehicle.json"),
  ]);

  // ★ style 이 없으면 죽는다. 기본색을 두면 config.js 를 아무도 안 고치고
  //   그 기본색이 화면에 남는다 — vehicle.py 가 기본 제원을 안 두는 것과
  //   같은 이유다.
  if (!graph.style) {
    throw new Error(
      "navi_graph.json 에 style 이 없다. 발행을 다시 해라:\n" +
      "  uv run python -m firelane.publish_navi");
  }
  return { graph, spec, view, poi, routeVehicle };
}

/**
 * 차종 선택이 쓰는 둘만 따로 읽는다.
 *
 * ★ `loadAll` 과 `vehicle_spec.json` 이 겹치는데 **일부러 그렇다.**
 *   겹침을 없애려고 `useNavigation` → `useFleet` → `useNavigation` 으로
 *   되먹였다가 무한 리렌더가 났다(2026-09-06). 의존이 한 방향인 것이
 *   중복보다 중요하고, 브라우저가 두 번째 fetch 를 캐시한다.
 *
 * ★ `fleet.json` 이 없어도 던지지 않는다. `publish_fleet` 를 안 돌린
 *   저장소에서도 개발할 수 있어야 한다 — 차종 선택 화면만 안 뜬다.
 */
export async function loadFleet(): Promise<{
  fleet: Fleet | null; spec: VehicleSpec;
}> {
  const [fleet, spec] = await Promise.all([
    optional<Fleet>("fleet.json"),
    j<VehicleSpec>("vehicle_spec.json"),
  ]);
  return { fleet, spec };
}
