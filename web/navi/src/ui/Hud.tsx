/**
 * ui/Hud.tsx — 와이어프레임(지혜님, 2026-09-05) 주행 화면.
 *
 * ── 계층 ────────────────────────────────────────────────────────
 * 이 파일은 **화면만** 한다. 계산·상태·지도를 모르고 `HudData` 하나만
 * 받는다. 여기만 고쳐도 로직이 안 깨지고, 로직을 고쳐도 여기가 안 깨진다.
 *
 *   domain/     계산 (순수)          React·MapLibre·fetch 를 모른다
 *   infra/      바깥 세계            fetch · geolocation · 음성 · Mapbox
 *   app/        배선                 상태머신 · 파생값 · 음성 판단
 *   components/ 지도                 MapLibre
 *   ui/         화면                 ← 여기가 지혜님 자리
 *
 * ── 회전 안내는 우리가 만든다 ───────────────────────────────────
 * ★ 2026-09-05 까지 "데이터가 없어 못 한다" 고 적었다. **틀렸다.**
 *   `PLAN #1`(node_link 그래프 투입)이 ⏳ 인 것과 회전각을 못 내는 것은
 *   다른 문제다 — **회전각은 데이터가 아니라 계산이다.** 교차점에서
 *   들어온 방위각과 나가는 방위각의 차이고, `domain/turn.ts` 가 낸다.
 *
 * ★ 아직 못 하는 것은 **차로 안내**뿐이다. 차로수가
 *   `segments.geojson` 에 없다. `road_link` 확인 후 열 것.
 */
import type { CSSProperties, ReactNode } from "react";
import { C, F, S, fmtDist, fmtDur } from "./tokens";
import { TurnArrow } from "./TurnArrow";
import type { TurnKind } from "../domain/turn";

export interface HudData {
  vehicleKind: string;
  safeMode: boolean;
  offRoute: boolean;

  /** 회전 방향. `domain/turn.ts::classify` 가 정한다 */
  turnKind: TurnKind | null;
  /** "좌회전 동명로14번길" 같은 문구. **음성과 같은 문구다** */
  turnText: string | null;
  nextLabel: string | null;
  nextDistM: number | null;

  remainM: number;
  remainSec: number;
  etaText: string;

  currentLabel?: string;
  currentVerdictLabel?: string;
  currentVerdictColor?: string;
  currentWidthM: number | null;
  /** 상용 도로망이 아는 구간인가 (폭 >= 요구폭) */
  sdkCovered: boolean;

  /** ── 안전 모드 패널 ── */
  uncertainCount: number;
  uncertainM: number;
  minWidthM: number | null;
  requiredM: number;
  marginM: number | null;
  slowerSec: number | null;
  fastMinWidthM: number | null;
  fastLengthM: number | null;
}

interface Props extends HudData {
  onCompare?: () => void;
  /** 음성 켜짐. null 이면 이 브라우저가 음성을 못 낸다 */
  voiceOn?: boolean | null;
  onToggleVoice?: () => void;
}

