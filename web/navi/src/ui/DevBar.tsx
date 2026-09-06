/**
 * ui/DevBar.tsx — 개발·시연 조작. **와이어프레임에 없는 것이라 따로 둔다.**
 *
 * ★ 시연 때 통째로 숨길 수 있어야 해서 분리했다. `App.tsx` 에서 이
 *   컴포넌트만 빼면 화면이 와이어프레임 그대로가 된다.
 *
 * ★ 배속은 **재생 배속**이지 주행 속도가 아니다. 주행 속도는
 *   `domain/speed.ts` 가 구간 폭에서 낸다 — 큰길 50 · 골목 20km/h.
 *   시연에서 2분짜리 경로를 다 볼 수 없어서 남긴 것뿐이다.
 *
 * ★ `lenient`(안전/연결성)는 디버그 플래그가 아니라 **제품 기능**이다.
 *   최종 UI 에서는 정식 자리를 잡아야 한다.
 */
import { C, F } from "./tokens";

interface Props {
  hint: string;
  guiding: boolean;
  simSpeed: number;
  setSimSpeed: (v: number) => void;
  lenient: boolean;
  setLenient: (v: boolean) => void;
  firstPerson: boolean;
  setFirstPerson: (v: boolean) => void;
  onVehicle?: () => void;
  onBottleneck?: () => void;
  onReset: () => void;
}

export function DevBar(p: Props) {
  return (
    <div style={{
      position: "absolute", zIndex: 5, right: 14, bottom: 14,
      display: "flex", gap: 6, alignItems: "center",
      background: C.dark, border: "1px solid rgba(255,255,255,.1)",
      borderRadius: 12, padding: "8px 12px",
    }}>
      <span style={{ fontSize: F.small, opacity: .6, color: C.darkInk }}>
        {p.hint}
      </span>
      {p.guiding && (
        <>
          <B on={p.simSpeed > 0} onClick={() => p.setSimSpeed(p.simSpeed > 0 ? 0 : 1)}>
            {p.simSpeed > 0 ? "■" : "▶"}
          </B>
          {[1, 4].map((v) => (
            <B key={v} on={p.simSpeed === v} onClick={() => p.setSimSpeed(v)}>
              ×{v}
            </B>
          ))}
          {p.onBottleneck && <B on={false} onClick={p.onBottleneck}>병목</B>}
        </>
      )}
      {p.onVehicle && <B on={false} onClick={p.onVehicle}>차량</B>}
      <B on={p.lenient} onClick={() => p.setLenient(!p.lenient)}>
        {p.lenient ? "연결성" : "안전"}
      </B>
      <B on={p.firstPerson} onClick={() => p.setFirstPerson(!p.firstPerson)}>
        {p.firstPerson ? "1인칭" : "탐색"}
      </B>
      <B on={false} onClick={p.onReset}>초기화</B>
    </div>
  );
}

function B({ on, onClick, children }: {
  on: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button onClick={onClick} style={{
      background: on ? "rgba(74,209,143,.22)" : "transparent",
      border: `1px solid rgba(255,255,255,${on ? .3 : .14})`,
      borderRadius: 8, color: C.darkInk, padding: "6px 10px",
      fontSize: F.small, cursor: "pointer", fontFamily: F.family,
    }}>{children}</button>
  );
}
