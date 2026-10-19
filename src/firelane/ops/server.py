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

★ **인증은 공유 토큰 하나다**(2026-10-14 · DECISIONS §527). 종전에 이 자리는
  「인증이 없다 — 한 출동을 한 관제가 보는 시연이고 토큰을 쥘 사람이 없다」
  였다. **그 가정이 깨졌다** — `web/navi/src/config.ts` 가 앞을
  `wss://*.cloudfront.net` 으로 적는다. 올라간 순간 URL 만 알면 누구나
  `/ops` 로 **가짜 출동 지령**을, `/cv/{cam}` 으로 **영상이 잰 통과폭**을
  밀어 넣고 `/units` 로 지금 누가 어디 나가 있는지 읽는다. 폭을 공공데이터로
  재겠다는 프로젝트에서 그 수를 아무나 쓸 수 있으면 판정이 무의미해진다.

  발급·갱신·폐기 체계는 **여전히 안 만든다** — 쥘 사람이 없다는 말은 아직
  맞다. 대신 `.env` 의 `FIRE_LANE_OPS_TOKEN` 하나를 모든 문이 요구한다.
  약한 자물쇠지만 **열린 문과는 다르다.**

★ **토큰이 없으면 선다 — 조용히 열리지 않는다.** 없이 돌리려면
  `FIRE_LANE_OPS_OPEN=1` 을 **일부러** 줘야 한다(그러면 뜰 때 운다).
  느슨한 쪽을 **기본**이 아니라 **선언**으로 만든다 — 종전에는 머리말에만
  적혀 있었고 머리말은 아무도 안 막는다.

IN    WebSocket 세 종류 · HTTP 두 개(둘러보기용) · FIRE_LANE_OPS_TOKEN
OUT   옮긴 글자
밖    규약의 뜻 · 저장 · **토큰의 발급·갱신·폐기** (위 ★)
"""
from __future__ import annotations

import hmac
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from firelane.paths import env as _env

from .roster import ROOM, Peer, Roster

#: 문을 여는 말이 **담긴 환경변수의 이름**. 값이 아니다 — 값은 `.env` 에 있다.
#: ★ 이름에 `TOKEN` 을 쓰면 ruff S105 가 「하드코딩한 비밀」로 읽는다. 억제하지
#:   않고 이름을 고쳤다 — 억제는 검사를 끄는 것이고, 끌 이유가 없다.
ENV_AUTH = "FIRE_LANE_OPS_TOKEN"
#: 토큰 없이 돌리겠다는 **선언**. 기본값이 아니다.
ENV_OPEN = "FIRE_LANE_OPS_OPEN"
#: 토큰을 싣는 질의 이름. URL 에 실어야 브라우저 WebSocket 이 보낼 수 있다 —
#: 그 API 는 헤더를 못 붙인다.
QS = "t"


def _token() -> str:
    return _env(ENV_AUTH).strip()


def _ok(given: str | None) -> bool:
    """맞는 말인가. **길이로 새지 않게** 상수시간으로 댄다."""
    want = _token()
    if not want:
        return True                      # 선언하고 연 상태 — `create_app` 이 이미 울었다
    return bool(given) and hmac.compare_digest(given or "", want)


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
    # ★ 2026-10-14 (DECISIONS §527). **토큰이 없으면 여기서 선다.**
    #   느슨한 쪽을 기본이 아니라 **선언**으로 만든다 — 종전에는 머리말에만
    #   「인증이 없다」가 적혀 있었고, 머리말은 아무도 안 막는다.
    if not _token():
        if _env(ENV_OPEN).strip() != "1":
            raise RuntimeError(
                f"★ {ENV_AUTH} 가 비어 있다 — 중개자를 **열린 채로 안 띄운다**.\n"
                f"  .env 에 한 줄 넣어라:  {ENV_AUTH}=<아무도 모르는 긴 글자>\n"
                f"  정말 열어야 하면 선언해라:  {ENV_OPEN}=1  (뜰 때 운다)")
        print(f"★ {ENV_OPEN}=1 — 중개자가 **열려 있다.** 아무나 "
              "출동 지령과 통과폭을 밀어 넣을 수 있다.")

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

    # ★ `/health` 는 연다 — 「살아 있는가」는 비밀이 아니고, 앞단 상태검사가
    #   토큰을 못 들고 온다. `/units` 는 **지금 누가 어디 나가 있는지**라서 닫는다.
    @app.get("/units", summary="지금 누가 나가 있는가")
    def units(t: str | None = None) -> dict[str, object]:
        if not _ok(t):
            raise HTTPException(status_code=401, detail=f"{QS} 가 틀렸다")
        r: Roster = app.state.roster
        return {"room": ROOM, "ops": r.ops_present(), "units": r.units()}

    # ── 중개 ──────────────────────────────────────────────────
    async def _serve(ws: WebSocket, kind: str, unit: str) -> None:
        """한 연결의 생애. 받은 글자를 **상대편 전부**에게 옮긴다."""
        # ★ 인증이 들어갈 자리는 여기 하나다(머리말 ★). 2026-10-14 에 채웠다.
        #   **받기 전에 본다** — `accept()` 뒤에 보면 그 사이에 글자가 들어온다.
        if not _ok(ws.query_params.get(QS)):
            await ws.close(code=1008, reason="auth")     # 1008 = policy violation
            return
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
                    except Exception:  # noqa: S112, BLE001 — 아래 ★
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

    # ★ 2026-10-03 (DECISIONS §363). 영상이 재 준 통과폭이 들어오는 문.
    #   말의 정본은 `web/navi/src/domain/cv.ts` 이고 **여기는 뜻을 안 본다** —
    #   `/ops` · `/unit` 과 같은 규율이다(머리말 ★).
    @app.websocket("/cv/{cam}")
    async def ws_cv(ws: WebSocket, cam: str) -> None:
        await _serve(ws, "cv", cam)

    return app


# ★ 2026-10-14 (DECISIONS §527). **게으르게 준다.** 종전에는 여기서 바로
#   `create_app()` 을 불렀는데, 토큰 관문이 선 뒤로는 **수입만 해도 죽는다** —
#   `import firelane.ops.server` 하는 시험과 CLI 표면 검사가 같이 쓰러진다.
#   PEP 562 로 미루면 `uvicorn firelane.ops.server:app` 이 **띄울 때** 울고,
#   수입은 조용하다. 관문은 그대로고 우는 자리만 옳아진다.
def __getattr__(name: str):
    """`app` 을 **부를 때** 만든다. uvicorn 이 드는 이름이다."""
    if name == "app":
        return create_app()
    raise AttributeError(name)
