/**
 * ui/DevBar.tsx — 개발·시연 조작. **와이어프레임에 없는 것이라 따로 둔다.**
 *
 * ★ 시연 때 통째로 숨길 수 있어야 해서 분리했다(`?dev=0`). 이 컴포넌트만
 *   빼면 화면이 와이어프레임 그대로가 된다.
 *
 * ★ 배속은 **재생 배속**이지 주행 속도가 아니다. 주행 속도는
 *   `domain/speed.ts` 가 구간 폭에서 낸다 — 큰길 50 · 골목 20km/h.
 *
 * ★ 2026-09-21 「시연 상태」 를 더했다. 와이어프레임 09-21 의 상태 화면을
 *   번호순으로 넘겨 본다. GPS 약함 · 통신 끊김 · 서버 오류 · 데이터 지연은
 *   **신호가 없어 여기서만 나온다** — 상단바가 「시연」 표지를 단다.
 *
 * ★ `lenient`(안전/연결성)는 디버그 플래그가 아니라 **제품 기능**이다.
 *
 * ★ 2026-09-22 (§213-3) 위치원 토글 · 순간이동. 기본이 「GPS 흉내」 다 —
 *   1Hz · σ5m · 40초마다 8초 음영. 「경로」 는 정답 점이 경로를 따라 걷는 것이라
 *   추정이 틀려도 맞아 보인다. 「+200m」 는 GPS 가 음영에서 튀어 돌아온 상황이고,
 *   옆의 「재동기화 N」 이 추정기가 그것을 알아챘는지를 센다.
 */
import type { PosMode } from "../app/useNavigation";
import { C, F } from "./tokens";
import { STATUS, STATUS_ORDER, type StatusKey } from "../domain/status";

interface Props {
  hint: string;
  guiding: boolean;
  simSpeed: number;
  setSimSpeed: (v: number) => void;
  posMode: PosMode;
  setPosMode: (v: PosMode) => void;
  onTeleport?: () => void;
  jumps: number;
  lastJumpM: number;
  lenient: boolean;
  setLenient: (v: boolean) => void;
  firstPerson: boolean;
  setFirstPerson: (v: boolean) => void;
  onBottleneck?: () => void;
  onReset: () => void;
  /** 시연 상태. null 이면 신호대로 */
  injected: StatusKey | null;
  setInjected: (k: StatusKey | null) => void;
  failNext: boolean;
  setFailNext: (v: boolean) => void;
}

export function DevBar(p: Props) {
  const i = p.injected ? STATUS_ORDER.indexOf(p.injected) : -1;
  const step = (d: number) => {
    const n = STATUS_ORDER.length;
    const j = i < 0 ? (d > 0 ? 0 : n - 1) : (i + d + n) % n;
    p.setInjected(STATUS_ORDER[j]);
  };
  return (
    <div style={{
      position: "absolute", zIndex: 7, bottom: 14,
      // 주행 전에는 좌측 패널의 단추를 가리지 않게 오른쪽, 주행 중에는
      // 병목 시트(오른쪽)를 가리지 않게 왼쪽.
      // ★ 2026-09-22. 주행 중에는 가운데 아래 남은 시간 알약을 가렸다 — 알약 왼쪽 반까지만 쓴다
      ...(p.guiding ? { left: 86, maxWidth: "calc(50vw - 260px)" } : { right: 14, maxWidth: 720 }),
      display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap",
      background: C.dark, border: "1px solid rgba(255,255,255,.1)",
      borderRadius: 12, padding: "8px 10px",
    }}>
      <span style={{ fontSize: F.small, opacity: .6, color: C.darkInk }}>{p.hint}</span>
      {p.guiding && (
        <>
          <B on={p.simSpeed > 0} onClick={() => p.setSimSpeed(p.simSpeed > 0 ? 0 : 1)}>
            {p.simSpeed > 0 ? "■" : "▶"}
          </B>
          {[1, 4, 10].map((v) => (
            <B key={v} on={p.simSpeed === v} onClick={() => p.setSimSpeed(v)}>×{v}</B>
          ))}
          <B on={p.posMode === "gpsSim"}
             onClick={() => p.setPosMode(p.posMode === "gpsSim" ? "route" : "gpsSim")}>
            {p.posMode === "gpsSim" ? "GPS 흉내" : "경로 주행"}
          </B>
          {p.onTeleport && <B on={false} onClick={p.onTeleport}>+200m</B>}
          <span style={{ fontSize: F.small, opacity: .7, color: C.darkInk }}>
            재동기화 {p.jumps}{p.jumps ? ` (${p.lastJumpM > 0 ? "+" : ""}${p.lastJumpM}m)` : ""}
          </span>
          {p.onBottleneck && <B on={false} onClick={p.onBottleneck}>병목</B>}
          <span style={{ width: 1, height: 20, background: "rgba(255,255,255,.2)" }} />
          <B on={false} onClick={() => step(-1)}>◀</B>
          <B on={!!p.injected} onClick={() => p.setInjected(null)}>
            {p.injected ? `시연 ${STATUS[p.injected].wf[0]}` : "신호대로"}
          </B>
          <B on={false} onClick={() => step(1)}>▶</B>
          <B on={p.failNext} onClick={() => p.setFailNext(!p.failNext)}>
            {p.failNext ? "다음 공유 실패" : "공유 정상"}
          </B>
        </>
      )}
      <B on={p.lenient} onClick={() => p.setLenient(!p.lenient)}>
        {p.lenient ? "연결성" : "안전"}
      </B>
      {p.guiding && (
        <B on={p.firstPerson} onClick={() => p.setFirstPerson(!p.firstPerson)}>
          {p.firstPerson ? "1인칭" : "탐색"}
        </B>
      )}
      <B on={false} onClick={p.onReset}>처음부터</B>
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