export function Hud(d: Props) {
  return (
    <>
      {/* ── 상단 안내 바 ─────────────────────────────────────── */}
      <div style={guideBar}>
        {d.offRoute ? (
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <TurnArrow kind="uturn" />
            <div>
              <div style={{ fontSize: F.big, fontWeight: 800 }}>경로 이탈</div>
              <div style={{ fontSize: F.base, opacity: .85, marginTop: 2 }}>
                현재 위치 기준으로 재탐색이 필요하다
              </div>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {d.turnKind && <TurnArrow kind={d.turnKind} />}
            <div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                {d.nextDistM != null && d.nextDistM > 15 && (
                  <>
                    <span style={{ fontSize: F.huge, fontWeight: 800, lineHeight: 1 }}>
                      {fmtDist(d.nextDistM)}
                    </span>
                    <span style={{ fontSize: F.mid, opacity: .85 }}>앞</span>
                  </>
                )}
                <span style={{ fontSize: F.big, fontWeight: 800 }}>
                  {d.turnText ?? "경로 안내"}
                </span>
              </div>
              <div style={{ fontSize: F.base, opacity: .82, marginTop: 2 }}>
                {d.nextLabel ?? "안내 종료"}
              </div>
            </div>
          </div>
        )}

        {/* 음성 토글. 브라우저가 못 내면 아예 안 보인다 */}
        {d.voiceOn != null && (
          <button onClick={d.onToggleVoice} style={voiceBtn} aria-label="음성">
            {d.voiceOn ? "🔊" : "🔇"}
          </button>
        )}
      </div>

      {/* ── 상단 중앙 · 모드 배지 ────────────────────────────── */}
      {/* ★ 파란 바 위에 뜨므로 **항상 불투명 흰 카드**여야 한다.
          반투명 초록을 얹었더니 대비가 죽어 글씨가 안 읽혔다(2026-09-05). */}
      <div style={{ ...card, top: 12, left: "50%", transform: "translateX(-50%)",
                    border: `2px solid ${d.safeMode ? C.safe : C.panelLine}`,
                    textAlign: "center", padding: "10px 18px" }}>
        <div style={{ display: "inline-block", background: C.panelInk, color: "#fff",
                      borderRadius: 999, padding: "5px 14px",
                      fontSize: F.base, fontWeight: 700 }}>
          {d.vehicleKind}
        </div>
        <div style={{ marginTop: 6, fontSize: F.mid, fontWeight: 800,
                      color: d.safeMode ? C.safeInk : C.panelInk }}>
          {d.safeMode ? "안전 경로 주행 중" : "연결성 우선 주행 중"}
          <span style={{ fontSize: F.small, fontWeight: 600, marginLeft: 8,
                         color: C.panelSub }}>폭 기준 추천</span>
        </div>
      </div>

      {/* ── 우측 · 안전 모드 패널 ────────────────────────────── */}
      <div style={{ ...card, top: S.guideBarH + 14, right: 14, width: 292,
                    border: `1.5px solid ${d.uncertainCount ? C.warn : C.safe}` }}>
        <Chip warn={!!d.uncertainCount}>
          {d.safeMode ? "안전 모드" : "연결성 우선"}
        </Chip>

        <div style={{ fontSize: F.big, fontWeight: 800, margin: "10px 0 12px" }}>
          {d.uncertainCount
            ? `확인 필요 구간 ${d.uncertainCount}개` : "확인 필요 구간 없음"}
        </div>

        <Row k="확인 필요 구간"
             v={d.uncertainCount
               ? `${d.uncertainCount}개 · ${Math.round(d.uncertainM)}m` : "0개"} />
        <Row k="최소 유효 도로 폭"
             v={d.minWidthM != null ? `${d.minWidthM.toFixed(2)}m` : "—"} />
        <Row k="요구 통행 폭" v={`${d.requiredM.toFixed(1)}m`} />
        <Row k="계산상 최소 여유"
             v={d.marginM != null ? `${d.marginM.toFixed(2)}m` : "—"}
             warn={d.marginM != null && d.marginM < 0.5} />
        {d.slowerSec != null && (
          <Row k="빠른 경로보다"
               v={d.slowerSec <= 1 ? "같음" : `${fmtDur(d.slowerSec)} 느림`} />
        )}

        {/* ★ 이 두 줄이 이 프로젝트의 정직함이다. 지우지 마라 —
            폭은 도면 기반 미검증 값이고 실시간 장애물은 보지 않는다.
            회전은 판정하지 않는다(turn_radius_verified: false). */}
        <div style={{ marginTop: 12, paddingTop: 10,
                      borderTop: `1px solid ${C.panelLine}`,
                      fontSize: F.small, color: C.panelSub, lineHeight: 1.5 }}>
          실시간 주정차 · 공사 · 이동 장애물은 반영되지 않았습니다.<br />
          폭은 도면 기반 미검증 값이며, 회전 및 높이 통과 여부는
          판정하지 않습니다.
        </div>

        {d.onCompare && d.fastLengthM != null && (
          <button onClick={d.onCompare} style={linkBtn}>빠른 경로 비교 →</button>
        )}
      </div>

      {/* ── 좌하단 · 현재 구간 ───────────────────────────────── */}
      {d.currentLabel && (
        <div style={{ ...card, left: 14, bottom: 104, minWidth: 224 }}>
          <div style={{ fontSize: F.small, color: C.panelSub }}>{d.currentLabel}</div>
          <div style={{ fontSize: F.mid, fontWeight: 800, marginTop: 3,
                        color: d.currentVerdictColor ?? C.panelInk }}>
            {d.currentVerdictLabel}
            {d.currentWidthM != null && (
              <span style={{ fontSize: F.base, fontWeight: 600, marginLeft: 8,
                             color: C.panelSub }}>
                폭 {d.currentWidthM.toFixed(2)}m
              </span>
            )}
          </div>
          <div style={{ fontSize: F.tiny, color: C.panelSub, marginTop: 4 }}>
            {d.sdkCovered ? "상용 도로망 커버 구간" : "상용 도로망 미수록 구간"}
          </div>
        </div>
      )}

      {/* ── 좌하단 · 도착 요약 ───────────────────────────────── */}
      <div style={{ ...card, left: 14, bottom: 14, display: "flex",
                    alignItems: "center", gap: 18, padding: "12px 20px" }}>
        <div>
          <div style={{ fontSize: F.tiny, color: C.link, fontWeight: 700 }}>도착</div>
          <div style={{ fontSize: 26, fontWeight: 800, lineHeight: 1.1 }}>
            {d.etaText}
          </div>
        </div>
        <Divider />
        <div>
          <div style={{ fontSize: F.mid, fontWeight: 700 }}>{fmtDist(d.remainM)}</div>
          <div style={{ fontSize: F.tiny, color: C.panelSub }}>남음</div>
        </div>
        <Divider />
        <div style={{ fontSize: F.mid, fontWeight: 700 }}>{fmtDur(d.remainSec)}</div>
      </div>
    </>
  );
}

