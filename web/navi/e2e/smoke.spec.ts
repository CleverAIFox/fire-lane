/**
 * e2e/smoke.spec.ts — 두 화면이 **뜨는가** · 콘솔이 **조용한가**.  (DECISIONS §700 · PLAN #223)
 *
 * ★ 과녁은 둘뿐이다. 화면의 글자 · 색 · 배치는 안 묻는다 — 화면을 고칠 때마다 시험이 울면 아무도 이 시험을 안 믿는다.
 * ★ **한계(적어 둔다).** 「콘솔 오류 0」은 모든 흰 화면을 못 잡는다 — 오류 없이 **아무것도 안 그리는** 화면(조건이 틀려 빈 분기로 가는 것 ·
 *   데이터가 비어 지도가 빈 것 · CSS 로 가려진 것)은 통과한다. 그래서 첫째 물음(루트에 글자가 `MIN_TEXT` 이상)을 같이 건다. 그것도 못 잡는
 *   것은 **그려진 내용이 틀린** 화면이다(지도 색 · 판정 값) — 그것은 사람의 눈과 `uicheck` · vitest 의 몫이다.
 */
import { type ChildProcess, spawn } from "node:child_process";
import fs from "node:fs";
import { type Page, expect, test } from "@playwright/test";

/** 「떴다」의 문턱 — 관제 816자 · 내비 110자였다(2026-11-12). 흰 화면은 0 이다. 세세한 글자는 안 묻는다. */
const MIN_TEXT = 30;
const VIEWS = [
  { name: "내비", query: "?dev=1" },
  { name: "관제", query: "?view=ops" },
] as const;

/** 한 화면의 소음을 모은다 — 같은 출처의 실패한 요청 · 콘솔 오류 · 잡히지 않은 예외. 경고(warning)는 안 모은다(지도가 자주 낸다). */
function listen(page: Page, origin: string): string[] {
  const bad: string[] = [];
  page.on("pageerror", (e) => bad.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") bad.push(`console.error: ${m.text()}`); });
  page.on("response", (r) => {
    if (r.url().startsWith(origin) && r.status() >= 400) bad.push(`HTTP ${r.status()}: ${r.url().replace(origin, "/")}`);
  });
  page.on("requestfailed", (r) => {
    if (r.url().startsWith(origin)) bad.push(`requestfailed: ${r.url().replace(origin, "/")} (${r.failure()?.errorText})`);
  });
  return bad;
}

async function rootText(page: Page): Promise<number> {
  return (await page.locator("#root").innerText().catch(() => "")).trim().length;
}

async function opens(page: Page, url: string): Promise<void> {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect.poll(() => rootText(page), { timeout: 30_000, message: "루트에 글자가 안 뜬다 — 흰 화면" }).toBeGreaterThanOrEqual(MIN_TEXT);
  await page.waitForTimeout(3000);       // 늦게 나는 오류(미룬 청크 · 지도 · 데이터)를 기다린다
}

for (const v of VIEWS) {
  test(`${v.name} 뷰가 뜨고 콘솔이 조용하다`, async ({ page, baseURL }) => {
    const origin = new URL(baseURL!).origin;
    const bad = listen(page, origin);
    await opens(page, `${baseURL}${v.query}`);
    expect(bad, "콘솔 오류 · 잡히지 않은 예외 · 실패한 요청").toEqual([]);
  });
}

/**
 * ★ 오늘의 결함(DECISIONS §699)을 **그대로 되풀이한다** — 개발 서버가 의존을 다시 최적화한 뒤에도 관제가 뜬다.
 *   서비스 워커가 개발 모듈을 쥐고 있으면 옛 `?v=` 모듈과 새 모듈이 섞여 React 가 두 벌이 되고 **여기서 빨개진다.**
 *   개발 서버가 필요하므로 `dev` 프로젝트에서만 돈다. 자기 서버 · 자기 의존 캐시를 쓴다(5185).
 */
test.describe("개발 서버 재최적화", () => {
  const PORT = 5185;
  const CACHE = "node_modules/.vite-smoke-restart";
  let server: ChildProcess | null = null;

  async function start(): Promise<void> {
    server = spawn("npx", ["vite", "--port", String(PORT), "--strictPort", "--host", "127.0.0.1"], {
      env: { ...process.env, FL_VITE_CACHE: CACHE }, detached: true, stdio: "ignore",
    });
    const url = `http://127.0.0.1:${PORT}/fire-lane/navi/`;
    for (let i = 0; i < 60; i++) {
      if (await fetch(url).then((r) => r.ok).catch(() => false)) return;
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error("개발 서버가 안 선다");
  }
  async function stop(): Promise<void> {
    if (server?.pid) { try { process.kill(-server.pid); } catch { /* 이미 죽었다 */ } }
    server = null;
    await new Promise((r) => setTimeout(r, 1000));
  }
  test.afterEach(async () => { await stop(); fs.rmSync(CACHE, { recursive: true, force: true }); });

  test("재최적화(의존 해시가 바뀐다) 뒤에도 관제가 뜬다", async ({ page }, info) => {
    test.skip(info.project.name !== "dev", "개발 서버 시험이다");
    test.setTimeout(150_000);
    fs.rmSync(CACHE, { recursive: true, force: true });
    const base = `http://127.0.0.1:${PORT}/fire-lane/navi/`;
    await start();
    // 내비를 두 번 연다 — 서비스 워커가 있다면 첫 방문 뒤에 붙고 둘째 방문의 모듈을 담는다
    await opens(page, `${base}?dev=1`);
    await opens(page, `${base}?dev=1`);
    await page.goto("about:blank");      // 열린 쪽을 놓는다 — 서버가 죽었다 살아나면 개발 클라이언트가 스스로 새로 고쳐 다음 이동을 끊는다
    await stop();
    fs.rmSync(CACHE, { recursive: true, force: true });      // 의존 캐시를 지우고 다시 띄운다 = 새 `?v=` 해시
    await start();
    const bad = listen(page, new URL(base).origin);
    await opens(page, `${base}?view=ops`);
    expect(bad, "재최적화 뒤 관제 뷰가 깨졌다(React 가 두 벌이 아닌가)").toEqual([]);
  });
});
