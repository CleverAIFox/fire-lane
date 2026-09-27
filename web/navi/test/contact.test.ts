/**
 * test/contact.test.ts — 접지 그림자가 **건물과 한 몸으로** 움직이는가.  (§261)
 *
 * ★ 2026-09-27. 사용자 보고 「도로랑 건물이 서로 다른 지면에 올라간 것처럼 뜬다」.
 *   원인은 높이가 아니었다 — 건물 base 0, 도로면 z=0 으로 **같은 평면**이다.
 *   빠진 것은 접지 음영이고, 그것을 한 겹 깔아 고쳤다.
 *
 * ★ 여기서 재는 것은 **어긋남**이다. 이 레이어는 건물 압출과 붙어 다녀야 하고,
 *   떨어지는 순간 화면이 더 나빠진다 —
 *     ① 압출 **아래**가 아니면 그림자가 건물을 덮는다
 *     ② 줌 문턱이 다르면 한쪽만 나타나 땅에 얼룩이 뜬다
 *     ③ 관제가 건물을 끌 때 같이 안 끄면 **그림자만 남는다**
 *     ④ 그림자가 배경보다 밝으면 「닿았다」가 아니라 후광이 된다
 *
 * ★ 지형(`setTerrain`)은 이 문제의 답이 아니다. 공개DEM 이 90m 격자라 스코프
 *   0.43km² 전체가 12×12 픽셀이다 — 그 사실은 `terrain.py` 머리말이 든다.
 *
 * 밖  실제로 「붙어 보이는가」는 눈이 든다. 스크립트는 WebGL 을 못 본다.
 *     식이 유효한지는 `style.test.ts` 의 검증기 소관이라 여기서 안 본다.
 */
import { test, ok } from "./harness";
import { FL } from "./harness";
import { baseLayers } from "../src/components/layers";
import { MAP } from "../src/ui/tokens";

const SRC: Record<string, string> = import.meta.glob(
  "../src/components/*.tsx", { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

const src = (name: string) =>
  Object.entries(SRC).find(([k]) => k.endsWith(`/${name}`))?.[1] ?? "";

/** `#rrggbb` → 상대 휘도(WCAG). 어느 쪽이 어두운지 기계로 가른다. */
function lum(hex: string): number {
  const v = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
}

test("접지 그림자 — 압출 바로 밑 · 같은 줌 문턱", () => {
  const ids = baseLayers(FL.graph.style ?? {}).map((l) => l.id);
  const s = ids.indexOf("bldg-contact");
  const b = ids.indexOf("bldg");
  ok(s >= 0, "`bldg-contact` 레이어가 없다 — 접지 음영이 통째로 빠졌다");
  ok(b >= 0, "`bldg` 레이어가 없다 — 이 시험의 전제가 깨졌다");
  ok(s === b - 1, `그림자가 압출 바로 밑이 아니다 (그림자 ${s} · 압출 ${b}) — 건물을 덮는다`);

  const layers = baseLayers(FL.graph.style ?? {});
  const zs = layers[s] as { minzoom?: number };
  const zb = layers[b] as { minzoom?: number };
  ok(zs.minzoom === zb.minzoom,
     `줌 문턱이 다르다 (그림자 ${zs.minzoom} · 압출 ${zb.minzoom}) — 한쪽만 떠서 땅에 얼룩이 진다`);
});

test("접지 그림자 — 배경보다 어둡다 (후광이 아니다)", () => {
  const bg = `#${MAP.bg.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
  ok(lum(MAP.contact) < lum(bg),
     `밝은 지도의 그림자(${MAP.contact})가 배경(${bg})보다 어둡지 않다 — 후광이 된다`);

  // ★ 관제(다크)는 제 토큰을 따로 든다. 그쪽도 같은 규칙이어야 한다.
  const ops = src("OpsMap.tsx");
  const dark = /contact:\s*"(#[0-9a-fA-F]{6})"/.exec(ops)?.[1];
  const dbg = /bg:\s*"(#[0-9a-fA-F]{6})"/.exec(ops)?.[1];
  ok(dark && dbg, "관제 다크 토큰에서 contact · bg 를 못 읽었다");
  ok(lum(dark!) < lum(dbg!),
     `관제 그림자(${dark})가 배경(${dbg})보다 어둡지 않다`);
});

test("접지 그림자 — 건물을 끄면 같이 꺼진다 (그림자만 남지 않는다)", () => {
  const ops = src("OpsMap.tsx");
  const cond = (id: string) =>
    new RegExp(`vis\\("${id}",\\s*([^)]+)\\)`).exec(ops)?.[1]?.trim();
  const a = cond("bldg");
  const b = cond("bldg-contact");
  ok(a, "관제가 `bldg` 를 `vis(...)` 로 안 켠다 — 이 시험의 전제가 깨졌다");
  ok(b, "관제가 `bldg-contact` 를 안 끈다 — 건물을 끄면 **그림자만 남는다**");
  ok(a === b, `켜는 조건이 다르다\n    bldg          ${a}\n    bldg-contact  ${b}`);
});

test("접지 그림자 — 1인칭에서 건물이 비치면 같이 비친다", () => {
  const navi = src("NaviMap.tsx");
  ok(/setPaintProperty\("bldg-contact",\s*"fill-opacity"/.test(navi),
     "주행 중 건물만 반투명해지고 그림자는 그대로다 — 건물 밑에 검은 판이 남는다");
});
