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

// ── 접합 — 슬래시는 늘 하나다(DECISIONS §708) ─────────────────────────────────────────────
describe("접합", () => {
  // base 셋: 루트 `/` · 저장소 아래 `/fire-lane/`(끝 슬래시) · 빈 문자열 — 거기에 `navi/` 로 끝나는 배포 base 도 같이 문다.
  const BASES = ["/", "/fire-lane/", "", "/fire-lane/navi/", "/fire-lane"] as const;
  const noDouble = (u: string) => !new URL(u, "https://h.test").pathname.includes("//");

  it("dataBase — 어느 base 에서도 경로에 `//` 가 없고 슬래시로 끝난다", async () => {
    for (const b of BASES) {
      const d = await withBase(b);
      expect(noDouble(d), `base ${JSON.stringify(b)} → ${d}`).toBe(true);
      expect(d.endsWith("/"), `base ${JSON.stringify(b)} → ${d}`).toBe(true);
    }
  });

  it("dataBase + 상대 경로 이음(지형 타일 꼴) — `//` 가 안 생긴다", async () => {
    for (const b of BASES) {
      const url = (await withBase(b)) + "terrain/{z}/{x}/{y}.png";
      expect(noDouble(url), `base ${JSON.stringify(b)} → ${url}`).toBe(true);
    }
  });

  it("appUrl — 앞 슬래시를 걷고 밑의 끝 슬래시를 하나로 맞춘다(셋 base × 앞 슬래시 유무)", async () => {
    vi.resetModules();
    const { appUrl } = await import("../src/infra/dataBase");
    for (const b of BASES) for (const rel of ["sw.js", "/sw.js", "//sw.js"]) {
      const u = appUrl(rel, b);
      expect(u.includes("//"), `base ${JSON.stringify(b)} rel ${rel} → ${u}`).toBe(false);
      expect(u.endsWith("/sw.js")).toBe(true);
    }
    expect(appUrl("sw.js", "/fire-lane/")).toBe("/fire-lane/sw.js");
    expect(appUrl("sw.js", "")).toBe("/sw.js");
    expect(appUrl("sw.js", "/")).toBe("/sw.js");
  });

  it("★ 소스에서 base 를 잇는 자리가 둘뿐이다 — 데이터 주소에 `/…` 를 이어 붙이는 곳이 없다", () => {
    const FILES = import.meta.glob("../src/**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
    const code = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    // `dataUrl + "/…"` · `D + "/…"` · `${BASE_URL}/…` · `BASE_URL + "/…"` 꼴 — 앞 슬래시를 이으면 프로토콜 상대 URL 이 된다
    const bad = Object.entries(FILES).flatMap(([f, t]) => code(t).split("\n")
      .filter((ln) => /\b(dataUrl|dataBase\(\)|D|BASE_URL)\b\s*\+\s*["'`]\//.test(ln) || /\$\{[^}]*BASE_URL[^}]*\}\//.test(ln))
      .map((ln) => `${f}: ${ln.trim()}`));
    expect(bad, "base 뒤에 `/` 를 또 붙이는 자리가 있다 — `//…` 는 프로토콜 상대 URL 이다").toEqual([]);
    const users = Object.entries(FILES).filter(([f, t]) => !f.endsWith("infra/dataBase.ts") && /import\.meta\.env\.BASE_URL/.test(code(t))).map(([f]) => f);
    expect(users, "BASE_URL 을 직접 읽는 곳이 dataBase.ts 밖에 있다 — 접합은 `appUrl` · `dataBase` 가 든다").toEqual([]);
  });
});
