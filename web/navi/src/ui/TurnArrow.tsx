/**
 * ui/TurnArrow.tsx — 회전 방향 아이콘.
 *
 * ★ 회전각이 아니라 **어휘**를 받는다. 각도를 그림으로 바꾸는 판단은
 *   `domain/turn.ts::classify` 가 이미 했고, 여기는 그리기만 한다.
 */
import type { TurnKind } from "../domain/turn";

const PATH: Record<TurnKind, string> = {
  start: "M20 32 L20 12 M12 20 L20 12 L28 20",
  straight: "M20 32 L20 10 M12 18 L20 10 L28 18",
  arrive: "M20 10 L20 26 M12 18 L20 26 L28 18",
  uturn: "M14 32 L14 18 A6 6 0 0 1 26 18 L26 26 M20 22 L26 28 L32 22",
  slight_left: "M22 32 L22 20 L14 12 M14 20 L14 12 L22 12",
  left: "M26 32 L26 18 L12 18 M18 11 L11 18 L18 25",
  sharp_left: "M26 32 L26 20 L14 26 M12 16 L14 26 L24 24",
  slight_right: "M18 32 L18 20 L26 12 M26 20 L26 12 L18 12",
  right: "M14 32 L14 18 L28 18 M22 11 L29 18 L22 25",
  sharp_right: "M14 32 L14 20 L26 26 M28 16 L26 26 L16 24",
};

export function TurnArrow({ kind, size = 46, color = "#fff" }: {
  kind: TurnKind; size?: number; color?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <path d={PATH[kind] ?? PATH.straight} fill="none" stroke={color}
            strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
