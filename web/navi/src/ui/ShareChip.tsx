/**
 * ui/ShareChip.tsx — 관제 공유 상태칩.  (와이어프레임 18 · 19 · 20 · 21)
 *
 * ★ 18·19·20 세 장이 2026-09-21 현재 **같은 그림**이라 표시 위치가 안
 *   정해졌다. 상단바 바로 아래 **가운데**에 둔다 — 처음엔 오른쪽에 뒀는데
 *   병목 시트(04)와 재탐색 카드(06)가 같은 자리를 써서 겹쳤다(검수 스크린샷).
 *   가운데는 주행 화면에서 아무도 안 쓰는 자리다. 지혜님 확인 사항.
 *
 * ★ `simulated` 이면 「시연」 표지를 단다. 관제 서버가 아직 없다.
 */
import type { CSSProperties } from "react";
import { C, S } from "./tokens";
import type { ShareInfo } from "../app/useShare";

const KIND: Record<string, string> = {
  bottleneck: "병목 구간", blocked: "통행 불가", arrival: "도착 보고",
};

export function ShareChip({ info, onRetry }: { info: ShareInfo; onRetry: () => void }) {
  if (info.state === "idle") return null;
  const what = KIND[info.kind ?? "bottleneck"];
  const t = info.state === "sending" ? { bg: "#eef4ff", ink: C.cta, text: `관제에 ${what} 공유 중…`, wf: "18" }
    : info.state === "awaiting" ? { bg: "#fff7e6", ink: C.warnInk, text: `관제 확인 대기 · ${what}`, wf: "19" }
    : info.state === "failed" ? { bg: "#fdecec", ink: C.danger, text: `공유 실패 · ${what}`, wf: "20" }
    : { bg: "#e9f9ef", ink: C.safeInk, text: `관제 확인 완료 ${info.ackedAt ?? ""} · ${what}`, wf: info.kind === "arrival" ? "23" : "21" };
  return (
    <div style={{ ...chip, background: t.bg, color: t.ink }} data-wf={t.wf}>
      <span style={{ fontWeight: 800 }}>{t.text}</span>
      {info.state === "failed" && (
        <button onClick={onRetry} style={retry}>다시 보내기</button>
      )}
      {info.simulated && <span style={sim} title="관제 서버가 아직 없다 — 전송을 흉내 낸다">시연</span>}
    </div>
  );
}

const chip: CSSProperties = {
  position: "absolute", zIndex: 6, top: S.guideBarH + 12, left: "50%",
  transform: "translateX(-50%)", whiteSpace: "nowrap",
  borderRadius: 12, padding: "9px 14px", display: "flex", alignItems: "center", gap: 10,
  fontSize: 14, boxShadow: "0 4px 14px rgba(0,0,0,.18)",
};
const retry: CSSProperties = {
  border: "none", background: C.danger, color: "#fff", borderRadius: 8,
  padding: "5px 10px", fontWeight: 800, cursor: "pointer",
};
const sim: CSSProperties = {
  background: "rgba(11,27,58,.75)", color: "#ffd166", borderRadius: 6,
  padding: "2px 6px", fontSize: 11, fontWeight: 800,
};
