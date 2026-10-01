/**
 * infra/opsLink.ts — 내비 ↔ 관제 전송.  (DECISIONS §214-3 · §343)
 *
 * 문은 `openLink()` **하나**다. 그 뒤에 전송이 둘 있다.
 *
 *     설정에 중개자 주소가 있다   WebSocket    다른 기계 · 다른 망에서도 닿는다
 *     없다                        BroadcastChannel  같은 브라우저의 탭끼리만
 *
 * ★ **부르는 쪽은 어느 쪽인지 모른다.** 종전에 이 파일은 `BroadcastChannel`
 *   하나였고, 그래서 관제와 내비는 **같은 브라우저의 두 탭**일 때만 이어졌다 —
 *   시연은 되고 출동은 안 된다. 전송을 고르는 일을 부르는 쪽에 올리면
 *   `OpsApp.tsx` 와 `useOpsUplink.ts` 가 **각각** 그 판단을 들고, 둘이 어긋나는
 *   날 한쪽만 서버에 붙는다. 그래서 고르는 자리는 여기 하나다(§18-3).
 *
 * ★ 말의 모양은 이 파일이 **안 본다.** 정본은 `domain/opsProtocol.ts` 다.
 *   여기가 드는 것은 **어디로 가는가**뿐이다 — 서버도 같은 경계를 지킨다
 *   (`src/firelane/ops/server.py` 머리말).
 */
import { OPS_CHANNEL } from "../domain/opsProtocol";
import { OPS_URL } from "../config";

export interface Link {
  send(m: unknown): void;
  close(): void;
  readonly available: boolean;
}

/** 내가 어느 쪽인가. 중개자가 관제와 내비를 다른 문으로 받는다. */
export type Who = { kind: "ops" } | { kind: "unit"; unit: string };

/**
 * ★ 재접속 간격 **고정 1초**다. 지수 백오프를 안 쓴다 — 출동 중에 간격이
 *   2·4·8초로 늘면 그 시간 동안 관제가 차를 잃는다. 관제 화면은
 *   `HB_TTL_MS`(4초)로 「끊김」을 띄우므로, 재접속이 그보다 느려지면 멀쩡한
 *   차가 끊긴 것으로 보인다. 중개자는 한 대이고 **우리 것이다** — 폭주를
 *   걱정할 상대가 아니다.
 */
const RETRY_MS = 1000;

function path(who: Who): string {
  return who.kind === "ops" ? "/ops" : `/unit/${encodeURIComponent(who.unit)}`;
}

function openLinkWs(base: string, who: Who, onMsg: (data: unknown) => void): Link {
  let ws: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const connect = () => {
    if (closed) return;
    let sock: WebSocket;
    try {
      sock = new WebSocket(base.replace(/\/$/, "") + path(who));
    } catch {
      // ★ 주소가 틀리면 생성 자체가 던진다. 그때도 다시 시도한다 — 사람이
      //   `.env` 를 고치고 서버를 올리는 동안 화면을 새로 고치지 않아도 붙는다.
      timer = setTimeout(connect, RETRY_MS);
      return;
    }
    ws = sock;
    sock.onmessage = (e) => {
      // ★ **글자로 받아 여기서 푼다.** 서버는 뜻을 안 보고 글자를 옮기므로
      //   (`server.py`), 푸는 자리는 받는 쪽이다. 깨진 글자는 버린다 —
      //   `asOpsMsg` 가 모양을 보는데, 그 앞에서 던지면 연결이 죽는다.
      try { onMsg(JSON.parse(e.data as string)); } catch { /* 깨진 글자 — 버린다 */ }
    };
    sock.onclose = () => {
      if (closed) return;
      timer = setTimeout(connect, RETRY_MS);
    };
    sock.onerror = () => { try { sock.close(); } catch { /* 이미 닫혔다 */ } };
  };
  connect();

  return {
    send(m) {
      // ★ **못 보낸 것을 쌓아 두지 않는다.** `UnitState` 는 0.5초마다 다시
      //   오므로 쌓아 두면 붙는 순간 **지난 위치가 한꺼번에** 쏟아지고, 관제는
      //   그것을 최신으로 읽는다. 늦은 진실보다 없는 편이 낫다.
      //
      //   대가가 있다. `share` 처럼 **한 번만 보내는 말**은 끊긴 사이에 사라진다.
      //   지금은 `ACK_TIMEOUT_MS`(30초)가 지나 화면에 「응답 없음」으로 뜨는 것이
      //   전부다 — 재전송은 보낸 쪽이 들어야 하고, 그 일은 아직 안 했다.
      if (ws && ws.readyState === WebSocket.OPEN) {
        try { ws.send(JSON.stringify(m)); } catch { /* 닫히는 중 — 무시 */ }
      }
    },
    close() {
      closed = true;
      if (timer !== null) clearTimeout(timer);
      try { ws?.close(); } catch { /* 이미 닫혔다 */ }
    },
    get available() { return ws?.readyState === WebSocket.OPEN; },
  };
}

function openLinkChannel(onMsg: (data: unknown) => void): Link {
  // ★ BroadcastChannel 이 없는 환경(아주 옛 브라우저 · 일부 웹뷰)에서는 **조용히
  //   없는 것으로** 돈다. 그러면 관제가 없는 것과 같고, 공유는 흉내로 돌며
  //   「시연」 을 단다.
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

/**
 * 전송을 연다. **설정이 고른다 — 부르는 쪽이 아니다.**
 *
 * @param onMsg 받은 말. WebSocket 쪽은 JSON 을 풀어서 준다
 * @param who   내가 관제인가 차인가. 중개자의 문이 갈린다
 */
export function openLink(onMsg: (data: unknown) => void, who: Who): Link {
  return OPS_URL ? openLinkWs(OPS_URL, who, onMsg) : openLinkChannel(onMsg);
}

/** 탭마다 다른 짧은 id. 관제가 차를 가른다 */
export function newId(prefix: string): string {
  const r = Math.random().toString(36).slice(2, 7);
  return `${prefix}-${Date.now().toString(36).slice(-4)}${r}`;
}
