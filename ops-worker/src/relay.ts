/**
 * src/relay.ts — **중개자의 순수 규칙.** 소켓 · Cloudflare 를 모른다.  (DECISIONS §755 · `src/firelane/ops/roster.py` 와 같은 규칙)
 *
 * ★ 규칙은 둘이다: ① 누가 누구에게 보내는가(`targets`) ② **마지막 한 통을 기억한다**(`Cache`).
 * ★ 메시지의 **뜻을 안 본다**(§342). 받은 글자를 그대로 옮기고 그대로 들고 그대로 재생한다 — 파싱 · 필드 읽기 · 해석이 없다.
 *   버킷 이름은 본문이 아니라 **전송**(경로)에서 온다: `unit:{id}` · `cv:{cam}`. 「상태를 든다」 가 아니라 「마지막 한 통을 기억한다」 다.
 * ★ `ops` 가 보낸 것(`hb` · `ack`)은 **기억하지 않는다** — 옛 `hb` 를 재생하면 이미 없는 관제가 있는 것으로 읽힌다.
 */
export type Kind = "ops" | "unit" | "cv";

/** 이 메시지를 받을 종류. `roster.py::targets` 와 같다 — 보낸 쪽에게는 돌려주지 않는다(호출부가 거른다). */
export function wants(sender: Kind): readonly Kind[] {
  if (sender === "ops") return ["unit"];
  if (sender === "cv") return ["ops", "unit"];
  return ["ops"];
}

/** 기억하는 종류 — 관제의 심장박동 · 확인은 지금의 신호이지 상태가 아니다. */
export const CACHED: readonly Kind[] = ["unit", "cv"];
export const MAX_BUCKETS = 256;
export const MAX_BYTES = 64 * 1024;

export class Cache {
  private m = new Map<string, { kind: Kind; text: string }>();

  static key(kind: Kind, id: string): string {
    return `${kind}:${id}`;
  }

  /** 마지막 한 통을 **글자 그대로** 둔다. 기억 안 하는 종류 · 너무 큰 글 · 버킷 상한이면 안 둔다(옮기기는 그대로 한다). */
  put(kind: Kind, id: string, text: string): boolean {
    if (!CACHED.includes(kind) || text.length > MAX_BYTES) return false;
    const k = Cache.key(kind, id);
    if (!this.m.has(k) && this.m.size >= MAX_BUCKETS) return false;
    this.m.set(k, { kind, text });
    return true;
  }

  /** 차량이 떠나면 그 버킷을 비운다 — 연결이 곧 명부다(`roster.py`). 영상은 측정값이라 연결과 무관하게 남긴다. */
  drop(kind: Kind, id: string): void {
    if (kind === "unit") this.m.delete(Cache.key(kind, id));
  }

  /** 새로 붙은 쪽이 받았어야 할 마지막 글자들(들어온 순서). 새로 붙은 쪽이 받을 종류가 보낸 쪽의 `wants` 에 들 때만이다. */
  replayFor(newcomer: Kind): string[] {
    const out: string[] = [];
    for (const { kind, text } of this.m.values()) if (wants(kind).includes(newcomer)) out.push(text);
    return out;
  }

  get size(): number {
    return this.m.size;
  }
}

/** 상수시간 비교 — 길이로 새지 않게(`server.py::_ok`). 토큰이 비면 「열려 있다」 선언이 있을 때만 통과한다. */
export function authOk(given: string | null, want: string, open: boolean): boolean {
  if (!want) return open;
  const g = given ?? "";
  let diff = g.length ^ want.length;                 // 길이가 달라도 같은 횟수를 돈다
  for (let i = 0; i < want.length; i++) diff |= (g.charCodeAt(i) || 0) ^ want.charCodeAt(i);
  return given !== null && diff === 0;
}
