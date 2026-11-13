/**
 * src/index.ts — **관제 ↔ 내비 중개자 (Cloudflare Workers · Durable Object).**  (DECISIONS §755 · PLAN #176)
 *
 * `src/firelane/ops/server.py`(FastAPI)의 표면을 **그대로** 옮겼다: WebSocket `/ops` · `/unit/{id}` · `/cv/{cam}` · HTTP `GET /health`(토큰 없이) · `GET /units`(토큰).
 * 토큰은 질의 `t` — `accept` **전에** 본다(틀리면 1008). 방은 하나(`fire-lane`)다.
 *
 * ★ **메시지의 뜻을 안 본다**(§342). 규칙은 `relay.ts` 에 있고 그것도 글자만 안다.
 * ★ Hibernation API 를 쓴다 — idle 이면 지속시간이 안 붙는다. 대가: **메모리의 마지막 한 통이 DO 가 쫓겨나면 사라진다.** 내비는 0.5초마다 `state` 를 다시 보내므로
 *   차량 버킷은 0.5초 안에 스스로 복구된다. 영상(`cv`)은 주기 신호가 아니라 복구가 안 된다(알려진 한계 — DECISIONS §755).
 * ★ 인증 · 열린 선언 · 환경변수 이름은 파이썬 서버와 같다: `FIRE_LANE_OPS_TOKEN` · `FIRE_LANE_OPS_OPEN=1`. 추가: `ALLOWED_ORIGINS`(쉼표 · 비면 안 본다).
 */
import { Cache, authOk, wants, type Kind } from "./relay.ts";

interface Env {
  ROOM: { idFromName(n: string): unknown; get(id: unknown): { fetch(r: Request): Promise<Response> } };
  FIRE_LANE_OPS_TOKEN?: string;
  FIRE_LANE_OPS_OPEN?: string;
  ALLOWED_ORIGINS?: string;
}

const ROOM = "fire-lane";
const QS = "t";

function route(path: string): { kind: Kind; id: string } | null {
  if (path === "/ops") return { kind: "ops", id: "" };
  let m = /^\/unit\/([^/]+)$/.exec(path);
  if (m) return { kind: "unit", id: decodeURIComponent(m[1]) };
  m = /^\/cv\/([^/]+)$/.exec(path);
  if (m) return { kind: "cv", id: decodeURIComponent(m[1]) };
  return null;
}

const json = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } });

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const want = (env.FIRE_LANE_OPS_TOKEN ?? "").trim();
    const open = (env.FIRE_LANE_OPS_OPEN ?? "").trim() === "1";
    // ★ 토큰이 없으면 선다 — 조용히 열리지 않는다(`server.py` 와 같다). 열려면 `FIRE_LANE_OPS_OPEN=1` 을 **일부러** 준다.
    if (!want && !open) return json({ error: "FIRE_LANE_OPS_TOKEN 이 비어 있다 — 열린 채로 안 띄운다" }, 503);
    if (url.pathname === "/health") return json({ ok: true });                       // 살아 있는가는 비밀이 아니다
    if (!authOk(url.searchParams.get(QS), want, open)) {
      return req.headers.get("upgrade") === "websocket" ? new Response(null, { status: 401 }) : json({ detail: `${QS} 가 틀렸다` }, 401);
    }
    const stub = env.ROOM.get(env.ROOM.idFromName(ROOM));
    if (url.pathname === "/units") return stub.fetch(req);
    const r = route(url.pathname);
    if (!r) return json({ error: "없는 길" }, 404);
    if (req.headers.get("upgrade") !== "websocket") return json({ error: "WebSocket 이 필요하다" }, 426);
    const allow = (env.ALLOWED_ORIGINS ?? "").split(",").map((s) => s.trim()).filter(Boolean);
    const origin = req.headers.get("origin");
    if (allow.length && (!origin || !allow.includes(origin))) return new Response(null, { status: 403 });
    return stub.fetch(req);
  },
};

/** 방 하나 — 연결이 곧 명부다(저장소 없음). */
export class Room {
  private cache = new Cache();
  constructor(private state: any) {}

  private who(ws: any): { kind: Kind; id: string } {
    return ws.deserializeAttachment() as { kind: Kind; id: string };
  }

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    if (url.pathname === "/units") {
      const socks: any[] = this.state.getWebSockets();
      const ids = new Set<string>(); let ops = false;
      for (const s of socks) { const w = this.who(s); if (w.kind === "unit" && w.id) ids.add(w.id); if (w.kind === "ops") ops = true; }
      return json({ room: ROOM, ops, units: [...ids].sort() });
    }
    const r = route(url.pathname)!;
    const pair = new (globalThis as any).WebSocketPair();
    const [client, server] = [pair[0], pair[1]];
    this.state.acceptWebSocket(server);
    server.serializeAttachment({ kind: r.kind, id: r.id });
    // 새로 붙은 쪽에게 마지막 한 통들을 **글자 그대로** 재생한다
    for (const text of this.cache.replayFor(r.kind)) { try { server.send(text); } catch { /* 한 통이 죽어도 나머지는 받는다 */ } }
    return new Response(null, { status: 101, webSocket: client } as any);
  }

  async webSocketMessage(ws: any, msg: string | ArrayBuffer): Promise<void> {
    if (typeof msg !== "string") return;                                // 글자만 옮긴다(파이썬 서버의 `receive_text` 와 같다)
    const me = this.who(ws);
    this.cache.put(me.kind, me.id, msg);
    const to = wants(me.kind);
    for (const s of this.state.getWebSockets()) {
      if (s === ws) continue;                                           // 보낸 쪽에게 돌려주지 않는다
      if (!to.includes(this.who(s).kind)) continue;
      try { s.send(msg); } catch { /* 한 쪽이 죽어도 나머지는 받는다 */ }
    }
  }

  /** 같은 차가 재접속하면 옛 연결이 늦게 닫힌다 — 같은 `unit` 이 아직 붙어 있으면 버킷을 비우지 않는다(`roster.py` 와 같다). */
  private dropIfGone(ws: any): void {
    const me = this.who(ws);
    const still = this.state.getWebSockets().some((s: any) => s !== ws && this.who(s).kind === me.kind && this.who(s).id === me.id);
    if (!still) this.cache.drop(me.kind, me.id);
  }

  async webSocketClose(ws: any, code: number, reason: string): Promise<void> {
    this.dropIfGone(ws);
    try { ws.close(code, reason); } catch { /* 이미 닫혔다 */ }
  }

  async webSocketError(ws: any): Promise<void> {
    this.dropIfGone(ws);
  }
}
