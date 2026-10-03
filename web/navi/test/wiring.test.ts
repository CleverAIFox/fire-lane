/**
 * test/wiring.test.ts — **TS 소스가 실제로 불리는가.** (DECISIONS §366-2)
 *
 * ── 왜 생겼나 ───────────────────────────────────────────────────
 * 파이썬 쪽에는 `tests/test_tools_are_wired.py` 가 있다 — 「도구가 어디서도
 * 안 불리면 운다. 면제는 사유와 함께 적는다」. **TS 쪽에는 대응물이 없었다.**
 * `test/layering.test.ts` 가 묻는 것은 「A 가 B 를 import 하는가」로 **방향**이고,
 * 「아무도 B 를 import 하지 않는가」는 아무도 안 물었다.
 *
 * 2026-10-03 실측으로 **고아 하나**가 나왔다 — `src/infra/matching.ts` 90줄.
 * 그리고 그 고아가 혼자가 아니었다(§366-2) —
 *
 *     tools/naviweight.ALLOWED   `api.mapbox.com` 을 **사유와 함께** 허용했고
 *                                그 사유가 「`infra/matching.ts` 가 실패하면
 *                                원래 점을 쓴다」였다 — **안 돌는 코드의 런타임
 *                                되돌림**을 근거로 바깥 의존 하나를 들고 있었다
 *     build-navi/action.yml      토큰이 없으면 **배포가 죽는다**. 그 토큰을 쓰는
 *                                코드가 번들에 없었다
 *
 * 즉 고아 하나가 **바깥 의존 선언과 배포 전건까지** 끌고 있었다. 「안 쓰는
 * 파일은 그냥 있는 것」이 아니다.
 *
 * ★ 판정을 `orphans()` 로 **꺼냈다.** 실제 트리에 걸어만 두면 트리가 깨끗해진
 *   날부터 이 검사가 무엇을 하는지 아무도 모른다 — 합성 입력이 그 함수를
 *   재게 한다(§17-0 · `fp_valid` 가 배운 그 형태).
 *
 * 밖 — **「많이 불리는가」는 안 본다.** 한 곳에서만 불려도 배선이다.
 *      **「쓸모가 있는가」도 안 본다** — 그것은 사람의 판단이고 §302 가 든다.
 *      **시험만 부르는 것은 고아로 센다** — 시험이 유일한 소비자인 모듈은
 *      제품에 안 실린다. 그것이 이 검사가 잡으려는 바로 그것이다.
 */
import { describe, expect, it } from "vitest";

/** ★ `node:fs` 를 안 쓴다 — `layering.test.ts` 와 같은 이유로 vite 가 준다. */
const SRC: Record<string, string> = import.meta.glob(
  "../src/**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true },
);

/**
 * 진입점 — 누가 import 하지 않아도 **번들러가 부른다.**
 * ★ 사유 없는 이름은 선언이 아니다(`naviweight.ALLOWED` 와 같은 규율).
 */
export const ROOTS: Record<string, string> = {
  "src/main.tsx":
    "진입점이다. `index.html` 의 `<script type=module src>` 가 부른다 — "
    + "TS import 로는 안 보인다",
  "src/vite-env.d.ts":
    "타입 선언 전용(`/// <reference types=vite/client>`). 값을 안 내보내므로 "
    + "import 될 일이 없고, 지우면 `import.meta.env` 타입이 사라진다",
};

/** `import … from "X"` · `export … from "X"` · `import("X")` · `import "X"` */
const SPEC =
  /(?:^|\n)\s*(?:import|export)[\s\S]{0,400}?from\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)|(?:^|\n)\s*import\s*["']([^"']+)["']/g;

function specs(src: string): string[] {
  const out: string[] = [];
  for (const m of src.matchAll(SPEC)) {
    const s = m[1] ?? m[2] ?? m[3];
    if (s) out.push(s);
  }
  return out;
}

