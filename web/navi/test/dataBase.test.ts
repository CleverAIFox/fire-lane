/**
 * dataBase.test.ts — 발행물 주소가 **페이지 위치와 무관한가.**  (DECISIONS §273-9)
 *
 * ★ 관제가 루트에 앉으면서 `navi_graph.json 404` 로 통째로 안 떴다. 원인은
 *   `document.baseURI` 기준 상대 경로였고, 그것은 페이지가 `/navi/` 에 있을
 *   때만 맞는다. 여기가 무는 것은 **어느 주소에서든 같은 자리를 가리키는가** 하나다.
 */
import { describe, expect, it, vi, afterEach } from "vitest";

async function withBase(base: string, origin = "https://x.github.io") {
  vi.resetModules();
  vi.stubEnv("BASE_URL", base);
  vi.stubGlobal("location", { origin } as Location);
  const { dataBase } = await import("../src/infra/dataBase");
  return dataBase();
}

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("dataBase", () => {
  it("배포 base 에서 저장소 아래 data 를 가리킨다", async () => {
    expect(await withBase("/fire-lane/navi/")).toBe("https://x.github.io/fire-lane/data/");
  });

  it("★ 관제가 루트에 앉아도 같은 자리다 — 이것이 404 의 원인이었다", async () => {
    // 루트 배포본도 같은 번들이라 BASE_URL 은 그대로 `/fire-lane/navi/` 다.
    // 페이지 주소가 `/fire-lane/` 여도 데이터 자리는 안 움직여야 한다.
    const fromRoot = await withBase("/fire-lane/navi/");
    const fromNavi = await withBase("/fire-lane/navi/");
    expect(fromRoot).toBe(fromNavi);
  });

  it("base 가 navi/ 로 안 끝나면 그 아래 data/ 다", async () => {
    expect(await withBase("/")).toBe("https://x.github.io/data/");
    expect(await withBase("/sub/")).toBe("https://x.github.io/sub/data/");
  });

  it("★ baseURI 를 안 본다 — 그것이 페이지 위치에 흔들리던 자리다", async () => {
    // ★ `node:fs` 를 안 쓴다 — vite 가 빌드 시각에 읽어 문자열로 준다(layering.test 와 같은 이유).
    const FILES = import.meta.glob("../src/**/*.ts", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
    const bad = Object.entries(FILES)
      .filter(([, t]) => t.replace(/\/\*[\s\S]*?\*\//g, "").includes("document.baseURI"))
      .map(([f]) => f);
    expect(bad, "발행물 주소를 baseURI 로 만드는 자리가 남아 있다 — 루트에서 404 가 난다").toEqual([]);
  });
});
