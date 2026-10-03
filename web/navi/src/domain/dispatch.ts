/**
 * dispatch.ts — 관제가 **내비를 여는 주소**. 순수 함수.  (DECISIONS §351)
 *
 * ★ 왜 생겼나 (2026-10-02). `OpsApp` 의 「출동 지령 — 내비 열기 »」 버튼이
 *   `./?incident=…` 를 열었다. **상대 주소 `./` 는 지금 있는 자리다.** 배포에서
 *   관제는 루트(`/<repo>/`)에 앉아 있고 그 index.html 에는 `__FL_VIEW="ops"` 가
 *   박혀 있으므로(§258), 그 버튼은 **관제를 한 장 더 열었다.** 내비는 거기 없다.
 *
 * ★ **경로로 판정하지 않는다.** `main.tsx` 가 같은 함정을 적어 뒀다 — dev 서버의
 *   루트는 `web/navi` 라 `location.pathname` 이 `/` 고, 경로로 보면 개발에서
 *   기본 화면이 뒤집힌다. 그래서 여기도 **박아 넣은 표시**(`__FL_VIEW`)를 읽는다.
 *   화면을 고르는 근거가 `main.tsx` 와 **같은 값**이어야 둘이 안 갈린다.
 *
 *       __FL_VIEW === "ops"   배포 루트의 관제다        내비는 `navi/` 아래
 *       그 밖                  dev · `?view=ops` 로 온 관제  내비는 같은 자리
 *
 * ★ 뒤쪽에서 `view` 를 안 붙인다. `main.tsx` 가 `?view` 를 먼저 읽고 없으면
 *   `__FL_VIEW` 를 보는데, dev 에는 그 표시가 없으므로 **쿼리를 비우는 것**이
 *   곧 내비다. `view=navi` 를 붙이면 「ops 가 아닌 값」이라는 우연에 기대게 된다.
 *
 * IN    화면 표시(`__FL_VIEW`) · 사건 좌표 · 이름 · 차종 · 센터
 * OUT   문자열 주소 (순수)
 * 밖    **열지 않는다.** `window.open` 은 부르는 쪽 일이다 — 그래야 시험이
 *       브라우저 없이 이 판단만 잰다. **주소가 실재하는지도 안 본다**(배포 소관).
 */

/** 출동 지령 한 건. 좌표는 `[lon, lat]`. */
export interface Dispatch {
  at: [number, number];
  label: string;
  vehicle: string;
  station: string;
}

/** 내비가 사는 자리. `__FL_VIEW` 가 `"ops"` 면 배포 루트의 관제다. */
export function naviBase(view: string | undefined | null): string {
  return view === "ops" ? "./navi/" : "./";
}

/**
 * 관제 → 내비 주소. 좌표는 6자리로 끊는다(약 11cm — 구간 분해능보다 작다).
 *
 * ★ 2026-10-04 (§386). `demo` 를 붙이면 `?demo=1` 이 따라간다 — **발표용**이고
 *   내비가 경로 주행으로 돈다. 기본은 꺼짐이다. 켜는 쪽을 명시하지 않으면
 *   지령 링크가 전부 모의 주행으로 나가고, 그러면 화면의 차가 운전자가
 *   아니게 된다(§W13-1 이 `?dev` 에서 겪은 그것이다).
 */
export function dispatchUrl(view: string | undefined | null, d: Dispatch,
                            demo = false): string {
  const q = new URLSearchParams({
    incident: `${d.at[0].toFixed(6)},${d.at[1].toFixed(6)}`,
    label: d.label,
    vehicle: d.vehicle,
    station: d.station,
  });
  if (demo) q.set("demo", "1");
  return `${naviBase(view)}?${q.toString()}`;
}
