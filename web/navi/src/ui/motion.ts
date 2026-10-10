/**
 * ui/motion.ts — **강조는 색이 아니라 휘도와 움직임으로 한다.**
 *
 * ── 왜 생겼나 (2026-10-09 · DECISIONS §441) ────────────────────
 * 관제 화면은 **색 채널을 판정 넷이 이미 다 먹었다**(통행 가능 · 확인 필요 ·
 * 통행 불가 · 미측정). 「이 칸을 봐라」를 색으로 하면 다섯째 색이 생기고 판정이
 * 흐려진다. 남은 전주의 채널이 **휘도**와 **움직임** 둘이고, 교안이 그중
 * 휘도를 명시한다 —
 *
 *   『3 Theoretical issue 3 — Lightness, Brightness, Contrast and Constancy』
 *   p.25 Note 3 — 강조는 휘도 대비 조절로 한다. 중요치 않은 것의 대비를 낮추거나
 *   배경을 국소 조절해 중요한 곳의 대비를 올린다.
 *   같은 자료 p.15 Note 1 — 회색조로 2~4개 넘는 수치를 나타내지 않는다.
 *
 * ★ 그래서 이 파일에는 **색이 없다.** 투명도와 시간만 있다. 색을 쓰려면
 *   `web/config.js` 의 판정 4색을 가져와야 하고, 그 정본은 하나다(MASTER §10-2).
 *   `tools/uicheck.py` 가 이 파일에 색 리터럴이 없는지 센다 — 없으면 다음 판에
 *   누군가 여기 다섯째 색을 심는다.
 *
 * ── 쓰는 자리 · 안 쓰는 자리 ───────────────────────────────────
 * 쓴다    지금 주의가 필요한 **하나**. 경과가 중앙값을 넘었다 · 미확인 공유가
 *         쌓였다. 둘 다 사람이 손을 써야 바뀌는 상태다.
 * 안 쓴다 판정 4색 · 범례 · 지도 바탕 · 그냥 있는 수.
 *         **늘 움직이면 움직임이 신호가 아니라 배경이 된다.**
 *
 * ★ `prefers-reduced-motion` 을 지킨다. 지키는 방법이 「끈다」 하나뿐이면 안 된다 —
 *   끄면 강조가 사라지므로, 모션을 끈 자리에는 **휘도 대비**가 남는다(`EMPH`).
 *
 * IN    없음 (선언)
 * OUT   CSS 문자열 · 스타일 조각
 * 밖    **무엇이 급한가는 안 고른다** — 부르는 쪽이 판정한다.
 */

/** 맥박 한 주기(ms). 관제는 오래 보는 화면이라 느려야 한다 — 빠르면 피로가 된다. */
export const PULSE_MS = 2400;

/** 카메라 · 패널이 자리를 옮길 때. 자르지 않고 이징한다. */
export const EASE = "cubic-bezier(.22,.61,.36,1)";
export const MOVE_MS = 260;

/**
 * 맥박과 흐름의 키프레임. **투명도만 움직인다** — 색상·채도는 안 건드린다.
 *
 * ★ `flpulse` 는 0.55 → 1 이다. 0 까지 내리면 칸이 **사라졌다 나타나고**, 그러면
 *   읽는 사람이 값을 놓친다. 강조는 읽기를 돕는 것이지 가리는 것이 아니다.
 */
export const MOTION_CSS = `
@keyframes flpulse{0%{opacity:1}50%{opacity:.55}100%{opacity:1}}
@keyframes fldash{to{stroke-dashoffset:-24}}
@media (prefers-reduced-motion: reduce){
  .fl-pulse{animation:none}
}
`;

/**
 * 강조 조각. `on` 이 참일 때만 움직인다.
 *
 * ★ 모션을 끈 환경에서도 **남는 것**이 있어야 한다 — 그래서 테두리 휘도를
 *   같이 올린다(`EMPH`). 모션은 거드는 쪽이고 대비가 본체다(교안 p.25 Note 3).
 */
export function emphasis(on: boolean): { className?: string; style: Record<string, string> } {
  if (!on) return { style: {} };
  return {
    className: "fl-pulse",
    style: {
      animation: `flpulse ${PULSE_MS}ms ease-in-out infinite`,
      // ★ 색이 아니라 **밝기**다. 바탕의 같은 색을 밝게 들어 올린다.
      filter: "brightness(1.35)",
    },
  };
}

/** 자리 옮김. 자르지 않는다. */
export const MOVE: Record<string, string> = {
  transition: `transform ${MOVE_MS}ms ${EASE}, opacity ${MOVE_MS}ms ${EASE}`,
};
