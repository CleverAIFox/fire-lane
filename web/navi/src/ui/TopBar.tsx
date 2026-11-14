/**
 * ui/TopBar.tsx — 통일 상단바.  (와이어프레임 2026-09-21 · 03~23)
 *
 *   [회전·제목·부제] [마이크] [모드 배지] [현재 시간 · 예상 도착 · 사건 접수] [헤드셋]
 *
 * ★ 2026-11-14 (PLAN 행 224 ④). **배치를 다시 짰다 — 글자는 전부 24px 이상이고 가로로 잘리는 말이 없다(1280 폭 · 상태 18개).**
 *   종전 배치는 배지 · 시각 칸이 각각 **두 줄**(위 줄에 14px 칩 둘 · 아래 줄에 15px 두 항목)이라 글자만 24px 로 키우면 가로가 터졌다
 *   (잘리는 상태 8 → 17 · DECISIONS §761). 지금은 두 칸 다 **세 줄 · 한 줄에 한 항목**이다 —
 *       배지   ① 태그(또는 경로 바꾸기 단추의 띠)  ② 상태 글씨(27px) 또는 주의(24px)  ③ 차종 칩 · 시연
 *       시각   ① 현재 시간(28px)  ② 예상 도착 / 도착 시간  ③ 사건 접수
 *   칸 폭이 준 만큼(362+340 → 약 332+246) 제목 칸이 넓어졌고(글자 폭 244 → 약 368), 상태 제목은 32px 한 줄 · 부제는 **두 줄까지 꺾인다**(말줄임 대신).
 *   막대 높이(124)는 그대로다 — 세 줄(32px × 3)이 안쪽 104px 에 들도록 안쪽 여백을 조였다.
 * ★ 경로 바꾸기 단추는 **배지 전체가 누르는 범위**다(약 332×104 — 종전 단추는 높이 29px 로 76 미만이던 마지막 터치 타깃이었다). 보이는 것은 맨 위 띠다.
 *
 * ★ **이 파일은 상태를 모른다.** `domain/status.ts` 의 표 한 줄(`StatusSpec`)과
 *   회전 안내 · 시각을 받아 그리기만 한다. 18장의 화면이 이 컴포넌트 하나다.
 *
 * ★ 09-05 판의 우측 「안전 모드 패널」 은 주행 화면에서 뺐다. 09-21 와이어
 *   프레임이 그 자리를 비웠고, 그 정보(최소 유효폭 · 요구폭 · 여유 · 측정
 *   신뢰도)는 병목 상세(04)로 옮겨 갔다. **정직함의 두 줄은 거기서 산다.**
 *
 * ★ 배지의 작은 태그(「빠른 경로 안내」)는 **단추다.** 안전 경로 주행 중에는
 *   빠른 경로로, 빠른 경로 주행 중에는 안전 경로로 바꾼다. 와이어프레임이
 *   03 과 03B 에서 태그 문구를 서로 뒤집어 둔 것이 그 뜻이다.
 */
import type { CSSProperties } from "react";
import { C, F, S, fmtDist } from "./tokens";
import { TurnArrow } from "./TurnArrow";
import { Doc, Truck } from "./icons";
import { TURN_WORD, type TurnKind } from "../domain/turn";
import { fillText, type StatusSpec, type Tone } from "../domain/status";

export interface TopBarProps {
  spec: StatusSpec;
  /** 부제 자리표 값 — `{last}` `{vehicle}` `{need}` `{road}` `{len}` */
  vars: Record<string, string>;
  vehicleKind: string;
  turnKind: TurnKind | null;
  nextDistM: number | null;
  roadName: string | null;
  nowText: string;
  etaText: string | null;
  incidentText: string | null;
  arrivedText?: string | null;
  /**
   * 이 상태가 **시연 막대가 넣은 것인가.**
   *
   * ★ 2026-09-24 (PLAN §13 W13-3). 종전에는 `spec.injected`(정적 표의 칸)를
   *   봤다. 그 칸이 붙은 것은 18갈래 중 다섯뿐인데 시연 막대는 **18갈래 전부**
   *   를 주입할 수 있다. `arrived` 를 주입하면 표지 없이 「도착」 이 떴다 —
   *   아직 달리는 중인데. 표가 아니라 **사실**을 본다.
   */
  injected?: boolean;
  voiceOn?: boolean | null;
  onToggleVoice?: () => void;
  /** 태그를 눌러 경로를 바꾼다. safe/fast 에서만 준다 */
  onSwitchRoute?: () => void;
  onHeadset?: () => void;
}

const TONE_BG: Record<Tone, string> = {
  green: C.toneGreen, yellow: C.toneYellow, cyan: C.toneCyan, white: C.toneWhite,
};

