"""
server.py — **관제와 내비 사이를 잇는 중개자.**

── 왜 이 파일이 생겼나 (DECISIONS §342) ────────────────────────
관제와 내비는 선택이 아니라 **무조건 연동**이다. 관제가 상위 위계이고 — 출동을
3인칭으로 보며 지휘한다 — 내비는 각각의 에이전트다. 카카오택시에서 배차 화면과
기사 화면이 갈라져 있으면 그것은 두 앱이 아니라 **깨진 한 앱**이다.

종전에 그 연결은 `infra/opsLink.ts` 의 `BroadcastChannel` 하나였다. 그것은
**같은 브라우저의 탭끼리만** 닿는다. 시연은 되고 출동은 안 된다.

★ **그래서 서버가 필요하다 — 호스팅이 아니다.** 호스팅은 이미 있다
  (`pages.yml` 이 관제·내비를 GitHub Pages 로 배포한다). 없는 것은 **런타임**,
  두 화면 사이에 서서 말을 옮기는 프로세스 하나다.

★ **폴링이 아니다.** `opsProtocol.ts` 가 `UnitState` 를 0.5초마다 보내고
  하트비트를 1.5초로 정한다(`HB_MS`). 그 규약 위에서 폴링은 요구를 못 맞춘다 —
  WebSocket 이다.

── 이 파일이 **안 하는 것** ────────────────────────────────────
★ **메시지의 뜻을 안 본다.** 받은 글자를 그대로 옮긴다. `UnitState` 가 무엇인지,
  `ack` 가 무엇인지 모른다 — 그 정본은 `web/navi/src/domain/opsProtocol.ts`
  하나다. 서버가 그것을 알면 **말의 집이 둘이 되고**, 규약이 바뀔 때마다 화면과
  서버를 같이 고쳐야 한다. 그렇게 어긋난 적이 이 저장소에 이미 있다(§18-3).

  대가가 있다. 깨진 메시지도 그대로 지나간다. 그 검사는 받는 쪽이
  `opsProtocol` 로 하고, 서버는 **누구에게 가는가**만 든다.

★ **저장소가 없다.** 출동 이력도 지난 위치도 안 남긴다. `roster.py` 머리말이
  그 이유를 적는다 — 연결이 곧 명부다.

★ **인증이 없다.** 지금 이것은 한 출동을 한 관제가 보는 시연이고, 앞은
  `*.cloudfront.net` 뒤에 있다. 토큰을 지금 넣으면 발급·갱신·폐기가 같이
  생기는데 **그것을 쥘 사람이 없다.** 넣을 자리는 `_accept()` 한 곳이다 —
  그래서 지금 비어 있는 것이 보인다.

IN    WebSocket 두 종류 · HTTP 두 개(둘러보기용)
OUT   옮긴 글자
밖    규약의 뜻 · 저장 · 인증 (위 ★)
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .roster import ROOM, Peer, Roster


def create_app() -> FastAPI:
    """앱을 **만들어 돌려준다.**

    ★ 모듈 전역에 두지 않는다. 명부가 가변 상태인데 전역이면 시험 둘이 같은
      명부를 쓰고, 먼저 돈 시험이 남긴 연결이 다음 시험의 답을 바꾼다. 그 꼴은
      초록·빨강이 **순서에 따라** 갈리는 시험이고, 그런 시험은 고쳐도 왜
      고쳐졌는지 모른다.
    """
    app = FastAPI(
        title="Fire-Lane 중개자",
        description=(
            "관제(1) ↔ 내비(N) 사이를 잇는다. 메시지의 뜻은 안 본다 — "
            "규약의 정본은 `web/navi/src/domain/opsProtocol.ts` 다."
        ),
        version="0.1.0",
    )
    app.state.roster = Roster()
    app.state.socks = {}      # cid -> WebSocket. 명부를 순수하게 두려고 여기 있다

    # ── 둘러보기용 HTTP ───────────────────────────────────────
    # ★ 이 둘은 **사람이 보는 문**이다. `/docs` 가 스웨거를 띄우고, 거기서
    #   서버가 살아 있는지와 지금 누가 붙어 있는지를 WebSocket 클라이언트
    #   없이 확인할 수 있다. 그게 없으면 "안 되는데요" 가 서버 문제인지
    #   화면 문제인지 가릴 길이 없다.

    @app.get("/health", summary="살아 있는가")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/units", summary="지금 누가 나가 있는가")
    def units() -> dict[str, object]:
        r: Roster = app.state.roster
        return {"room": ROOM, "ops": r.ops_present(), "units": r.units()}

    # ── 중개 ──────────────────────────────────────────────────
    async def _serve(ws: WebSocket, kind: str, unit: str) -> None:
        """한 연결의 생애. 받은 글자를 **상대편 전부**에게 옮긴다."""
        # ★ 인증이 들어갈 자리는 여기 하나다(머리말 ★). 지금은 비어 있다.
        await ws.accept()
        cid = uuid.uuid4().hex
        me = Peer(cid=cid, kind=kind, unit=unit)
        r: Roster = app.state.roster
        socks: dict[str, WebSocket] = app.state.socks
        r.join(me)
        socks[cid] = ws
        try:
            while True:
                text = await ws.receive_text()
                for other in r.targets(me):
                    peer = socks.get(other)
                    if peer is None:
                        continue
                    try:
                        await peer.send_text(text)
                    except Exception:
                        # ★ **한 쪽이 죽어도 나머지는 받는다.** 여기서 터뜨리면
                        #   끊긴 내비 하나가 출동 전체의 통신을 멈춘다. 끊긴
                        #   연결은 제 `finally` 에서 명부를 떠난다.
                        continue
        except WebSocketDisconnect:
            pass
        finally:
            # ★ **어떻게 끝나도 명부를 떠난다.** 안 떠나면 `/units` 가 이미
            #   돌아간 차를 나가 있다고 말하고, 그 거짓이 관제 화면까지 간다.
            r.leave(cid)
            socks.pop(cid, None)

    @app.websocket("/ops")
    async def ws_ops(ws: WebSocket) -> None:
        await _serve(ws, "ops", "")

    @app.websocket("/unit/{uid}")
    async def ws_unit(ws: WebSocket, uid: str) -> None:
        await _serve(ws, "unit", uid)

    return app


#: uvicorn 이 드는 이름. `firelane.ops.server:app`
app = create_app()
