/**
 * ui/Manual.tsx — **「읽는 법」 한 장.** 화면에서 걷어낸 설명이 전부 여기 산다.
 *
 * ── 왜 생겼나 (2026-10-09 · DECISIONS §441) ────────────────────
 * 관제·내비 화면이 패널마다 제 한계를 한 문장씩 달고 있었다 — 「폭은 도면 기반
 * 미검증 값이다」 · 「실시간 주정차 · 공사는 반영되지 않았습니다」 · 「회전반경은
 * 참고값 · 판정 안 함」 · 「줄을 누르면 그 색만 지도에서 뺀다」. 행이 그것을
 * **「개쓸데없는 TMI」** 라고 불렀고, 치우되 **사용 설명서로 옮기라**고 했다.
 *
 * ★ **지우는 것이 아니라 옮기는 것이다.** 한계를 지우면 화면이 「확정」처럼
 *   읽히고, 그것이 `Legend.tsx` 가 「이 한 줄을 지우지 마라」고 적어 둔 사유였다.
 *   그 줄도 여기로 왔다 — **사라지지 않았고, 한 번 눌러야 보일 뿐이다.**
 *
 * ★ 한 곳에만 산다. 종전에는 같은 말이 `SegCard` · `BottleneckPanel` ·
 *   `RouteCompare` 세 곳에 **조금씩 다른 문장**으로 있었다(족 2 — 정본이 둘).
 *   여기 `MANUAL` 하나가 정본이고 화면은 단추 하나만 둔다.
 *
 * IN    없음 (선언)
 * OUT   「읽는 법」 시트
 * 밖    **판정하지 않는다.** 무엇이 맞는 설명인가는 `MASTER` 가 든다.
 *       **색을 만들지 않는다** — 판정 4색의 정본은 `web/config.js` 다.
 */
import { useEffect } from "react";
import { D } from "./opsTheme";

/** 한 묶음. `title` 은 접힘 머리, `lines` 는 한 줄씩. */
export type ManualSection = { title: string; lines: string[] };

/**
 * 화면에서 걷어낸 문장 전부. **여기가 정본이다.**
 *
 * ★ 순서가 뜻이다 — 「반영하지 않는 것」이 맨 위다. 읽는 사람이 이 장을 여는
 *   까닭의 대부분이 「이 수를 믿어도 되나」이고, 그 답이 거기 있다.
 */
export const MANUAL: ManualSection[] = [
  {
    title: "반영하지 않는 것",
    lines: [
      "폭은 도면에서 잰 값이다. 현장 실측 전이고 전 구간 미검증이다.",
      "실시간 주정차 · 공사 · 이동 장애물은 반영하지 않는다.",
      "회전반경은 제원표 참고값이고 판정에 반영하지 않는다. 제원표에 그 차량이 없으면 등급으로 적는다.",
      "높이 통과 여부는 판정하지 않는다.",
      "일방통행은 방향을 대부분 모른다 — 모르는 구간은 양쪽 다 불리하게 계산한다.",
      "경로의 「안전」은 폭으로만 본 안전이다.",
    ],
  },
  {
    title: "판정 네 색",
    lines: [
      "통행 가능 — 요구폭을 넘는 유효폭이 확인된 구간.",
      "확인 필요 — 폭이 경계에 있거나 영상 판정(CV)이 필요한 구간.",
      "통행 불가 — 요구폭에 못 미치는 구간. 하한이다.",
      "미측정(회색) — CCTV 가 없거나 두 원천이 어긋나 확정하지 않은 구간. 「없다」가 아니라 「모른다」다.",
      "색은 도면 기반 1차 판정이다. 확정 판정이 아니다.",
    ],
  },
  {
    title: "수가 뜻하는 것",
    lines: [
      "여유폭 = 최소 유효폭 − 요구폭. 요구폭은 차량 전폭에 여유를 더한 값이다.",
      "단속 이력은 그 도로명 전체의 2022-01~2025-02 누계다. 지금 주차 상태가 아니다.",
      "단속 카메라 0 은 「도로명이 붙은 지점 중 없다」는 뜻이다.",
      "실측 중앙값은 같은 센터의 실제 출동→도착 시간이다. 내비 속도표와 다르고, 속도표 쪽이 미검증이다.",
      "출동 이력의 직선 km/h 는 센터~지점 직선거리 ÷ 시간이라 실제 주행 속도의 하한이다.",
      "영상 판정은 CCTV 에서 25m 안에서만 가능하다. 그 밖은 판정하지 않는다.",
      "폭 표본이 하나면 통과를 확정하지 않는다.",
      "동 경계는 표시용 가정값이다.",
    ],
  },
  {
    title: "조작",
    lines: [
      "지도에서 도로를 누르면 여유폭 · 사유 · 판정 근거 · 단속 이력이 열린다.",
      "범례의 줄을 누르면 그 색만 지도에서 숨는다.",
      "「출동 지령」은 새 탭에 내비를 열고 사건 · 차종 · 센터를 채운다. 위치와 공유는 같은 브라우저의 탭끼리 오간다 — 서버를 거치지 않는다.",
      "운전석에서는 목적지를 고르지 않는다. 지령이 온 내비는 검색과 지도 찍기가 닫힌다.",
      "「시연」 표시가 붙은 상태는 실제 신호가 아니라 시연 막대가 넣은 값이다.",
    ],
  },
];

