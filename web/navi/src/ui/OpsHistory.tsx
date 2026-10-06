/**
 * ui/OpsHistory.tsx — **출동 이력 요약(실측).** 관제 우측 패널의 접히는 한 칸.
 *                     (DECISIONS §414 · PLAN #143)
 *
 * ★ 2026-10-06. `OpsApp.tsx` 에서 떼었다. §130 이 넷을 뗀 것과 같은 이유이고
 *   같은 기준이다 — **상태를 하나도 안 지는 것부터** 뗀다. 이 조각은 펼침 여부
 *   하나만 지고, 그것도 부모가 준다.
 *
 * ★ **기본으로 안 편다.** 지금 이 순간 안 바뀌는 수이고, 관제사가 사건을 받는
 *   동안 읽을 것이 아니다. 지우지는 않는다 — 발표에서 드는 근거다.
 *   **빼는 것과 접는 것은 다르다**: 뺀 것은 못 찾고 접은 것은 한 번 누르면 연다.
 *
 * IN    요약(`loadHistory` 가 낸다) · 펼침 여부
 * OUT   화면
 * 밖    **수를 안 만든다.** 중앙값도 건수도 파이썬이 낸 것을 그대로 쓴다 —
 *       화면이 통계를 계산하면 그 수의 집이 둘이 된다.
 */
import { Row, Sec } from "./OpsBits";
import { D, linkBtn } from "./opsTheme";
import { fmtSec } from "./tokens";

interface Center { n: number; median_s: number | null; straight_kmh?: number | null }
export interface HistorySummary {
  by_center: Record<string, Center>;
  fire_donggu: { n: number; median_s: number | null };
  resp_median_s?: number | null;
  resp_n?: number;
}

/** 센터 이름에서 꼬리를 줄인다 — 좁은 칸에 들어가야 한다 */
function shortCenter(k: string): string {
  return k.replace(/119안전센터|119구조대/, (m) => (m.includes("구조") ? " 구조대" : ""));
}

export function OpsHistory(
  { hs, open, onToggle }: { hs: HistorySummary; open: boolean; onToggle: () => void },
) {
  return (
    <Sec title="출동 이력 요약 (실측)">
      <button onClick={onToggle} style={linkBtn}>
        {open ? "접는다" : `펼친다 — 센터별 중앙값 · 동구 화재 ${hs.fire_donggu.n}건`}
      </button>
      {open && (
        <>
          {Object.entries(hs.by_center).filter(([, v]) => v.n >= 5).map(([k, v]) => (
            <Row key={k} k={`${shortCenter(k)} · ${v.n}건`}
                 v={`${fmtSec(v.median_s)}${v.straight_kmh ? ` · 직선 ${v.straight_kmh}km/h` : ""}`} />
          ))}
          <Row k={`동구 화재 · ${hs.fire_donggu.n}건`} v={fmtSec(hs.fire_donggu.median_s)} />
          <div style={{ fontSize: 10.5, color: D.sub, marginTop: 6, lineHeight: 1.5 }}>
            출동 지령 → 현장 도착. 직선 km/h 는 센터~지점 직선거리 ÷ 시간(실제 주행 속도의 하한).
          </div>
        </>
      )}
    </Sec>
  );
}
