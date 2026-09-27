/**
 * app/useNow.ts — 초 단위 시계.
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `App.tsx` 가 640줄로 상한(600)을 넘었다. 이 훅은 **아무것도 모르고**
 *   초마다 시각만 낸다 — 형제 여섯이 사는 `app/` 의 규율대로 한 훅이 한 파일이다.
 *
 * ★ 1초다. 상단 「현재 시간」 과 「마지막 갱신」 이 이것을 읽으므로 더 잦으면 리렌더만
 *   늘고, 더 드물면 시계가 멈춘 것처럼 보인다.
 *
 * IN    (없음)
 * OUT   Date — 초마다 새 값
 * 밖    형식을 정하지 않는다. 「09:07」 로 적는 것은 `ui/tokens.ts::hhmm` 이다.
 */
import { useEffect, useState } from "react";

export function useNow(): Date {
  const [t, setT] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setT(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return t;
}