export function TopBar(p: TopBarProps) {
  const s = p.spec;
  // ★ 2026-11-12 (DECISIONS §704). 회전 안내는 **거리와 지시를 두 줄로 가른다** — 「127m 앞 좌회전」 을 한 줄에 놓으면 칸 256px 에 글자 308px 라
  //   「127m 앞 …」 으로 잘렸다(주행 화면에서 가장 중요한 줄이다 · 옛 TopBar 도 같았다). 거리가 위, 지시가 그 아래 — 지시는 **안 잘린다.**
  const turn = !s.title && p.turnKind
    ? { dist: p.nextDistM != null && p.nextDistM > 15 ? `${fmtDist(p.nextDistM)} 앞` : null, word: TURN_WORD[p.turnKind] ?? "경로 안내" }
    : null;
  const title = s.title ?? turn?.word ?? "경로 안내";
  const sub = s.title ? fillText(s.sub, p.vars) : (p.roadName ?? fillText(s.sub, p.vars));

  const eta = s.eta === "value" ? (p.etaText ?? "—")
    : s.eta === "computing" ? "계산 중"
    : s.eta === "checking" ? "확인 중"
    : s.eta === "arrivedAt" ? (p.arrivedText ?? p.nowText)
    : "—";

  const tagIsButton = !!p.onSwitchRoute && (s.tone === "green" || s.tone === "yellow")
    && !s.icon;
  const tagBg = s.tone === "green" ? C.toneYellow
    : s.tone === "yellow" ? C.toneGreen : "rgba(11,27,58,.10)";

  return (
    <div style={bar} data-status={s.wf.join(",")}>
      {/* ── 제목 ─────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: 18, minWidth: 0, flex: 1 }}>
        {s.icon === "P"
          ? <div style={pBadge}>P</div>
          : p.turnKind && !s.title
            ? <TurnArrow kind={p.turnKind} size={72} />
            : <div style={{ width: 8 }} />}
        <div style={{ minWidth: 0 }}>
          {turn ? (
            <>
              {turn.dist && <div data-turn="dist" style={turnLine}>{turn.dist}</div>}
              <div data-turn="word" style={turnLine}>{turn.word}</div>
            </>
          ) : (
            <div style={{ ...turnLine, ...cut, fontSize: 32 }}>
              {title}
            </div>
          )}
          {sub && (
            <div data-turn="road" style={turn ? { ...subLines, ...cut } : subLines}>
              {sub}
            </div>
          )}
        </div>
      </div>

      {/* ── 마이크 ───────────────────────────────────────── */}
      <button style={roundBtn} onClick={p.onToggleVoice} aria-label="음성"
              title={p.voiceOn === false ? "음성 꺼짐" : "음성 안내"}>
        <span style={disc}><MicIcon off={p.voiceOn === false} /></span>
      </button>

      {/* ── 모드 배지 — 세 줄: 태그 · 상태(또는 주의) · 차종 ─── */}
      <div style={{ ...badge, background: TONE_BG[s.tone] }}>
        {tagIsButton ? (
          // 누르는 범위는 배지 전체 · 보이는 것은 맨 위 띠(단추 글씨가 그 띠에 선다). 띠 밖은 비쳐서 아래 두 줄이 그대로 보인다.
          <button onClick={p.onSwitchRoute} style={{ ...tagBtn, background: `linear-gradient(${tagBg},${tagBg}) 0 0/100% 36px no-repeat` }}>
            ➤ {s.tag}
          </button>
        ) : null}
        {/* ★ 단추 문구는 단추가 있을 때만 — 없으면 상태 칩으로 그리지 않는다(§724 · B1). 그 줄은 비워 둔다(단추가 덮는 자리 · 세 줄 높이가 안 흔들린다). */}
        <div style={line}>
          {tagIsButton || s.switchTag ? null : <span style={s.tone === "white" ? undefined : { ...chip, background: tagBg }}>{s.tag}</span>}
        </div>
        <div style={s.caution ? line : { ...line, fontSize: 27, letterSpacing: -0.3 }}>
          {s.caution ? <><span style={{ color: C.warn }}>⚠</span> {s.caution}</> : s.label}
        </div>
        <div style={line}>
          <span style={{ ...chip, color: "#fff" }}><Truck size={22} /> {p.vehicleKind}</span>
          {p.injected && <span style={{ ...chip, color: "#ffd166", marginLeft: 8 }}>시연</span>}
        </div>
      </div>

      {/* ── 시각 — 세 줄: 현재 · 도착 · 접수 ─────────────────── */}
      <div style={timeBox}>
        <div style={{ ...line, fontSize: 28, color: C.timeGreen }}>
          현재 시간 {p.nowText}
        </div>
        {s.eta !== "none" && (
          <div style={timeLine}>
            {s.eta === "arrivedAt" ? "도착 시간 " : "예상 도착 "}
            <b style={{ color: "#fff" }}>{eta}</b>
          </div>
        )}
        {s.eta === "none" && s.blankRemain && !s.icon && (
          <div style={timeLine}>예상 도착 <b style={{ color: "#fff" }}>—</b></div>
        )}
        {p.incidentText && <div style={timeLine}><Doc size={20} /> 사건 접수 {p.incidentText}</div>}
      </div>

      {/* ── 헤드셋 ───────────────────────────────────────── */}
      <button style={roundBtn} onClick={p.onHeadset} aria-label="무전·헤드셋">
        <span style={disc}><HeadsetIcon /></span>
      </button>
    </div>
  );
}

