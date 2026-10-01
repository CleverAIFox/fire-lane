"""중개자 ① 명부 · ③ 경계 — **서버 없이 도는 것들.**  (DECISIONS §342)

── 왜 생겼나 ───────────────────────────────────────────────────
관제와 내비를 잇는 프로세스가 생겼다. 그것이 틀리면 **출동 전체가 틀린다** —
관제 화면이 이미 돌아간 차를 나가 있다고 말하거나, 지휘가 한 대에만 닿는다.

★ 「경계」 묶음이 이 파일의 본체다. 중개자는 **말의 뜻을 안 보기로** 했다
  (`server.py` 머리말). 그 약속은 코드를 읽어야 확인되는 종류이고, 읽어도 다음
  사람이 `if msg["t"] == "state"` 한 줄을 넣으면 아무도 안 운다. 규약의 집이
  둘이 되는 순간이 그 한 줄이다. 그래서 **글자로 잰다.**

★ **이 파일은 `fastapi` 를 안 쓴다.** 그래서 어떤 해석기에서도 돈다 — 실물
  왕복은 `tests/test_ops_server.py` 가 들고, 그쪽만 시험판 해석기에서
  건너뛸 수 있다(§342-5).

IN    src/firelane/ops/**.py · pyproject.toml
OUT   없음 (검사)
밖    **왕복을 안 본다.** 글자가 실제로 건너가는지는 `test_ops_server.py` 가
      실물 uvicorn 으로 든다.
      **규약이 맞는지 안 본다.** `UnitState` 의 칸이 옳은지는
      `web/navi/test/domain.test.ts` 가 든다 — 중개자는 뜻을 모르므로 여기서
      뜻을 재면 **이 파일이 규약의 두 번째 집**이 된다.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from firelane.ops.roster import ROOM, Peer, Roster

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "src" / "firelane" / "ops"

assert ROOM, "방 이름이 비면 `/units` 가 빈 방을 말한다"


# ══ ① 명부 — 순수 ═══════════════════════════════════════════════
def _ops(cid: str = "o1") -> Peer:
    return Peer(cid=cid, kind="ops", unit="")


def _unit(cid: str, unit: str) -> Peer:
    return Peer(cid=cid, kind="unit", unit=unit)


def test_empty_roster_has_no_ops_and_no_units() -> None:
    r = Roster()
    assert r.units() == []
    assert r.ops_present() is False


def test_a_unit_shows_up_and_leaves() -> None:
    r = Roster()
    r.join(_unit("c1", "navi-7"))
    assert r.units() == ["navi-7"]
    r.leave("c1")
    assert r.units() == []


def test_leaving_twice_is_not_an_error() -> None:
    """★ 끊김은 두 번 올 수 있다 — `WebSocketDisconnect` 와 `finally` 가 겹친다."""
    r = Roster()
    r.join(_unit("c1", "navi-7"))
    r.leave("c1")
    r.leave("c1")
    assert r.units() == []


def test_the_same_car_connecting_twice_is_one_car() -> None:
    """★ 재접속이다. 연결은 둘, 차는 하나 — 관제 화면에 같은 차가 둘로 보이면
    대원 수를 잘못 센다."""
    r = Roster()
    r.join(_unit("c1", "navi-7"))
    r.join(_unit("c2", "navi-7"))
    assert r.units() == ["navi-7"]


def test_a_unit_without_an_id_is_not_counted() -> None:
    """★ 빈 문자열은 차가 아니다. 세면 이름 없는 차가 명부에 선다."""
    r = Roster()
    r.join(_unit("c1", ""))
    assert r.units() == []


def test_ops_presence_is_seen_and_lost() -> None:
    r = Roster()
    assert r.ops_present() is False
    r.join(_ops())
    assert r.ops_present() is True
    r.leave("o1")
    assert r.ops_present() is False


def test_ops_sends_to_every_unit_and_not_to_itself() -> None:
    """★ 보낸 쪽에 안 돌려준다 — `BroadcastChannel` 이 그렇게 동작하고, 어댑터를
    갈아 끼워도 말이 같아야 한다. 안 그러면 화면이 제 상태를 두 번 적용한다."""
    r = Roster()
    r.join(_ops("o1"))
    r.join(_unit("c1", "a"))
    r.join(_unit("c2", "b"))
    assert r.targets(_ops("o1")) == ["c1", "c2"]


def test_a_unit_reaches_only_ops() -> None:
    """★ 차끼리는 안 닿는다. 지휘가 관제를 안 거치면 3인칭 시점이 깨진다."""
    r = Roster()
    r.join(_ops("o1"))
    r.join(_unit("c1", "a"))
    r.join(_unit("c2", "b"))
    assert r.targets(_unit("c1", "a")) == ["o1"]


def test_two_ops_screens_both_receive() -> None:
    """★ 관제를 둘 띄우는 일은 있다(상황실 큰 화면 + 노트북). 둘 다 받는다."""
    r = Roster()
    r.join(_ops("o1"))
    r.join(_ops("o2"))
    r.join(_unit("c1", "a"))
    assert sorted(r.targets(_unit("c1", "a"))) == ["o1", "o2"]


def test_a_unit_with_no_ops_has_nowhere_to_send() -> None:
    """★ 관제가 안 켜져 있으면 받을 쪽이 없다. 터지지 않고 빈 목록이다."""
    r = Roster()
    r.join(_unit("c1", "a"))
    assert r.targets(_unit("c1", "a")) == []


# ══ ③ 경계  — 중개자가 **규약을 모르는가** ═══════════════════════
PROTOCOL_WORDS = ("state", "hb", "ack", "share", "routeRev", "UnitState", "FeedItem")


def test_the_broker_source_does_not_name_the_protocol() -> None:
    """★ 이 파일의 본체다. 중개자가 `msg["t"] == "state"` 를 알게 되는 순간
    규약의 집이 둘이 되고, `opsProtocol.ts` 를 고칠 때마다 서버도 고쳐야 한다.
    그 한 줄은 리뷰로 안 걸린다 — 그래서 **글자로 잰다.**

    ★ 머리말과 주석은 뺀다. 거기서는 규약을 **가리키는 것이 옳다**.
    """
    bad = []
    for f in sorted(OPS.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        src = re.sub(r'"""(?:.|\n)*?"""', "", src)              # 머리말 · docstring
        live = "\n".join(x.split("#", 1)[0] for x in src.splitlines())
        for w in PROTOCOL_WORDS:
            pat = "[\"'](" + re.escape(w) + ")[\"']"
            for m in re.finditer(pat, live):
                bad.append(f"{f.name}:{live[:m.start()].count(chr(10)) + 1}  '{m.group(1)}'")
    assert not bad, (
        "중개자가 규약의 말을 들고 있다 — 말의 집은 "
        "`web/navi/src/domain/opsProtocol.ts` 하나다.\n  " + "\n  ".join(bad))


def test_the_roster_knows_no_framework_and_no_clock() -> None:
    """명부가 소켓도 시계도 모르는가. 알면 시험이 서버 없이는 안 돈다.

    ★ `tests/test_layering.py` 의 `DOMAIN` 에 `ops/roster.py` 를 넣었고 그쪽이
      **`firelane` 안쪽** 축을 든다(`paths`·`pipeline`… 을 모르는가). 여기가
      드는 것은 **바깥쪽** 축이다 — 프레임워크와 시계. 두 축이 겹치지
      않으므로 두 자리가 맞다. 겹치기 시작하면 하나를 지운다.
    """
    live = (OPS / "roster.py").read_text(encoding="utf-8")
    live = re.sub(r'"""(?:.|\n)*?"""', "", live)
    for banned in ("fastapi", "WebSocket", "asyncio", "time.", "datetime", "import os"):
        assert banned not in live, f"roster.py 가 {banned} 를 들고 있다 — 순수를 깬다"


def test_the_port_is_written_once() -> None:
    """★ 포트가 `__main__.py` · compose 두 곳에 손으로 적히면 어긋난다.
    선언은 `__main__.DEFAULT_PORT` 하나이고 compose 가 그것을 따른다.

    ★ **모듈을 import 하지 않는다.** `__main__.py` 는 `uvicorn` 을 import 하고,
      그러면 이 파일이 시험판 해석기에서 같이 죽는다 — 이 파일은 어떤
      해석기에서도 돌아야 한다. 글자로 읽는다.
    """
    src = (OPS / "__main__.py").read_text(encoding="utf-8")
    m = re.search(r"^DEFAULT_PORT = (\d+)$", src, re.M)
    assert m, "`__main__.py` 에서 `DEFAULT_PORT` 선언을 못 찾았다"
    port = m.group(1)
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert re.search(rf'"{port}:{port}"', compose), \
        f"docker-compose.yml 의 ops 포트 매핑이 {port} 와 다르다"
    assert re.search(rf'FIRE_LANE_OPS_PORT: "{port}"', compose), \
        f"docker-compose.yml 의 FIRE_LANE_OPS_PORT 가 {port} 와 다르다"


def test_the_broker_is_a_core_dependency_not_an_extra() -> None:
    """중개자의 의존성이 **코어**인가. (DECISIONS §341 · §342-5)

    ★ extras 로 두면 `verify.sh` 가 안 깐다(extras 를 안 깐다) — 그러면
      `test_ops_server.py` 가 Fox 의 기계에서 **조용히 건너뛰고**, 안 도는
      시험은 없는 시험이다. 건너뛰기의 **다른 길을 막는 자리**다.
    """
    pp = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def names(reqs: list[str]) -> set[str]:
        return {re.match(r"[A-Za-z0-9._-]+", d).group(0).lower() for d in reqs}

    core = names(pp["project"]["dependencies"])
    for need in ("fastapi", "uvicorn"):
        assert need in core, f"{need} 가 코어 의존성이 아니다 — 시험이 조용히 건너뛴다"
    assert "websockets" in names(pp["dependency-groups"]["dev"]), (
        "websockets 가 dev 에 없다 — 왕복 시험이 전이 의존성에 매달린다")
    # ★ 안 쓰는 것이 되돌아오지 않는가. `[vision]` 은 지웠다(§341-2).
    extras = pp["project"].get("optional-dependencies", {})
    assert "vision" not in extras, "`[vision]` extras 가 되돌아왔다 — CV 는 끝났다(§341-2)"


def test_a_skip_is_only_allowed_on_a_prerelease_interpreter() -> None:
    """★ **안전핀.** `test_ops_server.py` 가 건너뛰는 유일한 허용 사유는
    「해석기가 정식판이 아니다」 하나다.

    ── 왜 이 핀이 필요한가 (DECISIONS §342-5) ─────────────────
    2026-10-01, 중개자를 만든 샌드박스의 해석기가 **3.14.0rc2** 였고 거기서
    `import fastapi` 가 `AssertionError` 로 죽는다 — `pydantic` 이
    `typing.ForwardRef` 를 되짚는 자리이고, 같은 판 조합이 3.13.13 에서는
    멀쩡하다. 즉 **패키지가 아니라 rc 해석기**다.

    그래서 그 파일을 `importorskip` 으로 뒀다. 그런데 「적재 안 되면
    건너뛴다」만 두면 **정식판에서 진짜로 깨진 날에도 조용히 초록**이다 —
    그것이 1족(무음 통과)이고 이 저장소가 가장 많이 당한 꼴이다.

    이 시험이 그 구멍을 막는다. 정식판 해석기에서 `fastapi` 가 안 들어오면
    **빨강**이다.
    """
    try:
        import fastapi  # noqa: F401 — 적재되는가만 본다. 쓰지 않는 것이 요점이다
    except Exception as e:                       # pragma: no cover — 기계에 따라 갈린다
        assert sys.version_info.releaselevel != "final", (
            "정식판 해석기에서 `fastapi` 가 적재되지 않는다 — 중개자가 **안 뜬다.**\n"
            f"  {type(e).__name__}: {e}\n"
            f"  해석기 {sys.version.split()[0]}\n"
            "  건너뛰기는 시험판 해석기에서만 허용된다(DECISIONS §342-5).")


def test_the_server_file_actually_holds_the_round_trip() -> None:
    """★ **빈 그물 물음**(MASTER §17-0 ③). 위 안전핀이 지키는 그 파일이
    실제로 왕복을 재는가 — 비어 있으면 핀은 아무것도 안 지킨다."""
    srv = (ROOT / "tests" / "test_ops_server.py").read_text(encoding="utf-8")
    assert srv.count("def test_") >= 12, "test_ops_server.py 의 판별식이 너무 적다"
    for need in ("connect(", "uvicorn.Server", "recv("):
        assert need in srv, f"test_ops_server.py 가 `{need}` 를 안 쓴다 — 실물 왕복이 아니다"
