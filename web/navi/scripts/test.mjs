/**
 * scripts/test.mjs — 내비 단위 시험 러너.  `npm run test`
 *
 * ★ 2026-09-22 (DECISIONS §213-3). 위치 추정 · 턴바이턴은 화면으로 검수가 안 된다.
 *   시험 틀(vitest 등)을 들이지 않고 **이미 있는 esbuild** 로 묶어 node 로 돈다 —
 *   의존성 하나를 늘리면 그만큼 dependabot PR 과 깨질 자리가 는다(§212-3).
 *
 *   test/*.test.ts  →  esbuild 로 한 파일씩 묶기  →  node 로 import  →  test() 수집
 *
 * ★ 시험은 `web/data` 의 **실제 발행물**(navi_graph.json)을 먹는다. 합성 도로만으로
 *   맞추면 실제 교차로 · 되돌아 나오는 경로에서 틀려도 모른다. 파일은 러너가 읽어
 *   `globalThis.__FL__` 로 넘긴다 — 시험 코드가 node 타입(fs)을 몰라도 되게.
 */
import { build } from "esbuild";
import { readFileSync, readdirSync, mkdtempSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const navi = join(here, "..");
const data = join(navi, "..", "data");

const tests = [];
globalThis.__FL__ = {
  graph: JSON.parse(readFileSync(join(data, "navi_graph.json"), "utf8")),
  spec: JSON.parse(readFileSync(join(data, "vehicle_spec.json"), "utf8")),
  test: (name, fn) => tests.push({ name, fn }),
};

const files = readdirSync(join(navi, "test")).filter((f) => f.endsWith(".test.ts")).sort();
if (!files.length) { console.error("✗ test/*.test.ts 가 없다 — 러너가 빈 그물이다"); process.exit(1); }

const out = mkdtempSync(join(tmpdir(), "fl-navi-test-"));
let fail = 0;
try {
  for (const f of files) {
    const outfile = join(out, f.replace(/\.ts$/, ".mjs"));
    await build({
      entryPoints: [join(navi, "test", f)], bundle: true, platform: "node",
      format: "esm", outfile, logLevel: "error", target: "node22",
    });
    const before = tests.length;
    await import(pathToFileURL(outfile).href);
    const mine = tests.slice(before);
    if (!mine.length) { console.error(`✗ ${f} 에 test() 가 0개다`); fail++; }
    for (const t of mine) {
      try { await t.fn(); console.log(`  ✓ ${f} · ${t.name}`); }
      catch (e) { fail++; console.log(`  ✗ ${f} · ${t.name}\n      ${String(e?.message ?? e).split("\n").join("\n      ")}`); }
    }
  }
} finally { rmSync(out, { recursive: true, force: true }); }

console.log(`\n${tests.length - fail} 통과 · ${fail} 실패 (${files.length} 파일)`);
process.exit(fail ? 1 : 0);
