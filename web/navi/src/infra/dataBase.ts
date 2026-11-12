/**
 * dataBase.ts — **발행물이 어디 있는가.** 한 자리에서 정한다.  (DECISIONS §273-9)
 *
 * ★ 2026-09-27. 관제 화면이 `navi_graph.json 404` 로 통째로 안 떴다. 두 화면이
 *   각자 `new URL("../data/", document.baseURI)` 로 주소를 만들고 있었고,
 *   그것은 **페이지가 `/navi/` 에 있을 때만** 맞다.
 *
 *       /fire-lane/navi/   baseURI 기준 ../data/  →  /fire-lane/data/   ✓
 *       /fire-lane/        baseURI 기준 ../data/  →  /data/             ✗ 404
 *
 *   §258 이 **관제를 루트에 앉히면서** 두 번째 줄이 생겼다. 자산 경로는 절대라
 *   그대로 떴고(그래서 §258 이 초록이었다) **데이터만 상대였다.**
 *
 * ★ 정답은 `vite.config.ts` 가 이미 알고 있었다 — 거기에
 *   `base.replace(/navi\/$/, "data/")` 가 있다. 런타임만 그것을 안 썼다.
 *   `import.meta.env.BASE_URL` 은 빌드가 박아 주는 같은 값이므로 **페이지가
 *   어느 주소에 있든** 데이터 자리는 하나로 고정된다.
 *
 * ★ 화면마다 따로 계산하지 않는다. 두 벌이던 자리가 한 벌 갈리면서 난 사고다.
 */
export function dataBase(): string {
  const b = import.meta.env.BASE_URL || "/";
  // `…/navi/` → `…/data/`. `navi/` 로 안 끝나면 그 아래 `data/` 다(개발 서버·루트 서빙).
  const p = b.endsWith("navi/") ? b.replace(/navi\/$/, "data/") : `${b}data/`;
  return new URL(p, location.origin).href;
}

/**
 * 앱 자산(서비스 워커 등)의 주소 — `BASE_URL` 에 상대 경로를 잇는다. **슬래시는 늘 하나다.**
 *
 * ★ 2026-11-12 (DECISIONS §708). 접합의 정본은 여기 둘(`dataBase` · `appUrl`)이다 — Vite 의 `BASE_URL` 은 **이미 끝에 슬래시가 있다**(`/` · `/fire-lane/navi/`) ·
 *   빌드 설정에 따라 빈 문자열일 수도 있다. 그 뒤에 `/` 를 또 붙이거나 앞에 `/` 가 붙은 상대 경로를 이으면 `//…` 가 되고, 브라우저는 그것을 **프로토콜 상대 URL**
 *   (`//fire-lane/…` = 호스트 `fire-lane`)로 읽는다. 그래서 상대 경로의 **앞 슬래시를 걷고** 밑의 **끝 슬래시를 하나로 맞춘다.**
 */
export function appUrl(rel: string, base: string = import.meta.env.BASE_URL): string {
  const b = (base || "/").replace(/\/*$/, "/");
  return b + rel.replace(/^\/+/, "");
}
