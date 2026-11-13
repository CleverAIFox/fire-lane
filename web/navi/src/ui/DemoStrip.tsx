/**
 * ui/DemoStrip.tsx — **시연 중임을 늘 보인다 · 시연을 켜고 끄는 단 하나의 길.**  (DECISIONS §713 · ⓲C)
 *
 * ★ 시연이 켜져 있으면 화면 **테두리가 호박색**이고 「시연 중」 띠가 늘 뜬다(실제 위치가 아님은 이 색이 말한다) — 실주행과 헷갈리면 최악이다. 테두리는 눌림을 안 가로챈다.
 * ★ 켤 수 있는 때만 단추가 있다(`demoUi`) — **실주행 중에는 단추가 없다.** 안내 문구가 가리키는 이름은 `DEMO_START` 한 곳이다.
 *
 * IN    단계 · 측위 상태 · 시연 켜짐 · 배속 · 조작 함수
 * OUT   화면
 * 밖    시연을 돌리는 일(위치원)은 안 한다 — `app/usePositionSource`.
 */
import type { Phase } from "../domain/types";
import { DEMO_BADGE, DEMO_START, type GpsState } from "../domain/demo";
import { C, F, S } from "./tokens";

export type DemoButton = "on" | "start" | "end" | null;
export const DEMO_END = "끝내기";

/** 화면이 낼 것. `badge` 는 시연이 켜진 동안 늘 true. 단추 이름은 안내 문구(`domain/demo.ts`)와 같은 규칙에서 나온다 */
export function demoUi(phase: Phase, gps: GpsState, demo: boolean): { badge: boolean; button: DemoButton } {
  if (demo) return { badge: true, button: "end" };
  if (phase === "loading" || phase === "arrived") return { badge: false, button: null };
  if (phase === "guiding") return { badge: false, button: gps === "live" ? null : "start" };
  return { badge: false, button: "on" };
}

interface Props {
  phase: Phase;
  gps: GpsState;
  demo: boolean;
  simSpeed: number;
  setSimSpeed: (v: number) => void;
  /** 켜기 · 끄기. 실주행 중이면 켜기를 거절한다(false) */
  setDemo: (on: boolean) => boolean;
  /** 처음부터 — 끝내기가 부른다 */
  reset: () => void;
  /** 출발 센터 — 시연이 켜지면 카메라가 여기로 간다 */
  origin?: readonly [number, number];
  refocus: (at: [number, number]) => void;
}

export function DemoStrip(p: Props) {
  const ui = demoUi(p.phase, p.gps, p.demo);
  // ★ 시연 켜기 · 끝내기(§713). 끝내기 = 처음으로(시연 차가 서고 위치원이 비워진다). 켜지면 **출발 센터로 카메라가 간다** — 서울에서 열면 지도는 광주인데 위치는 서울이다.
  const act = () => {
    if (ui.button === "end") { p.setDemo(false); p.reset(); return; }
    if (!p.setDemo(true)) return;
    if (p.phase === "guiding" && p.origin) p.refocus([p.origin[0], p.origin[1]]);
  };
  return (
    <>
      {ui.badge && (
        <div data-testid="demo-frame" style={{
          position: "absolute", inset: 0, zIndex: 9, pointerEvents: "none",
          boxShadow: `inset 0 0 0 5px ${C.warn}`,
        }} />
      )}
      {(ui.badge || ui.button) && (
        <div data-testid="demo-strip" style={{
          position: "absolute", zIndex: 9,
          // ★ 주행 중에는 **왼쪽 위**(막대 아래)로 비킨다 — 앞을 보는 카메라에서 먼 목적지 P 와 그 알약 문구(「대체 접근 지점」)가 가운데 위쪽에 오는데 가운데 띠가 그것을 가렸다(DECISIONS §767)
          ...(p.phase === "guiding" ? { top: S.guideBarH + 8, left: 14 } : { bottom: 14, left: "50%", transform: "translateX(-50%)" }), display: "flex", gap: 6, alignItems: "center",
          background: ui.badge ? C.warn : C.dark, color: ui.badge ? "#1b1203" : C.darkInk,
          borderRadius: 12, padding: "7px 12px", fontSize: F.small, fontFamily: F.family, fontWeight: 800,
        }}>
          {ui.badge && <span>{DEMO_BADGE}</span>}
          {ui.badge && p.phase === "guiding" && (
            <>
              <B onClick={() => p.setSimSpeed(p.simSpeed > 0 ? 0 : 1)}>{p.simSpeed > 0 ? "■" : "▶"}</B>
              {[1, 4, 10].map((v) => <B key={v} on={p.simSpeed === v} onClick={() => p.setSimSpeed(v)}>×{v}</B>)}
            </>
          )}
          {ui.button && (
            <B onClick={act}>
              {ui.button === "end" ? DEMO_END : DEMO_START}
            </B>
          )}
        </div>
      )}
    </>
  );
}

function B({ onClick, on, children }: { onClick: () => void; on?: boolean; children: React.ReactNode }) {
  return (
    <button onClick={onClick} style={{
      background: on ? "rgba(0,0,0,.28)" : "rgba(0,0,0,.12)", border: "1px solid rgba(0,0,0,.35)", borderRadius: 8,
      color: "inherit", padding: "5px 10px", fontSize: F.small, fontWeight: 800, cursor: "pointer", fontFamily: F.family,
    }}>{children}</button>
  );
}
