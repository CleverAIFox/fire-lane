#!/usr/bin/env node
/* tools/js_graph_check.mjs — web/js 모듈 문법 · 그래프 검사
   ════════════════════════════════════════════════════════════
   ★ 왜 필요한가 — `node --check` 만으로는 못 잡는다.

     contract.yml 은 `find web -name '*.js' | xargs node --check` 를 돌린다.
     app.js 가 클래식 스크립트일 때는 이게 맞았다. ES 모듈로 쪼갠 뒤로는
     아니다. Node 는 `.js` 를 CommonJS 로 먼저 읽고, `export` 때문에 실패하면
     조용히 넘어간다. 실측(node v22):

         export const a = 1;
         const b = {{{;           ← 명백한 문법 오류

       node --check bad.js    → 종료코드 0   ★ 통과한다
       node --check bad.mjs   → 종료코드 1
       node --input-type=module --check < bad.js → 종료코드 1

     즉 모듈로 쪼갠 순간 CI 의 JS 문법 검사가 **조용히 무력화된다.**
     이 저장소가 계속 겪은 종류의 사고다 — turn_restriction 이 전국
     44,125행을 읽고도 [OK] 로 기록된 것과 구조가 같다. 검사가 죽었는데
     초록불이 뜬다.

   검사 3종:
     1. 문법      --input-type=module 로 실제 파싱
     2. 미해결    import 대상 파일이 실제로 있는가 (오타·이름 변경)
     3. 순환      A → B → A. 브라우저에서는 "지도가 안 뜬다"로만 보인다

   사용:  node tools/js_graph_check.mjs
   ════════════════════════════════════════════════════════════ */
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve, relative } from "node:path";
import { execFileSync } from "node:child_process";

const ROOT = resolve(dirname(new URL(import.meta.url).pathname), "..");
const JS_DIR = join(ROOT, "web", "js");

function walk(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap(n => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : (n.endsWith(".js") ? [p] : []);
  });
}

const files = walk(JS_DIR);
if (files.length === 0) {
  console.log("web/js 가 없다 — 검사할 모듈 없음");
  process.exit(0);
}

const problems = [];

/* ── 1. 문법 ─────────────────────────────────────────────── */
for (const f of files) {
  try {
    execFileSync(process.execPath, ["--input-type=module", "--check"], {
      input: readFileSync(f), stdio: ["pipe", "pipe", "pipe"],
    });
  } catch (e) {
    const msg = (e.stderr?.toString() || "").split("\n")
      .filter(l => l.includes("Error") || l.includes(".js:")).slice(0, 2).join(" | ");
    problems.push(`문법  ${relative(ROOT, f)}\n        ${msg}`);
  }
}

/* ── 2·3. import 그래프 ──────────────────────────────────── */
const IMPORT_RE = /^\s*(?:import|export)\s[^;]*?from\s+["'](\.[^"']+)["']/gm;
const graph = new Map();

for (const f of files) {
  const srcText = readFileSync(f, "utf8");
  const deps = [];
  for (const m of srcText.matchAll(IMPORT_RE)) {
    const target = resolve(dirname(f), m[1]);
    if (!existsSync(target)) {
      problems.push(`미해결 ${relative(ROOT, f)}  →  ${m[1]}  (그 파일이 없다)`);
      continue;
    }
    deps.push(target);
  }
  graph.set(f, deps);
}

const seen = new Set(), stack = [], cycles = new Set();
function walkDeps(n) {
  if (stack.includes(n)) {
    cycles.add(stack.slice(stack.indexOf(n)).concat(n)
      .map(p => relative(ROOT, p)).join("\n          → "));
    return;
  }
  if (seen.has(n)) return;
  seen.add(n); stack.push(n);
  for (const d of graph.get(n) || []) walkDeps(d);
  stack.pop();
}
for (const f of files) walkDeps(f);
for (const c of cycles) problems.push(`순환  ${c}`);

/* ── 결과 ────────────────────────────────────────────────── */
if (problems.length) {
  console.error(`\n★ web/js 검사 실패 — ${problems.length}건\n`);
  problems.forEach(p => console.error("  " + p + "\n"));
  process.exit(1);
}

const edges = [...graph.values()].reduce((a, d) => a + d.length, 0);
console.log(`OK  web/js  ${files.length}개 모듈 · import ${edges}개 · 순환 0 · 미해결 0`);
