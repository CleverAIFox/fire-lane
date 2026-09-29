/**
 * sw.js — **통신이 끊겨도 돈다.**  (PLAN §13 W13-4 · DECISIONS §312)
 *
 * ★ 지하 주차장 · 산간 · 재난 현장은 통신이 제일 먼저 끊기는 곳이고,
 *   출동은 정확히 그런 곳으로 간다. 「인터넷이 없으면 못 씁니다」는
 *   이 물건에서 답이 아니다.
 *
 * ── 두 갈래로 나눈다 ────────────────────────────────────────────
 *   껍데기(앱 · 지도 엔진 · 글자)   캐시 먼저.  판이 바뀌면 파일 이름이 바뀐다
 *   판정 데이터(../data/)          망 먼저.   되면 새것을 캐시에 넣고,
 *                                            안 되면 **마지막으로 받은 것**을 준다
 *
 * ★ 데이터를 캐시 먼저로 두면 안 된다. 폭 판정이 바뀌었는데 옛것을 보여 주면
 *   그것은 오프라인 지원이 아니라 **틀린 답**이다. 망이 되면 늘 새것을 쓴다.
 * ★ 낡은 판의 캐시는 활성화 때 지운다. 안 지우면 기기에 판이 쌓인다.
 */
const V = "fl-v1";
const SHELL = `${V}-shell`;
const DATA = `${V}-data`;

self.addEventListener("install", (e) => {
  // 미리 받지 않는다 — 첫 방문에서 실제로 쓴 것만 담는다. 무엇이 필요한지는
  // 브라우저가 안다. 목록을 손으로 적으면 그 목록이 반드시 낡는다.
  e.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (!k.startsWith(V)) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;   // 밖은 안 건드린다

  const isData = url.pathname.includes("/data/");
  e.respondWith((async () => {
    const cache = await caches.open(isData ? DATA : SHELL);
    if (isData) {
      try {
        const r = await fetch(req);
        if (r.ok) cache.put(req, r.clone());
        return r;
      } catch {
        const hit = await cache.match(req);
        if (hit) return hit;
        throw new Error("판정 데이터가 캐시에도 없다");
      }
    }
    const hit = await cache.match(req);
    if (hit) return hit;
    const r = await fetch(req);
    if (r.ok) cache.put(req, r.clone());
    return r;
  })());
});
