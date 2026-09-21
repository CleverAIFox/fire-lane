/**
 * ui/TopBar.tsx — 통일 상단바.  (와이어프레임 2026-09-21 · 03~23)
 *
 *   [회전·제목·부제] [마이크] [모드 배지] [현재 시간 · 예상 도착 · 사건 입력] [헤드셋]
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
  const title = s.title
    ?? (p.turnKind
      ? `${p.nextDistM != null && p.nextDistM > 15 ? `${fmtDist(p.nextDistM)} 앞 ` : ""}`
        + (TURN_WORD[p.turnKind] ?? "경로 안내")
      : "경로 안내");
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
            ? <TurnArrow kind={p.turnKind} size={56} />
            : <div style={{ width: 8 }} />}
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.1,
                        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {title}
          </div>
          {sub && (
            <div style={{ fontSize: 18, color: C.topBarSub, marginTop: 4, whiteSpace: "nowrap" }}>
              {sub}
            </div>
          )}
        </div>
      </div>

      {/* ── 마이크 ───────────────────────────────────────── */}
      <button style={roundBtn} onClick={p.onToggleVoice} aria-label="음성"
              title={p.voiceOn === false ? "음성 꺼짐" : "음성 안내"}>
        <MicIcon off={p.voiceOn === false} />
      </button>

      {/* ── 모드 배지 ────────────────────────────────────── */}
      <div style={{ ...badge, background: TONE_BG[s.tone] }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {tagIsButton ? (
            <button onClick={p.onSwitchRoute} style={{ ...tag, background: tagBg, cursor: "pointer" }}>
              ➤ {s.tag}
            </button>
          ) : s.tone === "white" ? (
            <span style={{ ...tagPlain, fontSize: 12 }}>{s.tag}</span>
          ) : (
            <span style={{ ...tag, background: tagBg }}>{s.tag}</span>
          )}
          <span style={chip}><Truck /> {p.vehicleKind}</span>
          {s.injected && <span style={injected} title="이 상태는 신호가 아니라 시연 막대가 넣었다">시연</span>}
        </div>
        {s.caution ? (
          <div style={{ fontSize: 13, fontWeight: 700, color: C.toneInk, marginTop: 6 }}>
            <span style={{ color: C.warn }}>⚠</span> {s.caution}
          </div>
        ) : (
          <div style={{ fontSize: 21, fontWeight: 800, color: C.toneInk, marginTop: 4,
                        textAlign: "center" }}>
            {s.label}
          </div>
        )}
      </div>

      {/* ── 시각 ─────────────────────────────────────────── */}
      <div style={timeBox}>
        <div style={{ fontSize: 22, fontWeight: 800, color: C.timeGreen, lineHeight: 1.1 }}>
          현재 시간 {p.nowText}
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 6, fontSize: 13, color: "#cfd8e6",
                      whiteSpace: "nowrap" }}>
          {s.eta !== "none" && (
            <span>
              {s.eta === "arrivedAt" ? "도착 시간 " : "예상 도착 "}
              <b style={{ fontSize: 17, color: "#fff" }}>{eta}</b>
            </span>
          )}
          {s.eta === "none" && s.blankRemain && !s.icon && (
            <span>예상 도착 <b style={{ fontSize: 17, color: "#fff" }}>—</b></span>
          )}
          {p.incidentText && <span><Doc /> 사건 입력 {p.incidentText}</span>}
        </div>
      </div>

      {/* ── 헤드셋 ───────────────────────────────────────── */}
      <button style={roundBtn} onClick={p.onHeadset} aria-label="무전·헤드셋">
        <HeadsetIcon />
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
const roundBtn: CSSProperties = {
  width: 52, height: 52, borderRadius: 999, border: "none", background: "#fff",
  display: "grid", placeItems: "center", cursor: "pointer", flex: "0 0 auto",
  boxShadow: "0 2px 8px rgba(0,0,0,.18)",
};
const badge: CSSProperties = {
  flex: "0 0 auto", minWidth: 250, borderRadius: 14, padding: "8px 12px",
  boxShadow: "0 3px 12px rgba(0,0,0,.2)",
};
const tag: CSSProperties = {
  border: "none", borderRadius: 7, padding: "3px 8px", fontSize: 12, fontWeight: 800,
  color: C.toneInk, fontFamily: F.family, whiteSpace: "nowrap",
};
const tagPlain: CSSProperties = {
  fontWeight: 800, color: C.toneInk, whiteSpace: "nowrap",
};
const chip: CSSProperties = {
  background: C.toneInk, color: "#fff", borderRadius: 7, padding: "3px 8px",
  fontSize: 12, fontWeight: 700, whiteSpace: "nowrap",
};
const injected: CSSProperties = {
  background: "rgba(11,27,58,.75)", color: "#ffd166", borderRadius: 6,
  padding: "2px 6px", fontSize: 11, fontWeight: 800,
};
const timeBox: CSSProperties = {
  flex: "0 0 auto", background: C.timeBox, borderRadius: 12, padding: "9px 16px",
  minWidth: 240,
};
const pBadge: CSSProperties = {
  width: 56, height: 56, borderRadius: 999, border: "3px solid #fff",
  display: "grid", placeItems: "center", fontSize: 30, fontWeight: 800,
};
