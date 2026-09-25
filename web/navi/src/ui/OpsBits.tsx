/**
 * ui/OpsBits.tsx — 관제 화면의 되풀이되는 조각 넷.
 *
 *   Row     「이름 … 값」 한 줄. 값이 위태로우면 빨강(`warn`)
 *   Sec     제목 붙은 패널 하나
 *   Tile    상황판의 수 하나 (접수 · 출동 중 · 미확인 공유 · 실측 도착)
 *   Center  적재 중 · 치명적 오류를 가운데에
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `OpsApp.tsx` 가 744줄로 상한(600)을 넘었다. 이 넷은 **아무것도 모른다** —
 *   props 만 받아 그린다. 시험이 없는 파일을 쪼갤 때는 되돌리기 비용이 낮은 것부터
 *   떼는 것이 맞고, 상태를 안 지는 조각이 그 첫째다.
 *
 * ★ 순수 표시다. 관제 상태(`OpsState`) · 링크 · 그래프를 모른다.
 *
 * IN    props 뿐
 * OUT   조각 넷
 * 밖    무엇을 보일지 고르지 않는다. 고르는 것은 `OpsApp.tsx` 다.
 */
import { D, secBox, tile, shell } from "./opsTheme";

export function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "4px 0",
                  borderBottom: `1px solid ${D.line}` }}>
      <span style={{ color: D.sub }}>{k}</span>
      <b style={{ color: warn ? D.danger : D.ink, textAlign: "right" }}>{v}</b>
    </div>
  );
}

export function Sec({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={secBox}>
      <div style={{ fontSize: 11, fontWeight: 800, color: D.sub, letterSpacing: .6, marginBottom: 8 }}>{title}</div>
      {children}
    </section>
  );
}

export function Tile({ k, v, sub, tone }: { k: string; v: string; sub?: string; tone?: "ok" | "warn" | "danger" }) {
  const c = tone === "ok" ? D.ok : tone === "warn" ? D.warn : tone === "danger" ? D.danger : D.ink;
  return (
    <div style={tile}>
      <div style={{ fontSize: 10.5, color: D.sub, whiteSpace: "nowrap" }}>{k}</div>
      <div style={{ fontSize: 18, fontWeight: 800, color: c, lineHeight: 1.15 }}>
        {v}{sub && <span style={{ fontSize: 10.5, color: D.sub, fontWeight: 600 }}> {sub}</span>}
      </div>
    </div>
  );
}

export function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ ...shell, display: "grid", placeItems: "center" }}>{children}</div>;
}
