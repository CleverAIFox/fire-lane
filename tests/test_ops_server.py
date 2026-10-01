"""중개자 ② 중개 — **진짜 서버**를 띄워서 잰다.  (DECISIONS §342-3)

★ `fastapi.testclient.TestClient` 로는 **못 잰다.** 그것은 WebSocket 세션마다
  제 이벤트 루프를 세우므로, 연결 A 의 핸들러가 연결 B 의 소켓으로 보내는
  순간 다른 루프에 일을 맡기고 **영원히 기다린다.** 2026-10-01 에 그렇게
  멈췄다. 그런데 이 중개자가 하는 일이 바로 그 「A 에서 B 로」다 —
  **도구가 못 재는 것을 못 재는 채로 두면 재지 않은 것이다.**

★ 그래서 포트 0 으로 실물 uvicorn 을 올린다. 포트를 OS 가 고르므로 다른
  시험과 안 부딪히고, `started` 를 기다렸다가 쓰므로 경주가 없다.

★ **건너뛸 수 있는 유일한 자리다.** 그 허용 범위는
  `test_ops_roster.py::test_a_skip_is_only_allowed_on_a_prerelease_interpreter`
  가 묶는다 — 정식판 해석기에서 `fastapi` 가 안 들어오면 그쪽이 빨개진다.

IN    src/firelane/ops/**.py · docker-compose.yml
OUT   없음 (검사)
밖    **지연을 안 본다.** `HB_MS` 1.5초 · `UnitState` 0.5초가 지켜지는지는
      화면의 타이머가 정하고, 중개자는 받은 즉시 옮긴다.
      **배포도 안 본다.** EC2 · CloudFront · Compose 가 실제로 서는지는 이
      시험이 닿는 곳이 아니다(`Dockerfile.api` · MASTER §12-8).
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ★ `pytest.importorskip` 을 **안 쓴다.** 그것은 `ImportError` 만 잡는데,
#   3.14.0rc2 에서 `import fastapi` 는 **`AssertionError`** 로 죽는다
#   (`pydantic` 이 `typing.ForwardRef` 를 되짚는 자리). 그래서 `importorskip`
#   으로 두면 건너뛰는 대신 **수집 단계가 깨진다** — 2026-10-01 에 그렇게
#   깨졌고, 그 전에는 `fastapi` 가 안 깔려 있어서 우연히 `ImportError` 였다.
#   어떤 꼴로 죽어도 같은 답을 내야 한다.
try:
    import fastapi  # noqa: F401 — 적재되는가만 본다
except Exception as _e:                          # noqa: BLE001 — 위 ★
    # ★ 사유는 **정책 어휘로** 적는다(`tests/skip_policy.py` · DECISIONS §175).
    #   분류 접두사가 f-string 의 **고정 부분**에 와야 판별식이 그것을 본다.
    #   없는 것은 「도구」다 — 해석기가 이 패키지를 못 적재한다.
    pytest.skip(
        "환경skip(도구) — 시험판 해석기에서 fastapi 가 안 들어온다"
        f" ({sys.version.split()[0]} · {type(_e).__name__})."
        " test_ops_roster.py 의 안전핀이 이 건너뛰기를 묶는다(§342-5)",
        allow_module_level=True,
    )

# ★ 아래 넷은 **위 `importorskip` 뒤여야 한다.** 올리면 건너뛰기 판단 전에
#   적재되고, 적재가 실패하는 해석기에서 모듈이 수집 단계에 죽는다 — 건너뛰기가
#   무의미해진다. 그래서 `E402` 를 끈다.
import uvicorn  # noqa: E402 — importorskip 뒤라 올릴 수 없다
from websockets.sync.client import connect  # noqa: E402 — importorskip 뒤라 올릴 수 없다

from firelane.ops.roster import ROOM, Peer, Roster  # noqa: E402 — importorskip 뒤라 올릴 수 없다
from firelane.ops.server import create_app  # noqa: E402 — importorskip 뒤라 올릴 수 없다

#: 한 왕복을 기다리는 시한. 넘으면 **빨강이다** — 매달린 시험은 사람이 죽이고,
#: 죽이면 무엇이 틀렸는지 영영 모른다(§284-5 가 같은 자리에서 배운 것).
WAIT_S = 5.0

@pytest.fixture
def base() -> Iterator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(create_app(), log_level="warning"))
    t = threading.Thread(target=srv.run, kwargs={"sockets": [sock]}, daemon=True)
    t.start()
    deadline = time.monotonic() + 20
    while not srv.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert srv.started, "중개자가 20초 안에 안 떴다"
    try:
        yield f"127.0.0.1:{port}"
    finally:
        srv.should_exit = True
        t.join(timeout=20)


def _get(base: str, path: str) -> dict:
    url = f"http://{base}{path}"
    with urllib.request.urlopen(url, timeout=WAIT_S) as r:  # noqa: S310 — 주소를 이 파일이 짠다. `base` 는 위 fixture 의 `127.0.0.1:<OS 가 고른 포트>` 이고 바깥 값이 아니다
        return json.loads(r.read())


def _ws(base: str, path: str):
    return connect(f"ws://{base}{path}", open_timeout=WAIT_S)


def _settle(base: str, want: object, path: str = "/units") -> dict:
    """명부가 `want` 가 될 때까지 기다린다.

    ★ 붙고 끊기는 일은 **서버 쪽에서 비동기로** 끝난다. 바로 물으면 아직
      안 끝난 상태를 보고, 그 시험은 기계가 바쁠 때만 빨개진다 — 그런 빨강은
      아무도 안 읽는다. 기다리고, 안 되면 **시한으로 빨개진다.**
    """
    deadline = time.monotonic() + WAIT_S
    got: dict = {}
    while time.monotonic() < deadline:
        got = _get(base, path)
        if got == want:
            return got
        time.sleep(0.02)
    assert got == want, f"{WAIT_S}초 안에 {want} 가 안 됐다 — 실제 {got}"
    return got


def test_health_says_it_is_alive(base: str) -> None:
    assert _get(base, "/health") == {"ok": True}


def test_units_is_empty_before_anyone_connects(base: str) -> None:
    assert _get(base, "/units") == {"room": ROOM, "ops": False, "units": []}


def test_swagger_stands(base: str) -> None:
    """★ 「현관을 뭘로 할지」의 답이다 — 스웨거가 서면 WebSocket 클라이언트 없이
    서버가 살아 있는지 사람이 눈으로 본다."""
    spec = _get(base, "/openapi.json")
    assert set(spec["paths"]) >= {"/health", "/units"}


def test_a_connected_unit_appears_in_units(base: str) -> None:
    with _ws(base, "/unit/navi-7"):
        _settle(base, {"room": ROOM, "ops": False, "units": ["navi-7"]})


def test_a_unit_disappears_when_it_disconnects(base: str) -> None:
    """★ 안 지우면 `/units` 가 이미 돌아간 차를 나가 있다고 말한다."""
    with _ws(base, "/unit/navi-7"):
        _settle(base, {"room": ROOM, "ops": False, "units": ["navi-7"]})
    _settle(base, {"room": ROOM, "ops": False, "units": []})


def test_ops_presence_is_seen_and_lost(base: str) -> None:
    with _ws(base, "/ops"):
        _settle(base, {"room": ROOM, "ops": True, "units": []})
    _settle(base, {"room": ROOM, "ops": False, "units": []})


def test_a_unit_message_reaches_ops(base: str) -> None:
    with _ws(base, "/ops") as ops, _ws(base, "/unit/navi-7") as u:
        _settle(base, {"room": ROOM, "ops": True, "units": ["navi-7"]})
        u.send('{"t":"state","unit":"navi-7"}')
        assert ops.recv(timeout=WAIT_S) == '{"t":"state","unit":"navi-7"}'


def test_ops_reaches_every_unit(base: str) -> None:
    with _ws(base, "/ops") as ops, _ws(base, "/unit/a") as a, _ws(base, "/unit/b") as b:
        _settle(base, {"room": ROOM, "ops": True, "units": ["a", "b"]})
        ops.send("명령")
        assert a.recv(timeout=WAIT_S) == "명령"
        assert b.recv(timeout=WAIT_S) == "명령"


def test_the_broker_does_not_read_the_message(base: str) -> None:
    """★ **규약의 집은 하나다.** 서버가 뜻을 안 보므로 규약 밖의 글자도 그대로
    지나간다. 이 시험이 초록인 동안 `opsProtocol.ts` 를 고치면서 서버를 같이
    고칠 일이 없다."""
    with _ws(base, "/ops") as ops, _ws(base, "/unit/a") as a:
        _settle(base, {"room": ROOM, "ops": True, "units": ["a"]})
        a.send("이것은 JSON 도 아니다")
        assert ops.recv(timeout=WAIT_S) == "이것은 JSON 도 아니다"


def test_a_unit_does_not_reach_another_unit(base: str) -> None:
    """★ 차끼리는 안 닿는다. 지휘가 관제를 안 거치면 3인칭 시점이 깨진다."""
    import websockets.exceptions

    with _ws(base, "/ops") as ops, _ws(base, "/unit/a") as a, _ws(base, "/unit/b") as b:
        _settle(base, {"room": ROOM, "ops": True, "units": ["a", "b"]})
        a.send("a 가 보낸 것")
        assert ops.recv(timeout=WAIT_S) == "a 가 보낸 것"
        with pytest.raises(TimeoutError):
            b.recv(timeout=0.5)
        assert websockets.exceptions is not None


def test_a_unit_sending_with_no_ops_does_not_kill_the_connection(base: str) -> None:
    """★ 관제가 안 켜져 있어도 내비는 계속 돈다. 여기서 터지면 관제를 켜기
    전에 출발한 차가 전부 끊긴다."""
    with _ws(base, "/unit/a") as a:
        _settle(base, {"room": ROOM, "ops": False, "units": ["a"]})
        for _ in range(5):
            a.send("관제가 없는 동안")
        _settle(base, {"room": ROOM, "ops": False, "units": ["a"]})


def test_ops_arriving_late_still_receives(base: str) -> None:
    """★ 관제는 **늦게 켜진다.** 차가 먼저 출발하는 것이 정상이다."""
    with _ws(base, "/unit/a") as a:
        a.send("관제 없을 때")
        with _ws(base, "/ops") as ops:
            _settle(base, {"room": ROOM, "ops": True, "units": ["a"]})
            a.send("관제 켜진 뒤")
            assert ops.recv(timeout=WAIT_S) == "관제 켜진 뒤"


def test_the_same_car_reconnecting_is_still_one_row(base: str) -> None:
    with _ws(base, "/unit/navi-7"), _ws(base, "/unit/navi-7"):
        _settle(base, {"room": ROOM, "ops": False, "units": ["navi-7"]})


def test_one_unit_dropping_does_not_stop_the_others(base: str) -> None:
    """★ `server.py` 의 `except Exception: continue` 가 드는 물음이다. 한 대가
    죽어도 나머지는 받는다 — 안 그러면 끊긴 내비 하나가 출동 전체를 멈춘다."""
    with _ws(base, "/ops") as ops, _ws(base, "/unit/b") as b:
        a = _ws(base, "/unit/a")
        _settle(base, {"room": ROOM, "ops": True, "units": ["a", "b"]})
        a.close()
        _settle(base, {"room": ROOM, "ops": True, "units": ["b"]})
        ops.send("남은 차에게")
        assert b.recv(timeout=WAIT_S) == "남은 차에게"


def test_each_app_has_its_own_roster(base: str) -> None:
    """★ 명부가 모듈 전역이면 시험 둘이 같은 명부를 쓰고, 먼저 돈 시험이 남긴
    연결이 다음 시험의 답을 바꾼다. `create_app()` 이 그래서 있다.

    ★ 띄워 둔 서버에 차가 붙어 있는 동안 **새로 만든 앱은 비어 있다** — 그것이
      전역이 아니라는 증거다. 명부 객체가 다른지도 같이 본다.
    """
    with _ws(base, "/unit/navi-7"):
        _settle(base, {"room": ROOM, "ops": False, "units": ["navi-7"]})
        fresh = create_app()
        assert fresh.state.roster.units() == []
        r = Roster()
        r.join(Peer(cid="x", kind="unit", unit="navi-9"))
        assert fresh.state.roster.units() == [], "명부가 공유된다 — create_app 이 무의미하다"