/** 단추. 머리띠에 둔다 — 관제와 내비가 같은 것을 쓴다. */
export function ManualButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} title="이 화면을 읽는 법" style={btn}>읽는 법</button>
  );
}

/**
 * 시트. `open` 이 거짓이면 아무것도 안 그린다.
 *
 * ★ Esc 로 닫힌다 — 관제는 마우스를 지도에 두고 쓰는 화면이라 닫기 단추만
 *   두면 손이 한 번 더 간다.
 */
export function ManualSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div style={scrim} onClick={onClose} role="presentation">
      <div style={sheet} onClick={(e) => e.stopPropagation()} role="dialog" aria-label="읽는 법">
        <div style={head}>
          <b style={{ fontSize: 16 }}>읽는 법</b>
          <span style={{ fontSize: 12, color: D.sub }}>이 화면의 수가 무엇이고 무엇이 아닌가</span>
          <div style={{ flex: 1 }} />
          <button onClick={onClose} style={close}>닫기</button>
        </div>
        <div style={bodyBox}>
          {MANUAL.map((s) => (
            <section key={s.title} style={{ marginBottom: 16 }}>
              <div style={secHead}>{s.title}</div>
              <ul style={list}>
                {s.lines.map((t) => <li key={t} style={li}>{t}</li>)}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

const btn: React.CSSProperties = {
  background: "transparent", color: D.sub, border: `1px solid ${D.line}`,
  borderRadius: 6, padding: "3px 9px", fontSize: 12, cursor: "pointer",
};
const scrim: React.CSSProperties = {
  position: "fixed", inset: 0, background: "rgba(2,6,17,.66)",
  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 60,
};
const sheet: React.CSSProperties = {
  width: "min(720px, 92vw)", maxHeight: "82vh", overflowY: "auto",
  background: D.panel, color: D.ink, border: `1px solid ${D.line}`,
  borderRadius: 10, boxShadow: "0 24px 64px rgba(0,0,0,.5)",
};
const head: React.CSSProperties = {
  display: "flex", alignItems: "baseline", gap: 10,
  padding: "14px 18px", borderBottom: `1px solid ${D.line}`,
  position: "sticky", top: 0, background: D.panel,
};
const close: React.CSSProperties = { ...btn, color: D.ink };
const bodyBox: React.CSSProperties = { padding: "14px 18px 20px" };
const secHead: React.CSSProperties = {
  fontSize: 12, fontWeight: 800, color: D.accent, marginBottom: 6,
};
const list: React.CSSProperties = { margin: 0, paddingLeft: 18 };
const li: React.CSSProperties = { fontSize: 13, lineHeight: 1.7, color: D.ink };
