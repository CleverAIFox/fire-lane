/**
 * ui/icons.tsx — 작은 아이콘. **이모지를 쓰지 않는다.**
 *
 * ★ 2026-09-21. 이모지(🔥 🚒)는 글꼴이 그린다. 시연 태블릿·차량 단말에
 *   컬러 이모지 글꼴이 없으면 네모 칸으로 나온다 — 검수용 크로미움에서
 *   실제로 그랬다. SVG 는 어디서나 같게 그려진다.
 */
export function Flame({ size = 20, color = "#ef2d2d" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <path d="M12 2 C14 7 19 9 19 15 A7 7 0 0 1 5 15 C5 11 8 9.5 9 6 C10 9 11.5 10 12 2 Z" fill={color} />
      <path d="M12 12 C13 14.5 15 15 15 17 A3 3 0 0 1 9 17 C9 15.5 10.5 14.5 12 12 Z" fill="#fff" opacity=".85" />
    </svg>
  );
}
export function Truck({ size = 14, color = "#fff" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden style={{ verticalAlign: "-2px" }}>
      <path d="M2 7h11v9H2zM13 10h4l3 3v3h-7z" fill={color} />
      <circle cx="6" cy="17.5" r="2" fill={color} /><circle cx="17" cy="17.5" r="2" fill={color} />
    </svg>
  );
}
export function Doc({ size = 12, color = "#cfd8e6" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden style={{ verticalAlign: "-1px" }}>
      <path d="M6 2h8l4 4v16H6z" fill={color} /><path d="M9 11h6M9 15h6" stroke="#0b1220" strokeWidth="1.6" />
    </svg>
  );
}
