"""
중개자 — 관제(1) ↔ 내비(N).  (DECISIONS §342)

관제와 내비는 선택이 아니라 **무조건 연동**이다. 관제가 상위 위계이고, 내비는
각각의 에이전트다. 그 둘을 잇는 프로세스가 이 묶음이다.

    roster.py    지금 누가 나가 있는가 — **순수**
    server.py    WebSocket 두 문 · HTTP 두 개 — FastAPI
    __main__.py  띄우는 자리

★ **말의 뜻은 여기 없다.** 규약의 정본은 `web/navi/src/domain/opsProtocol.ts`
  하나다. 이 묶음이 드는 것은 「누구에게 가는가」뿐이다.
"""
