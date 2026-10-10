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
import { D, LAYER, secBox, tile, shell } from "./opsTheme";
import type { Tier } from "./opsTheme";
import { emphasis } from "./motion";

export function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "4px 0",
                  borderBottom: `1px solid ${D.line}` }}>
      <span style={{ color: D.sub }}>{k}</span>
      <b style={{ color: warn ? D.danger : D.ink, textAlign: "right" }}>{v}</b>
    </div>
  );
}

export function Sec({ title, children, tier = "pick" }: {
  title: string; children: React.ReactNode; tier?: Tier;
}) {
  // ★ 2026-10-09 (§445 · #143). 층은 **휘도**다 — 사유는 `opsTheme.LAYER` 가 든다.
  return (
    <section style={{ ...secBox, ...LAYER[tier] }}>
      <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: .6, marginBottom: 8,
                    color: tier === "idle" ? "#55657e" : tier === "act" ? D.ink : D.sub }}>{title}</div>
      {children}
    </section>
  );
}

/**
 * 상황판 한 칸.
 *
 * ★ 2026-10-09 (§441). `urgent` 를 받는다 — **색이 아니라 휘도**로 강조한다.
 *   `tone` 은 이미 색을 고르고 있고 그 색은 판정 넷과 같은 채널이다. 「급하다」를
 *   색으로 또 말하면 다섯째 색이 생긴다. 사유는 `ui/motion.ts` 머리말이 든다.
 */
export function Tile({ k, v, sub, tone, urgent }: {
  k: string; v: string; sub?: string; tone?: "ok" | "warn" | "danger"; urgent?: boolean;
}) {
  const c = tone === "ok" ? D.ok : tone === "warn" ? D.warn : tone === "danger" ? D.danger : D.ink;
  const em = emphasis(!!urgent);
  // ★ 2026-10-09 (§445 · #143). 색이 안 붙은 칸은 **쉬는 칸**이다 — 평시에
  //   셋이 다 0 이고 같은 밝기로 자리를 먹었다. 휘도를 내려 무게를 뺀다.
  const tier: Tier = tone ? "pick" : "idle";
  return (
    <div style={{ ...tile, ...LAYER[tier] }}>
      <div style={{ fontSize: 10.5, color: tier === "idle" ? "#55657e" : D.sub, whiteSpace: "nowrap" }}>{k}</div>
      <div className={em.className}
           style={{ fontSize: 18, fontWeight: 800, color: c, lineHeight: 1.15, ...em.style }}>
        {v}{sub && <span style={{ fontSize: 10.5, color: D.sub, fontWeight: 600 }}> {sub}</span>}
      </div>
    </div>
  );
}

export function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ ...shell, display: "grid", placeItems: "center" }}>{children}</div>;
}
