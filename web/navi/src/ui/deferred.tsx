/**
 * ui/deferred.tsx — **첫 화면에 안 쓰이는 부품을 진입 청크 밖에 둔다.**
 *
 * ── 왜 생겼나 ──────────────────────────────────────────────────
 * `naviweight --build` 의 진입 청크 래칫(127KB)이 PR #360 의 배포 `dry` 를 막았다
 * (130.56KB · 래칫보다 512바이트 위). 165커밋이 쌓이는 동안 주행 화면 부품이
 * 전부 `App.tsx` 의 정적 import 로 진입 청크에 들어와 있었다. 래칫을 올리지 않고
 * **첫 화면이 안 쓰는 것을 뒤로 뺀다.**
 *
 * ── 무엇을 미뤘나 · 왜 첫 화면이 아닌가 ─────────────────────────
 *   RouteBrief       `s.screen === "brief"` 에서만 선다 — 첫 화면은 `wait`(WaitPanel)이다
 *   BottleneckPanel  주행 화면(`!s.planning && hud`)에서만 선다
 *   ShareChip        주행 화면에서만 선다
 *   DevBar           `?dev=1` 일 때만 선다 — 배포본에서는 아예 안 받는다
 *
 * ★ **「나중에 온다」지 「안 온다」가 아니다.** 서비스 워커는 **첫 방문에서 실제로
 *   쓴 것만** 캐시한다(`public/sw.js` — 목록을 안 적는다). 미룬 청크를 안 받은 채
 *   통신이 끊기면 주행 화면이 비어 버린다. 그래서 `prefetch()` 가 **데이터가 온 직후
 *   유휴 시간에** 미룬 부품(DevBar 제외)을 미리 받는다 — 브라우저가 받아 SW 캐시에 든다.
 * ★ 폴백이 `null` 이다. 미리 받은 뒤에는 지연이 한 틱이고, 폴백 문구가 깜빡이는 쪽이
 *   더 나쁘다. 못 받은 채 화면이 오면(아주 빠른 지령) 부품이 한 박자 늦게 선다.
 */
import { lazy } from "react";

const loadBrief = () => import("./RouteCompare").then((m) => ({ default: m.RouteBrief }));
const loadBottleneck = () => import("./BottleneckPanel").then((m) => ({ default: m.BottleneckPanel }));
const loadShareChip = () => import("./ShareChip").then((m) => ({ default: m.ShareChip }));
const loadLegend = () => import("./Legend").then((m) => ({ default: m.Legend }));
const loadDemoStrip = () => import("./DemoStrip").then((m) => ({ default: m.DemoStrip }));
const loadDevBar = () => import("./DevBar").then((m) => ({ default: m.DevBar }));

export const RouteBrief = lazy(loadBrief);
export const BottleneckPanel = lazy(loadBottleneck);
export const ShareChip = lazy(loadShareChip);
export const DevBar = lazy(loadDevBar);
export const Legend = lazy(loadLegend);               // 범례 — 주행 중 토글이라 첫 화면에 안 필요하다(진입 청크 래칫 · §713)
export const DemoStrip = lazy(loadDemoStrip);       // 시연 표 · 단추 — 첫 화면에 안 필요하다(`?demo=1` 이 아니면 단추 하나)

/** 미룬 부품(DevBar 제외)을 유휴 시간에 미리 받는다. 취소 함수를 돌려준다. */
export function prefetch(): () => void {
  const run = () => { for (const l of [loadBrief, loadBottleneck, loadShareChip, loadLegend, loadDemoStrip]) void l().catch(() => {}); };
  if (typeof requestIdleCallback === "function") {
    const id = requestIdleCallback(run, { timeout: 3000 });
    return () => cancelIdleCallback(id);
  }
  const t = setTimeout(run, 1500);
  return () => clearTimeout(t);
}
