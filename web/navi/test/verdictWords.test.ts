/**
 * test/verdictWords.test.ts — 판정 이름은 **`style` 한 곳**에서 읽는다.  (PLAN #265 · DECISIONS §843)
 *
 * 범례는 「영상으로 확정 못 함」 · 「영상판정 전」 이라 부르는데 카드와 경로 문구가 「폭 모름」 · 「확인 필요」 로 부르면 한 화면이 같은 것을 둘로 부른다.
 * 화면 소스에 옛 낱말이 **코드로** 다시 들어오면 운다(주석은 안 센다).
 */
import graph from "../../data/navi_graph.json";
import { ok, test } from "./harness";

/** `node:fs` 를 안 쓴다 — `layering.test.ts` 와 같이 vite 가 빌드 시각에 파일을 문자열로 박아 준다 */
const FILES: Record<string, string> = import.meta.glob("../src/**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true });
const code = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "").replace(/(?<!:)\/\/[^\n]*$/gm, "");

test("화면 소스에 옛 판정 낱말(폭 모름 · 확인 필요)이 코드로 남지 않는다", () => {
  const left: string[] = [];
  for (const [p, src] of Object.entries(FILES)) {
    const c = code(src);
    for (const w of ["폭 모름", "확인 필요"]) if (c.includes(w)) left.push(`${p} · ${w}`);
  }
  ok(left.length === 0, `범례와 말이 갈린다: ${left.join(" / ")}`);
});

test("발행 자료의 style 이름이 새 낱말이다 — 화면이 읽는 곳이 낡지 않았다", () => {
  const st = graph.style as Record<string, { label: string }>;
  ok(st.unknown.label === "영상으로 확정 못 함" && st.needs_cv.label === "영상판정 전", `${st.unknown.label} · ${st.needs_cv.label}`);
});
