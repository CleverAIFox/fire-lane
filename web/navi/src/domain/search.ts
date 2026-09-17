/**
 * domain/search.ts — 목적지 검색. 순수 함수.
 *
 * ★ 2026-09-17 (DECISIONS §181). 색인이 `poi.geojson`(상가 2,077)에서 `dest.geojson` 으로
 *   바뀌었다 — 상가 + 주소/건물(내비게이션용DB) + 관공서/학교(민원행정기관), 지도 이동 범위 안.
 *   필드는 같고(name · cat · sub · addr) `alt`(지번) · `src`(원천) 가 더해졌다.
 *   서버 없이 통째로 메모리에 올려 찾는다.
 *
 * ★ 목적지를 색인 좌표로 쓰지 않는다. 건물은 출입구 좌표지만 그래도 차도 위가 아니다.
 *   호출부가 반드시 `snap` 을 거쳐 **도로 위 점**으로 바꾼다 — 내비는 차도만 다닌다.
 *
 * ★ 한글 초성 검색을 넣지 않았다. 수천 건 규모에서 부분일치로 충분하다.
 */
import type { LngLat } from "./geo";

export type PoiSrc = "civil" | "build" | "store";

export interface Poi {
  name: string;
  cat: string;
  sub: string;
  addr: string;
  /** 지번 — `동명동 18-12 · 동명동 18-11`. 없으면 빈 문자열 */
  alt: string;
  src: PoiSrc;
  point: LngLat;
}

export interface PoiHit extends Poi {
  /** 낮을수록 좋다 */
  score: number;
}

/** 같은 점수면 관공서 · 이름 있는 건물이 상가보다 앞선다 — 법원을 치면 법원 앞 김밥집이 먼저 뜨지 않게 */
const SRC_RANK: Record<PoiSrc, number> = { civil: 0, build: 1, store: 2 };

/** GeoJSON → 검색용 배열. **한 번만 호출한다.** */
export function preparePois(fc: GeoJSON.FeatureCollection): Poi[] {
  const out: Poi[] = [];
  for (const f of fc.features) {
    if (f.geometry?.type !== "Point") continue;
    const p = (f.properties ?? {}) as Record<string, string>;
    if (!p.name) continue;
    const src = (p.src === "civil" || p.src === "build") ? p.src : "store";
    out.push({
      name: p.name, cat: p.cat ?? "", sub: p.sub ?? "", addr: p.addr ?? "",
      alt: p.alt ?? "", src,
      point: f.geometry.coordinates as LngLat,
    });
  }
  return out;
}

/** 공백을 무시한다 — `필문대로230` 과 `필문대로 230` 이 같은 질의다 */
const norm = (s: string) => s.toLowerCase().replace(/\s+/g, "");

/**
 * 부분일치 검색.
 *
 * 점수는 낮을수록 좋다 —
 *   0  이름이 질의로 시작
 *   1  이름에 포함
 *   2  유형 · 세부에 포함
 *   3  도로명주소 · 지번에 포함
 *
 * ★ 2026-09-17. 종전에는 `limit * 8` 건을 모으면 끊었다. 색인 순서가 상가 먼저라
 *   넓은 질의(`동구`)에서 관공서가 후보에 들기도 전에 잘렸다. 수천 건은 전수로 돈다.
 */
export function searchPois(pois: Poi[], q: string, limit = 20): PoiHit[] {
  const s = norm(q.trim());
  if (s.length < 1) return [];
  const hits: PoiHit[] = [];
  for (const p of pois) {
    const n = norm(p.name);
    let score = -1;
    if (n.startsWith(s)) score = 0;
    else if (n.includes(s)) score = 1;
    else if (norm(`${p.cat}${p.sub}`).includes(s)) score = 2;
    else if (norm(p.addr).includes(s) || norm(p.alt).includes(s)) score = 3;
    if (score >= 0) hits.push({ ...p, score });
  }
  hits.sort((a, b) => a.score - b.score
    || SRC_RANK[a.src] - SRC_RANK[b.src]
    || a.name.length - b.name.length);
  return hits.slice(0, limit);
}