/** `../src/domain/cv.ts` → `src/domain/cv.ts` */
function norm(key: string): string {
  return key.replace(/^\.\.\//, "");
}

/** `a/b/../c` → `a/c`. `path` 를 안 쓴다(브라우저 런타임) */
function resolve(fromFile: string, spec: string): string | null {
  if (!spec.startsWith(".")) return null;
  const parts = fromFile.split("/").slice(0, -1).concat(spec.split("/"));
  const stack: string[] = [];
  for (const p of parts) {
    if (p === "." || p === "") continue;
    if (p === "..") stack.pop();
    else stack.push(p);
  }
  return stack.join("/");
}

/**
 * **아무도 import 하지 않는 파일.** 판정은 이 함수 하나다.
 *
 * @param files 파일 경로 → 내용. 키는 `src/…` 꼴
 * @param roots 진입점(사유 딸린 표의 키)
 */
export function orphans(
  files: Record<string, string>, roots: Iterable<string>,
): string[] {
  const used = new Set<string>();
  for (const [f, src] of Object.entries(files)) {
    for (const s of specs(src)) {
      const base = resolve(f, s);
      if (base == null) continue;
      for (const cand of [base, `${base}.ts`, `${base}.tsx`,
                          `${base}/index.ts`, `${base}/index.tsx`]) {
        if (cand in files) { used.add(cand); break; }
      }
    }
  }
  const rootSet = new Set(roots);
  return Object.keys(files).filter((f) => !used.has(f) && !rootSet.has(f)).sort();
}

describe("고아 모듈", () => {
  const files = Object.fromEntries(
    Object.entries(SRC).map(([k, v]) => [norm(k), v]));

  it("★ 소스를 0개 못 읽으면 **이 검사가 빈 그물이다**", () => {
    expect(Object.keys(files).length).toBeGreaterThan(50);
  });

  it("아무도 import 하지 않는 소스가 없다", () => {
    const got = orphans(files, Object.keys(ROOTS));
    expect(got, [
      "아무도 import 하지 않는 소스가 있다:",
      ...got.map((f) => `  ${f}`),
      "",
      "  셋 중 하나다 —",
      "    ① 배선을 잊었다        → 부르는 자리를 만든다",
      "    ② 쓸모가 없어졌다      → **지운다**(§302 — 소비자 0 은 철거로 답한다)",
      "    ③ 진입점이다          → `ROOTS` 에 **사유와 함께** 적는다",
      "  ★ 시험만 부르는 것은 고아다. 제품에 안 실린다.",
      "  ★ 지울 때 **그 파일이 끌고 있는 것**을 같이 본다 — `matching.ts` 는",
      "    바깥 의존 선언 하나와 배포 전건 하나를 끌고 있었다(§366-2).",
    ].join("\n")).toEqual([]);
  });

  it("진입점 면제는 **사유가 본체다** — 한 줄짜리 사유는 사유가 아니다", () => {
    const thin = Object.entries(ROOTS).filter(([, w]) => w.length < 40);
    expect(thin.map(([k]) => k)).toEqual([]);
  });

  it("진입점 선언이 **실재하는 파일**을 든다 — 지운 파일의 면제는 죽은 면제다", () => {
    const gone = Object.keys(ROOTS).filter((f) => !(f in files));
    expect(gone).toEqual([]);
  });
});

describe("★ 판정 양성 대조 — 합성 입력으로 생사를 본다", () => {
  it("고아를 심으면 집어낸다", () => {
    const f = {
      "src/main.tsx": 'import { a } from "./domain/a";',
      "src/domain/a.ts": "export const a = 1;",
      "src/domain/dead.ts": "export const d = 2;",
    };
    expect(orphans(f, ["src/main.tsx"])).toEqual(["src/domain/dead.ts"]);
  });

  it("★ 불리는 것은 **안** 집는다 — 「전부 고아」로 틀리지 않는다", () => {
    const f = {
      "src/main.tsx": 'import { a } from "./domain/a";',
      "src/domain/a.ts": "export const a = 1;",
    };
    expect(orphans(f, ["src/main.tsx"])).toEqual([]);
  });

  it("네 import 꼴을 다 본다 — 하나라도 놓치면 산 파일이 고아로 뜬다", () => {
    const f = {
      "src/main.tsx": [
        'import { a } from "./a";',
        'export { b } from "./b";',
        'const c = await import("./c");',
        'import "./d";',
      ].join("\n"),
      "src/a.ts": "export const a = 1;",
      "src/b.ts": "export const b = 1;",
      "src/c.ts": "export const c = 1;",
      "src/d.ts": "console.log(1);",
    };
    expect(orphans(f, ["src/main.tsx"])).toEqual([]);
  });

  it("확장자 없는 지목과 디렉터리 `index` 를 푼다", () => {
    const f = {
      "src/main.tsx": 'import { a } from "./dir";\nimport { b } from "./b";',
      "src/dir/index.ts": "export const a = 1;",
      "src/b.tsx": "export const b = 1;",
    };
    expect(orphans(f, ["src/main.tsx"])).toEqual([]);
  });

  it("`..` 를 거슬러 올라가는 지목을 푼다", () => {
    const f = {
      "src/main.tsx": 'import { x } from "./app/h";',
      "src/app/h.ts": 'import { y } from "../domain/y";\nexport const x = y;',
      "src/domain/y.ts": "export const y = 1;",
    };
    expect(orphans(f, ["src/main.tsx"])).toEqual([]);
  });

  it("바깥 꾸러미(`react` · `maplibre-gl`)는 파일이 아니라 **무시한다**", () => {
    const f = {
      "src/main.tsx": 'import React from "react";\nimport "maplibre-gl/dist/x.css";',
    };
    expect(orphans(f, ["src/main.tsx"])).toEqual([]);
  });
});
