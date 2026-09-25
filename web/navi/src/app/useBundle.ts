/**
 * app/useBundle.ts — `web/data` 를 한 번 적재하고 스냅기를 세운다.
 *
 * ── 왜 갈랐나 (PLAN §1 #129) ────────────────────────────────────
 * ★ 2026-09-25. `useNavigation` 이 570줄로 넷을 들고 있었다 — **적재** · 위치원 배선 ·
 *   추측항법 · 경로와 단계 기계. 적재는 그 중 **한 번만 일어나고 다시 안 바뀌는** 것이라
 *   나머지와 수명이 다르다. 여기 있는 것은 앱이 사는 동안 한 번 돌고, 그 뒤로는 읽기만 한다.
 *
 * ★ 파이썬과 같은 답을 내는지 **적재 직후 즉시** 대조한다. 대조를 미루면 틀린 비용으로
 *   낸 경로를 사람이 먼저 본다 — 화면이 거짓말한 뒤에 아는 것은 늦다.
 *
 * ★ 알림(`notice`)은 이 훅이 안 가진다. 알림 칸은 하나이고 여러 곳이 번갈아 쓴다 —
 *   두 군데가 각자 들면 나중 것이 앞선 것을 못 지운다. 그래서 **쓰는 함수만** 받는다.
 *
 * IN    (없음 — `infra/dataSource` 가 `web/data` 를 읽는다) · 적재 끝 알림 · 알림 쓰기
 * OUT   data · fatal · tracker(ref) · snapAt
 * 밖    경로를 안 낸다. 단계(`Phase`)도 안 가른다 — 적재가 끝났다고 알리기만 한다.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { SCOPE_M } from "../config";
import { createTracker, prepare, snap as snapOnce, type Tracker } from "../domain/snap";
import { verifyAgainstPrecomputed } from "../domain/vehicle";
import { loadAll, type Bundle } from "../infra/dataSource";
import type { SnapResult } from "../domain/types";

export function useBundle(onReady: () => void, onNotice: (m: string) => void) {
  const [data, setData] = useState<Bundle | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const tracker = useRef<Tracker | null>(null);
  const prepared = useRef<ReturnType<typeof prepare> | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const d = await loadAll();
        // ★ 파이썬과 같은 답을 내는지 즉시 대조한다.
        const v = verifyAgainstPrecomputed(d.graph.edges, d.spec, d.routeVehicle);
        if (v.mismatch.length) {
          console.error("★ edgeCost 이식이 파이썬과 갈렸다", v.mismatch.slice(0, 10));
          onNotice(`edgeCost 대조 실패 — ${v.mismatch.length}건 (콘솔 확인)`);
        } else {
          console.info(`edgeCost 대조 OK — ${v.checked}구간 전량 일치`);
        }
        prepared.current = prepare(d.graph.edges.map((e) => ({
          seg_uid: e.seg_uid, verdict: e.verdict,
          width_min_m: e.width_min_m, seg_label: e.seg_label, coords: e.coords,
        })));
        tracker.current = createTracker(prepared.current);
        setData(d);
        onReady();
      } catch (e) { setFatal(String(e)); }
    })();
  }, [onReady, onNotice]);

  /** 좌표를 도로에 붙여본다. 목적지 후보의 판정을 미리 보는 데 쓴다. */
  const snapAt = useCallback((lon: number, lat: number): SnapResult | null => {
    if (!prepared.current) return null;
    const r = snapOnce(lon, lat, prepared.current, {});
    return r && r.dist_m <= SCOPE_M ? r : null;
  }, []);

  return { data, fatal, tracker, snapAt };
}
