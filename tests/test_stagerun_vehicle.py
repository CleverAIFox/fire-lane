"""단계가 **자식 프로세스**로 돌 때도 차량 제원이 들어가는가.  (DECISIONS §530)

── 왜 생겼나 ───────────────────────────────────────────────────
`pipeline.main()` 이 `vehicle.use(ledger.vehicle_spec())` 를 부른다. 그런데
단계는 `subprocess.run([… -m firelane.stagerun …])` 로 **자식에서** 돈다.
제원은 모듈 전역(`vehicle._S`)이라 **프로세스를 못 넘는다.**

★ 그래서 `segments` 가 매 실행 「차량 경로 생략 — 차량 제원이 주입되지
  않았다」를 찍고 `route_vehicle.csv` 를 **안 다시 썼다.** 옛 파일이 그대로
  발행돼 관제 화면의 도달 수가 **옛 폭**으로 서 있었다. 2026-10-14 에
  측정 배치의 「지표 재산출」이 `passable` ↔ `edge_cost` **8건 어긋남**으로
  그것을 처음 집었다 — 그때까지 아무도 안 봤다.

★ **조용한 생략이 제일 나쁘다.** 죽었으면 그 날 고쳤다. 한 줄 찍고 넘어가니
  로그를 읽는 사람만 보고, 로그는 500줄이다.

IN    `firelane.stagerun`
OUT   주입됐는가
밖    **제원이 옳은가는 안 본다** — `sources.yaml` 과 `seg/vehicle.use()` 소관이다.
      **경로가 옳은가도 안 본다** — 그것은 `evalgate` 의 `passable` 게이트다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _run(code: str) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC),
           "HOME": str(Path.home())}
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


#: `main()` 을 **진짜로** 지나가며 제원이 섰는지 묻는 탐침.
#: 단계 모듈을 가짜로 바꿔 그 안에서 본다 — 실제 단계는 레이크가 필요하다.
_PROBE = """
import sys
sys.argv = ["x", "segments"]
import firelane.stagerun as SR
from firelane.seg import vehicle as V

def probe():
    try:
        print("W", V.WIDTH)
    except V.SpecMissing:
        print("MISSING")

SR.stage_main = lambda name: probe
SR.main()
"""


def test_the_real_entry_point_injects_the_spec() -> None:
    """**이 판의 머리다.** `stagerun.main()` 을 지나면 단계가 제원을 본다.

    ★ `_inject_vehicle()` 을 직접 부르지 않는다 — 그러면 **그 함수만** 밀고
      `main()` 이 그것을 부르는지는 안 민다. 2026-10-14 에 그렇게 썼다가
      호출을 지워도 초록이었다. 그물은 **사람이 지나는 길**에 쳐야 한다.
    """
    r = _run(_PROBE)
    assert r.returncode == 0, f"자식이 죽었다 — {r.stderr[-400:]}"
    assert "W 2.5" in r.stdout, (
        "자식 프로세스에 차량 제원이 안 들어갔다 — `route_vehicle.csv` 가 "
        f"조용히 안 다시 써진다(DECISIONS §530). 받은 것: {r.stdout!r}")


def test_without_the_injection_the_spec_is_missing() -> None:
    """**반대 방향.** 안 부르면 비어 있다 — 한쪽만 밀면 빈 그물이다."""
    r = _run("from firelane.seg import vehicle as V\n"
             "try:\n"
             "    V.spec(); print('STOOD')\n"
             "except V.SpecMissing:\n"
             "    print('MISSING')\n")
    assert r.returncode == 0, r.stderr[-400:]
    assert "MISSING" in r.stdout, (
        "안 불렀는데 제원이 서 있다 — 이 시험이 아무것도 안 민다")


def test_the_injection_runs_before_the_stage() -> None:
    """순서가 뜻이다 — 단계를 **고르기 전에** 넣는다. 뒤에 넣으면 늦다."""
    src = (ROOT / "src" / "firelane" / "stagerun.py").read_text(encoding="utf-8")
    i, j = src.index("_inject_vehicle()\n    fn ="), src.index("fn = stage_main(name)")
    assert i < j, "제원 주입이 단계 선택보다 뒤에 있다"


def test_a_missing_spec_does_not_kill_the_stage() -> None:
    """제원이 없어도 **안 죽는다** — 그것과 무관한 단계가 많다."""
    src = (ROOT / "src" / "firelane" / "stagerun.py").read_text(encoding="utf-8")
    k = src.index("def _inject_vehicle")
    body = src[k:src.index("def main()", k)]
    assert "except _V.SpecMissing:" in body and "pass" in body, (
        "제원이 없을 때 삼키지 않는다 — ingest · terrain 까지 못 돈다")
