/**
 * app/useFading.ts — 값이 바뀌면 보이고 잠시 뒤 사라진다.
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `App.tsx` 가 640줄로 상한(600)을 넘었다. 이 훅은 화면도 데이터도
 *   모르고 **한 값의 수명**만 진다 — `app/` 의 형제들과 같은 규율로 따로 산다.
 *
 * ★ 알림은 6초 뒤 내린다. 「위치 없음」 처럼 한 번 알면 되는 것이 주행 내내
 *   남아 남은 시간 알약 위를 가렸다(검수 스크린샷).
 *
 * ★ **같은 값이 다시 와도 새로 보이지 않는다.** 의존이 값 자체라, 같은 문구를 다시
 *   쓰면 React 가 바뀐 것으로 안 본다 — 반복되는 알림으로 화면을 막지 않는 쪽을 골랐다.
 *
 * IN    보일 값(없으면 null) · 보여 둘 시간(ms)
 * OUT   지금 보일 값, 또는 null
 * 밖    무엇을 알릴지 안 고른다. 고르는 것은 `useNavigation` 의 `notice` 다.
 */
import { useEffect, useState } from "react";

export function useFading(v: string | null, ms: number): string | null {
  const [shown, setShown] = useState<string | null>(null);
  useEffect(() => {
    setShown(v);
    if (!v) return;
    const t = setTimeout(() => setShown(null), ms);
    return () => clearTimeout(t);
  }, [v, ms]);
  return shown;
}
