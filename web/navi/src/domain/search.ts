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
 * ★ 2026-09-23 (DECISIONS §224-5). 한글 초성 검색을 넣었다. 종전 머리말은
 *   「수천 건 규모에서 부분일치로 충분하다」 였는데, 그것은 **찾는 쪽 사정**이지
 *   치는 쪽 사정이 아니다. 관제요원은 신고자 말을 받아치면서 지도를 본다 —
 *   `ㄷㅁㄷㅎㅈㅂㅈㅅ` 가 `동명동행정복지센터` 로 가야 한다.
 *   **질의가 전부 초성일 때만** 초성으로 찾는다. 섞이면 지금처럼 부분일치다 —
 *   안 그러면 `ㄱ` 한 자가 1,836건을 다 물어온다.
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
  /** 이름의 초성 — `동명동행정복지센터` → `ㄷㅁㄷㅎㅈㅂㅈㅅㅌ`. 색인 시 한 번만 만든다 */
  cho: string;
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
      cho: choOf(p.name),
    });
  }
  return out;
}

/** 공백을 무시한다 — `필문대로230` 과 `필문대로 230` 이 같은 질의다 */
const norm = (s: string) => s.toLowerCase().replace(/\s+/g, "");

/** 현대 한글 음절의 초성 19자. 유니코드 순서 그대로여야 한다 — 순서가 곧 색인이다. */
const CHO = "\u3131\u3132\u3134\u3137\u3138\u3139\u3141\u3142\u3143\u3145\u3146\u3147\u3148\u3149\u314a\u314b\u314c\u314d\u314e";

/**
 * 문자열의 초성. 한글 음절만 바꾸고 나머지(숫자 · 영문 · 기호)는 그대로 둔다 —
 * `GS25` 가 `GS25` 로 남아야 `ㅍㅇㅁㄹGS25` 같은 질의도 걸린다.
 */
export function choOf(s: string): string {
  let out = "";
  for (const ch of s) {
    const c = ch.codePointAt(0) ?? 0;
    out += (c >= 0xac00 && c <= 0xd7a3) ? CHO[Math.floor((c - 0xac00) / 588)] : ch;
  }
  return out;
}

/**
 * 질의가 **전부** 초성인가. 한 자라도 완성 음절이 섞이면 false.
 *
 * ★ 이 문이 좁아야 한다. 넓히면 `ㄱ` 한 자가 색인 전체를 물어오고, 그러면
 *   부분일치 결과가 초성 결과에 묻힌다 — 잘 되던 것이 나빠진다.
 */
export function isChoQuery(s: string): boolean {
  if (!s) return false;
  for (const ch of s) if (!CHO.includes(ch)) return false;
  return true;
}

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
  // ★ 질의가 전부 초성이면 **초성으로만** 찾는다. 섞어 찾지 않는다 —
  //   `ㄱ` 이 이름 · 유형 · 주소를 동시에 훑으면 결과가 무의미해진다.
  const cho = isChoQuery(s);
  const hits: PoiHit[] = [];
  for (const p of pois) {
    const n = norm(p.name);
    let score = -1;
    if (cho) {
      const c = norm(p.cho);
      if (c.startsWith(s)) score = 0;
      else if (c.includes(s)) score = 1;
    } else if (n.startsWith(s)) score = 0;
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
