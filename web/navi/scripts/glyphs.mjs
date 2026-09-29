/**
 * glyphs.mjs — 지도 글자를 **저장소 안에서** 만든다.  (DECISIONS §312)
 *
 *     npm run glyphs            web/fonts/<스택>/<범위>.pbf 를 다시 뽑는다
 *     npm run glyphs -- --check 뽑은 것이 지금 트리와 같은가 (관문용)
 *
 * ── 왜 생겼나 ───────────────────────────────────────────────────
 * PLAN §13 W13-4. 내비가 글자를 `demotiles.maplibre.org` 에서 받아 왔다.
 * **지하 주차장과 산간에서 도로 이름이 사라진다** — 출동 중에 가장 필요한 순간에
 * 가장 먼저 사라지는 것이 남의 서버에 있었다.
 *
 * ★ 한글은 이미 로컬이다(`localIdeographFontFamily`). 남의 서버가 필요했던 것은
 *   **숫자와 로마자**뿐이다 — 「필문대로205번길」의 `205` 석 자 때문에 외부 의존이
 *   하나 걸려 있었다. 그래서 뽑는 범위가 좁다.
 *
 * ★ 글꼴은 `fonts-src/` 에 **같이 둔다.** npm 에서 받으면 그날의 판이 달라질 수
 *   있고, 받을 수 없는 기계에서는 다시 못 뽑는다. SIL OFL 1.1 이라 재배포가
 *   허용된다(`fonts-src/LICENSE-Liberation.txt`).
 *
 * ★ 스택 이름을 실물에 맞춘다. 종전에는 `Open Sans Regular` 였는데 그것은
 *   demotiles 의 이름이었다 — 우리가 뽑는 글자는 Liberation Sans 다. 이름과 실물이
 *   다르면 다음 사람이 없는 글꼴을 찾는다.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fontnik from "fontnik";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const NAVI = path.resolve(HERE, "..");
const SRC = path.join(NAVI, "fonts-src", "LiberationSans-Regular.ttf");
const OUT = path.resolve(NAVI, "..", "fonts", "Liberation Sans Regular");

/**
 * **기기가 스스로 그리는 구간.** MapLibre 의 `localIdeographFontFamily` 가 맡는다.
 * 여기는 글자 파일을 안 만든다 — 만들면 한글 2,700자가 통째로 들어와 무게만 는다.
 */
const LOCAL = [
  [0x1100, 0x11FF],   // 한글 자모
  [0x3000, 0x303F],   // CJK 구두점
  [0x3040, 0x30FF],   // 히라가나 · 가타카나
  [0x3400, 0x4DBF],   // CJK 확장 A
  [0x4E00, 0x9FFF],   // CJK 통합
  [0xAC00, 0xD7AF],   // 한글 음절
  [0xFF00, 0xFFEF],   // 반각 · 전각
];

/** 글자가 실린 칸. 이름이 아니라 **실물**을 본다. */
const TEXT_KEY = /name|명$|road_name|BULD_NM|seg_label/i;

/**
 * **뽑을 범위를 데이터에서 잰다.** 손으로 적지 않는다.
 *
 * ★ 2026-09-29 실측. 손으로 적었으면 `256-511`(라틴 확장 A)을 넣었을 것이다 —
 *   124KB 인데 실제 데이터에 **0자**다. 반대로 `8448-8703`(ⅠⅡ) · `9728-9983`(★) ·
 *   `63744-63999`(茶) 셋은 한 두 자씩 실재하는데 짐작으로는 절대 안 나온다.
 *   그리고 데이터가 바뀌어 새 글자가 들어오면 `--check` 가 운다 — 글자가 조용히
 *   안 그려지는 것은 화면에서 제일 알아채기 어려운 결함이다.
 */
function neededRanges(dataDir) {
  const seen = new Set();
  const walk = (o, inText) => {
    if (typeof o === "string") {
      if (inText) for (const ch of o) seen.add(ch.codePointAt(0));
    } else if (Array.isArray(o)) {
      for (const v of o) walk(v, inText);
    } else if (o && typeof o === "object") {
      for (const [k, v] of Object.entries(o)) walk(v, inText || TEXT_KEY.test(k));
    }
  };
  for (const f of fs.readdirSync(dataDir)) {
    if (!/\.(geo)?json$/.test(f)) continue;
    try { walk(JSON.parse(fs.readFileSync(path.join(dataDir, f), "utf8")), false); }
    catch { /* 산출물이 아직 없는 기계 — 아래에서 0범위로 운다 */ }
  }
  const local = (c) => LOCAL.some(([a, b]) => c >= a && c <= b);
  const bases = new Set();
  for (const c of seen) if (!local(c)) bases.add(Math.floor(c / 256) * 256);
  return [...bases].sort((a, b) => a - b).map((a) => [a, a + 255]);
}

const RANGES = neededRanges(path.resolve(NAVI, "..", "data"));
if (!RANGES.length) {
  console.error("✗ 뽑을 범위가 0 이다 — web/data 가 비었거나 읽는 칸이 틀렸다");
  process.exit(1);
}

const check = process.argv.includes("--check");
const font = fs.readFileSync(SRC);

const made = new Map();
for (const [a, b] of RANGES) {
  const buf = await new Promise((res, rej) =>
    fontnik.range({ font, start: a, end: b }, (e, d) => (e ? rej(e) : res(d))));
  made.set(`${a}-${b}.pbf`, buf);
}

if (check) {
  let bad = 0;
  for (const [name, buf] of made) {
    const q = path.join(OUT, name);
    if (!fs.existsSync(q) || !fs.readFileSync(q).equals(buf)) {
      console.error(`  ✗ ${name} 이 없거나 다르다`);
      bad++;
    }
  }
  const extra = fs.existsSync(OUT)
    ? fs.readdirSync(OUT).filter((f) => f.endsWith(".pbf") && !made.has(f)) : [];
  for (const f of extra) { console.error(`  ✗ ${f} 는 선언에 없는 범위다`); bad++; }
  if (bad) {
    console.error("\n✗ 글자 파일이 선언과 다르다 —  npm run glyphs");
    process.exit(1);
  }
  console.log(`✓ 글자 ${made.size}범위가 선언과 같다 · ${OUT.replace(/.*\/web\//, "web/")}`);
} else {
  fs.mkdirSync(OUT, { recursive: true });
  let total = 0;
  for (const [name, buf] of made) {
    fs.writeFileSync(path.join(OUT, name), buf);
    total += buf.length;
    console.log(`  ${name.padEnd(14)} ${String(buf.length).padStart(7)} 바이트`);
  }
  console.log(`✓ ${made.size}범위 · ${(total / 1024).toFixed(1)}KB → web/fonts/`);
}
