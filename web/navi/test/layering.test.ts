/**
 * test/layering.test.ts — 계층 의존이 한 방향인가.
 *
 * ★ 2026-09-24 (DECISIONS §244). 파이썬에는 `tests/test_layering.py` 가 있는데
 *   **TS 쪽에는 대응물이 없었다.** 지금 `domain/` 이 깨끗한 것은 사실이지만
 *   그것은 **규율이지 강제가 아니다** — 그리고 이 저장소가 반복해 배운 형태가
 *   정확히 그것이다(규약은 문서에 있고 강제하는 검사가 없다 · MASTER §17).
 *
 * ★ 같은 날 파이썬 쪽 강제자에서 **구멍**이 나왔다 — `from X import Y` 를
 *   `X` 로만 기록해 `firelane.paths` 금지를 못 봤다. 그래서 여기서는
 *   **import 문 전체**를 정규식으로 잡고, 경로 문자열만으로 판정한다.
 *
 * 규칙 — 안쪽이 바깥쪽을 모른다.
 *
 *     domain/      순수. 프레임워크도, 다른 계층도 모른다
 *     infra/       domain 만 안다 (브라우저 API 를 감싼다)
 *     app/         domain · infra 를 안다 (React 훅)
 *     ui/ · components/   domain 만 안다. **훅 모듈을 모른다**
 *
 * 밖 — 무엇이 순수인가는 여기서 안 본다. 「A 가 B 를 import 하는가」만 본다.
 *      함수가 실제로 부수효과를 내는지는 이 검사의 물음이 아니다.
 */
import { test, ok } from "./harness";

/** ★ `node:fs` 를 안 쓴다 — `@types/node` 를 더하지 않으려고 **vite 가 이미 주는
 *  것**을 쓴다. 번들러가 빌드 시각에 파일을 읽어 문자열로 박아 준다. */
const FILES: Record<string, string> = import.meta.glob(
  "../src/**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true },
);

/** `import … from "X"` · `export … from "X"` · `import("X")` 의 X 전부. */
const FROM = /(?:^|\n)\s*(?:import|export)[\s\S]{0,400}?from\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;

/** 이 파일이 import 하는 것들. */
function imports(src: string): string[] {
  const out: string[] = [];
  for (const m of src.matchAll(FROM)) {
    const spec = m[1] ?? m[2];
    if (spec) out.push(spec);
  }
  return out;
}

/** `../src/ui/DevBar.tsx` → `ui`. glob 키는 언제나 이 꼴이다. */
function layerIn(key: string): string {
  return key.replace("../src/", "").split("/")[0];
}

/** 상대 import 가 닿는 계층. 패키지면 `pkg:<이름>`. */
function layerOf(spec: string, fromKey: string): string {
  if (!spec.startsWith(".")) return `pkg:${spec.split("/")[0]}`;
  const parts = fromKey.split("/").slice(0, -1);   // 자기 파일명을 뗀다
  for (const seg of spec.split("/")) {
    if (seg === ".") continue;
    else if (seg === "..") parts.pop();
    else parts.push(seg);
  }
  return layerIn(parts.join("/"));
}

/** 계층별 금지 목록. 「이 계층은 이것을 몰라야 한다」 */
const FORBIDDEN: Record<string, string[]> = {
  domain: ["pkg:react", "pkg:react-dom", "pkg:maplibre-gl", "infra", "app", "ui", "components"],
  infra: ["app", "ui", "components"],
  ui: ["app", "infra"],
  components: ["app"],
};

test("계층 의존이 한 방향이다 — 안쪽이 바깥쪽을 모른다", () => {
  const bad: string[] = [];
  for (const [key, src] of Object.entries(FILES)) {
    const banned = FORBIDDEN[layerIn(key)];
    if (!banned) continue;
    for (const spec of imports(src)) {
      const hit = layerOf(spec, key);
      if (banned.includes(hit)) bad.push(`${key.replace("../src/", "")} → ${spec} (${hit})`);
    }
  }
  ok(bad.length === 0,
     "계층을 거슬러 올라가는 import:\n  " + bad.join("\n  ") +
     "\n  타입만 넘나드는 것도 위반이다 — 계층은 런타임이 아니라 읽는 사람의 머릿속에서 먼저 무너진다." +
     "\n  공유 타입의 집은 `domain/types.ts` 다.");
});

test("★ 판별식이 살아 있다 — 합성 경로로 직접 문다", () => {
  // ★ 위 시험은 지금 초록이다. 초록인 검사는 제가 보고 있다는 것을 스스로
  //   증명하지 못한다 — 파이썬 쪽이 바로 그 상태로 `from X import Y` 를
  //   놓치고 있었다(DECISIONS §244).
  const f = "../src/domain/x.ts";
  ok(layerOf("../app/useNavigation", f) === "app", "상대경로가 계층으로 안 접힌다");
  ok(layerOf("./types", f) === "domain", "같은 계층을 다른 계층으로 읽는다");
  ok(layerOf("../infra/gps", f) === "infra", "형제 계층을 못 읽는다");
  ok(layerOf("react", f) === "pkg:react", "패키지를 계층으로 읽는다");
  ok(layerOf("maplibre-gl", f) === "pkg:maplibre-gl", "패키지 이름을 못 읽는다");

  const src = [
    'import { a } from "../app/x";',
    'import type { B } from "../app/y";',
    'export type { C } from "../infra/z";',
    'const m = await import("../ui/w");',
  ].join("\n");
  const seen = [...src.matchAll(FROM)].map((m) => m[1] ?? m[2]);
  ok(seen.length === 4,
     `import 꼴 넷 중 ${seen.length} 만 읽는다 — type-only · 재수출 · 동적 import 를 놓친다`);
});

test("계층이 실제로 존재한다 — 빈 목록을 초록으로 읽지 않는다", () => {
  const keys = Object.keys(FILES);
  ok(keys.length > 40, `src 에서 ${keys.length} 파일만 찾았다 — 수집기가 죽었다`);
  for (const layer of Object.keys(FORBIDDEN)) {
    const n = keys.filter((k) => layerIn(k) === layer).length;
    ok(n > 0, `${layer}/ 에 파일이 0개다 — 계층 이름이 바뀌었는데 목록이 안 따라왔다`);
  }
});
