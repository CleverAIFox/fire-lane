"""pytest 공통 훅 — skip 정책(`tests/skip_policy.py`)을 모든 skip 보고에 건다.

★ 2026-09-17 (DECISIONS §175). 분류 밖 사유로 skip 하면 **실패로 바꾼다.**
  알리기만 하면 51 에 묻힌다 — 그것이 이 훅이 생긴 이유다.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import skip_policy as sp


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if not rep.skipped or hasattr(rep, "wasxfail"):
        return
    lr = rep.longrepr
    reason = lr[2] if isinstance(lr, tuple) and len(lr) == 3 else str(lr)
    why = sp.judge(reason, lake_attached=sp.lake_attached(), today=datetime.now(ZoneInfo("Asia/Seoul")).date(),
                   plan_titles=set(sp.plan_titles()), outputs_present=sp.outputs_present())
    if why:
        rep.outcome = "failed"
        rep.longrepr = f"skip 정책 위반(tests/skip_policy.py) — {why}\n  skip 사유: {reason}"


# ── 쉘 환경 (PLAN #151 · DECISIONS §431) ───────────────────────
#: 비우는 것 — **스위치와 폐기 이름.** 목록을 손으로 적지 않고 `env_check` 에서
#: 유도한다. 거기가 「이 저장소가 아는 환경변수」의 정본이고, 스위치가 늘면
#: 이 그물도 같이 는다(§398 · §285-2 가 배운 그 꼴).
#:
#: ★ **`SETTINGS` 는 안 비운다.** `FIRE_LANE_DATA` 를 지우면 레이크 시험이
#:   통째로 skip 으로 바뀌고 — 그러면 **덜 재면서 초록**이 된다. 그 방향이
#:   반대 방향보다 비싸다. 켜짐이 새는 것(스위치)은 판정을 **바꾸고**,
#:   레이크 경로가 새는 것은 판정을 **더 많이 재게** 한다.
#:
#: ★ 아직 안 한 것 — 「어느 변수가 실제로 결과를 바꾸나」는 **안 쟀다.**
#:   변수마다 전수 pytest 는 열 개에 80분이다(PLAN #151 이 적은 수).
#:   그래서 **구조로** 자른다: 스위치는 정의상 동작을 바꾸므로 전부 비운다.
@pytest.fixture(autouse=True)
def _shell_switches_do_not_leak(monkeypatch):
    """쉘에 켜 둔 스위치가 시험 결과를 바꾸지 못하게 한다.

    ★ 2026-10-08. 종전에 `conftest` 는 skip 정책만 걸었다. `FIRE_LANE_NO_MERGE`
      하나가 켜져 있으면 병합을 건너뛴 산출로 판정이 돌고, 그래도 **초록으로
      보인다** — 새는 환경은 「덜 재고 통과」를 만든다.
    """
    import env_check as _ec
    for k in sorted(_ec.SWITCHES | _ec.RETIRED):
        monkeypatch.delenv(k, raising=False)


# ── 차량 제원 주입 (PLAN #122 · DECISIONS §431) ────────────────
# ★ 도메인(`seg/vehicle.py`)이 더는 대장을 직접 안 읽는다. 진입점이 주입하고,
#   시험에서는 여기가 그 진입점이다. 안 넣으면 `V.WIDTH` 가 전부 죽는다.
# ★ **대장이 비어 있어도 조용히 넘어간다** — 제원이 없다는 사실 자체를 보는
#   시험(`SpecMissing`)이 따로 있고, 그것까지 막으면 그 시험이 죽는다.
@pytest.fixture(autouse=True, scope="session")
def _vehicle_spec_injected():
    from firelane import ledger as _led
    from firelane.seg import vehicle as _V
    try:
        _V.use(_led.vehicle_spec())
    except _V.SpecMissing:
        pass