function MicIcon({ off }: { off?: boolean }) {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden>
      <rect x="9" y="3" width="6" height="11" rx="3" fill={C.topBar} />
      <path d="M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6" stroke={C.topBar} strokeWidth="2"
            fill="none" strokeLinecap="round" />
      {off && <path d="M4 4 L20 20" stroke={C.danger} strokeWidth="2.4" strokeLinecap="round" />}
    </svg>
  );
}
function HeadsetIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden>
      <path d="M4 14v-2a8 8 0 0 1 16 0v2" stroke={C.topBar} strokeWidth="2.2" fill="none" />
      <rect x="3" y="13" width="4" height="7" rx="1.6" fill={C.topBar} />
      <rect x="17" y="13" width="4" height="7" rx="1.6" fill={C.topBar} />
    </svg>
  );
}

const bar: CSSProperties = {
  position: "absolute", top: 0, left: 0, right: 0, height: S.guideBarH, zIndex: 6,
  background: C.topBar, color: "#fff", boxSizing: "border-box",
  padding: "10px 22px", display: "flex", alignItems: "center", gap: 18,
  boxShadow: "0 4px 18px rgba(0,0,0,.25)",
};
/** 회전 안내 한 줄 — 거리 · 지시 모두 같은 크기이고 **말줄임이 없다**(지시는 어떤 폭에서도 끝까지 보인다). 40px 였던 것을 34px 로 낮춘 것은 두 줄 + 도로명이 막대 높이(104px) 안에 들게 하려는 것이다. */
const turnLine: CSSProperties = { fontSize: 34, fontWeight: 800, lineHeight: 1.1, letterSpacing: -0.5, whiteSpace: "nowrap" };
/** 누르는 범위는 76×76(Android Auto 터치 타깃 · DECISIONS §702 · §703) — 보이는 동그라미는 그대로 64 이고 그 안에 가운데 둔다. */
const roundBtn: CSSProperties = {
  width: 76, height: 76, border: "none", background: "transparent", padding: 0, margin: "0 -6px",
  display: "grid", placeItems: "center", cursor: "pointer", flex: "0 0 auto",
};
const disc: CSSProperties = {
  width: 64, height: 64, borderRadius: 999, background: "#fff",
  display: "grid", placeItems: "center", boxShadow: "0 2px 8px rgba(0,0,0,.18)",
};
/** 한 줄로 두고 넘치면 말줄임 — 상태 제목과 회전 안내의 도로명. */
const cut: CSSProperties = { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
/** 부제 — 상태 부제는 **두 줄까지 꺾는다**(말줄임이 아니다 · 낱말 가운데서 안 끊는다). 회전 안내의 도로명은 여기에 `cut` 을 얹어 한 줄이다. */
const subLines: CSSProperties = {
  fontSize: 24, color: C.topBarSub, marginTop: 3, lineHeight: 1.1, wordBreak: "keep-all", maxHeight: 53, overflow: "hidden",
};
/** 배지 · 시각 칸의 한 줄(32px). 세 줄 96 + 위아래 4×2 = 104 = 막대 안쪽 높이(124 − 20). 안 꺾는다 — 길면 칸이 넓어지고 제목 칸이 그만큼 준다. */
const line: CSSProperties = { height: 32, font: `800 24px/32px ${F.family}`, color: C.toneInk, whiteSpace: "nowrap" };
const badge: CSSProperties = {
  position: "relative", flex: "0 0 auto", minWidth: 312, borderRadius: 16, padding: "4px 10px",
  boxShadow: "0 3px 12px rgba(0,0,0,.2)",
};
/** 경로 바꾸기 단추 — 배지 전체를 덮는다(터치 76 이상). 글씨는 맨 위 줄에 서고 그 줄만 띠(`background`)로 칠한다. */
const tagBtn: CSSProperties = {
  ...line, position: "absolute", inset: 0, height: "100%", width: "100%", boxSizing: "border-box", border: "none", borderRadius: 16, padding: "4px 20px", cursor: "pointer",
  display: "flex", alignItems: "flex-start",
};
/** 칩 — 태그 · 차종 · 시연. 바탕은 쓰는 자리가 덮어쓴다. */
const chip: CSSProperties = { background: C.toneInk, borderRadius: 8, padding: "0 10px" };
const timeBox: CSSProperties = {
  flex: "0 0 auto", background: C.timeBox, borderRadius: 14, padding: "4px 12px", minWidth: 222,
};
const timeLine: CSSProperties = { ...line, fontWeight: 400, color: "#cfd8e6" };
const pBadge: CSSProperties = {
  width: 68, height: 68, borderRadius: 999, border: "3px solid #fff",
  display: "grid", placeItems: "center", fontSize: 36, fontWeight: 800,
};
