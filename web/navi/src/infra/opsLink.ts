/**
 * infra/opsLink.ts — 내비 ↔ 관제 전송.  (DECISIONS §214-3)
 *
 * `BroadcastChannel` 하나다. **같은 브라우저 · 같은 출처의 탭끼리만** 닿는다 —
 * 서버가 아니다. 말의 모양은 `domain/opsProtocol.ts` 가 든다. 실제 관제 시스템과
 * 이을 때는 이 파일만 갈아 끼운다(웹소켓 · MQTT …).
 *
 * ★ BroadcastChannel 이 없는 환경(아주 옛 브라우저 · 일부 웹뷰)에서는 **조용히 없는
 *   것으로** 돈다. 그러면 관제가 없는 것과 같고, 공유는 흉내로 돌며 「시연」 을 단다.
 */
import { OPS_CHANNEL } from "../domain/opsProtocol";

export interface Link {
  send(m: unknown): void;
  close(): void;
  readonly available: boolean;
}

export function openLink(onMsg: (data: unknown) => void): Link {
  if (typeof BroadcastChannel === "undefined") {
    return { send() {}, close() {}, available: false };
  }
  const ch = new BroadcastChannel(OPS_CHANNEL);
  ch.onmessage = (e) => onMsg(e.data);
  return {
    send(m) { try { ch.postMessage(m); } catch { /* 닫힌 채널 — 무시 */ } },
    close() { ch.close(); },
    available: true,
  };
}

/** 탭마다 다른 짧은 id. 관제가 차를 가른다 */
export function newId(prefix: string): string {
  const r = Math.random().toString(36).slice(2, 7);
  return `${prefix}-${Date.now().toString(36).slice(-4)}${r}`;
}
