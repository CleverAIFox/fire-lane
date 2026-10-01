"""
중개자를 띄운다.

    uv run python -m firelane.ops                 # 0.0.0.0:8000
    FIRE_LANE_OPS_PORT=9000 uv run python -m firelane.ops

★ **호스트가 0.0.0.0 이다.** 컨테이너 안에서 127.0.0.1 에 묶으면 바깥에서
  닿지 않는다 — Compose 의 포트 매핑이 조용히 무의미해진다.

★ `--reload` 는 안 쓴다. 자동 재적재는 개발 편의인데, 이 프로세스가 **지금
  하는 일은 두 화면을 잇는 것**이고 재적재는 붙어 있던 연결을 전부 끊는다.
  고치고 다시 띄우는 것이 더 정직하다.

★ 환경변수를 **`paths` 를 지나서** 읽는다. `os.environ` 을 직접 읽으면
  `env_check` 가 운다 — 그리고 그 규칙이 옳다(`paths.py` §환경변수 접근자).
  2026-10-01 에 여기서 바로 걸렸다.

IN    FIRE_LANE_OPS_PORT (없으면 8000)
OUT   떠 있는 프로세스
밖    **무엇을 옮기는지 안 본다** — `server.py` 의 일이다
"""
from __future__ import annotations

from firelane import paths
from firelane.cli import no_args

#: ★ 기본 8000. `docker-compose.yml` 의 `ops` 서비스가 같은 수를 적고,
#:   `tests/test_ops_roster.py::test_the_port_is_written_once` 가 둘이 같은지 본다 —
#:   포트가 두 곳에 손으로 적히면 어긋난다.
DEFAULT_PORT = 8000


def port() -> int:
    """들을 포트. **못 읽는 값이면 기본으로 떨어진다.**

    ★ 여기서 터뜨리지 않는다. `FIRE_LANE_OPS_PORT=` (빈 값)이나 오타 하나로
      중개자가 안 뜨면, 출동 중에 그것을 고칠 사람이 없다. 기본 포트로 뜨고
      **떠 있는 것**이 안 뜨는 것보다 낫다 — 어느 포트인지는 로그가 적는다.
    """
    raw = paths.env("FIRE_LANE_OPS_PORT", "").strip()
    if raw.isdigit() and 0 < int(raw) < 65536:
        return int(raw)
    return DEFAULT_PORT


def main() -> None:
    # ★ 인자를 안 받는다. 포트는 환경변수가 정한다 — 깃발로도 받으면 두 문이
    #   되고, 어느 쪽이 이기는지 아무도 모른다. `-h` 는 머리말을 낸다.
    #   `tests/test_cli_surface.py` 가 **모르는 깃발을 거절하는가**를 든다.
    no_args(__doc__)

    # ★ **관문 뒤에서 들인다.** 줄머리에 두면 `uvicorn` 적재가 관문보다 먼저
    #   일어나고, 그것이 실패하는 기계에서는 `--help` 도 모르는 깃발도
    #   **파이썬 역추적**으로 답한다. 2026-10-01 에 여기서 바로 걸렸다 —
    #   사용법을 내야 하는 자리에서 ModuleNotFoundError 가 났다.
    #   함수 안 import 를 이 저장소는 보통 결함으로 본다(§25). 여기가 예외인
    #   이유는 하나 — **적재 실패도 답해야 하는 자리**다.
    import uvicorn

    uvicorn.run(
        "firelane.ops.server:app",
        host="0.0.0.0",      # noqa: S104 — 위 ★
        port=port(),
        log_level="info",
    )


if __name__ == "__main__":
    main()
