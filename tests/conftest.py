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
