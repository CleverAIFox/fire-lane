/**
 * domain/search.ts — 목적지 검색. 순수 함수.
 *
 * `poi.geojson` 2,077건은 `name`·`cat`·`sub`·`addr` 이 **결손 0** 이다.
 * 서버 없이 통째로 메모리에 올려 찾는다 — 524KB 다.
 *
 * ★ 목적지를 POI 좌표로 쓰지 않는다. 상가→도로 거리가 중앙 15.6m ·
 *   p90 70.9m 라 그대로 쓰면 엉뚱한 골목에 붙는다. 호출부가 반드시
 *   `snap` 을 거쳐 **도로 위 점**으로 바꾼다 — 내비는 차도만 다닌다.
 *
 * ★ 한글 초성 검색을 넣지 않았다. 2,077건 규모에서 부분일치로 충분하고,
 *   초성 분해는 라이브러리를 하나 더 싣는다. 필요해지면 그때 넣는다.
 */
import type { LngLat } from "./geo";

export interface Poi {
  name: string;
  cat: string;
  sub: string;
  addr: string;
  point: LngLat;
}

export interface PoiHit extends Poi {
  /** 낮을수록 좋다 */
  score: number;
}

/** GeoJSON → 검색용 배열. **한 번만 호출한다.** */
export function preparePois(fc: GeoJSON.FeatureCollection): Poi[] {
  const out: Poi[] = [];
  for (const f of fc.features) {
    if (f.geometry?.type !== "Point") continue;
    const p = (f.properties ?? {}) as Record<string, string>;
    if (!p.name) continue;
    out.push({
      name: p.name, cat: p.cat ?? "", sub: p.sub ?? "", addr: p.addr ?? "",
      point: f.geometry.coordinates as LngLat,
    });
  }
  return out;
}

/**
 * 부분일치 검색.
 *
 * 점수는 낮을수록 좋다 —
 *   0  이름이 질의로 시작
 *   1  이름에 포함
 *   2  업종에 포함
 *   3  주소에 포함
 */
export function searchPois(pois: Poi[], q: string, limit = 20): PoiHit[] {
  const s = q.trim();
  if (s.length < 1) return [];
  const lower = s.toLowerCase();
  const hits: PoiHit[] = [];
  for (const p of pois) {
    const n = p.name.toLowerCase();
    let score = -1;
    if (n.startsWith(lower)) score = 0;
    else if (n.includes(lower)) score = 1;
    else if (`${p.cat}${p.sub}`.toLowerCase().includes(lower)) score = 2;
    else if (p.addr.toLowerCase().includes(lower)) score = 3;
    if (score >= 0) hits.push({ ...p, score });
    if (hits.length > limit * 8) break;   // 너무 넓은 질의를 잘라낸다
  }
  hits.sort((a, b) => a.score - b.score || a.name.length - b.name.length);
  return hits.slice(0, limit);
}