function Chip({ warn, children }: { warn: boolean; children: ReactNode }) {
  return (
    <span style={{ display: "inline-block", borderRadius: 999,
                   background: warn ? "rgba(245,158,11,.16)" : "rgba(34,197,94,.14)",
                   color: warn ? C.warnInk : C.safeInk,
                   padding: "4px 12px", fontSize: F.small, fontWeight: 700 }}>
      {children}
    </span>
  );
}
function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between",
                  fontSize: F.base, padding: "3px 0" }}>
      <span style={{ color: C.panelSub }}>{k}</span>
      <span style={{ fontWeight: 700, color: warn ? C.danger : C.panelInk }}>{v}</span>
    </div>
  );
}
const Divider = () => (
  <div style={{ width: 1, height: 34, background: C.panelLine }} />
);

const guideBar: CSSProperties = {
  position: "absolute", top: 0, left: 0, right: 0, height: S.guideBarH,
  background: C.guideBar, color: C.guideBarText, zIndex: 3,
  padding: "14px 24px", boxSizing: "border-box",
  display: "flex", alignItems: "center", justifyContent: "space-between",
};
const voiceBtn: CSSProperties = {
  background: "rgba(255,255,255,.14)", border: "1px solid rgba(255,255,255,.25)",
  borderRadius: 10, color: "#fff", fontSize: 18, cursor: "pointer",
  width: 44, height: 44, marginRight: 320,   // 중앙 배지를 피한다
};
const card: CSSProperties = {
  position: "absolute", zIndex: 4,
  background: C.panel, color: C.panelInk,
  border: `1px solid ${C.panelLine}`, borderRadius: S.radius,
  padding: `${S.pad - 2}px ${S.pad}px`,
  boxShadow: "0 8px 28px rgba(0,0,0,.32)",
};
const linkBtn: CSSProperties = {
  marginTop: 10, background: "none", border: "none", padding: 0,
  color: C.link, fontSize: F.base, fontWeight: 700, cursor: "pointer",
  fontFamily: F.family,
};
