"""`contract_verdict` 의 래칫 둘이 `tools/ratchet.py` 의 **선언 안**에 있는가 · 실물 갈래의 셈이 한 곳인가.  (PLAN #185 ②)

★ 이 행의 문제가 「선언 밖 래칫이 샌다」였다. 래칫 상수가 `src/firelane/` 모듈에 살아 `tools/` 만 훑던 `ratchet.py` 가 못 봤다 —
  훑기를 `src/firelane/` 까지 넓히고 선언 갈래 둘(`NO_CONTRACT_RATCHET` · `CRS_DECLARED_RATCHET`)을 들였다. 양성 대조가 본체다:
  ① 훑기가 그 모듈을 **실제로** 집는다 ② 선언한 이름이 `ratchet_values()` 와 같다 ③ 방향이 판정과 맞다(무계약은 늘면 · crs 는 줄면 운다)
  ④ 시험이 `TOOLS` 를 사본으로 갈아끼우면 실물 `src` 를 같이 읽지 않는다.

IN    `tools/ratchet.py` · `src/firelane/contract_verdict.py`
OUT   없음 (검사)
PARAM 없음
밖    실물 갈래 둘(`REAL_FAIL_RATCHET` · `REAL_WARN_RATCHET`)은 안 본다 — 선언 밖에 남겼다(`contract_verdict` 머리의 사유). 레이크가 필요한 셈은 안 돈다.
"""
from __future__ import annotations

from types import SimpleNamespace

import ratchet as RT

from firelane import contract_verdict as CV


def test_the_scan_picks_up_the_module_under_src():
    """★ 양성 대조 — 훑기가 `src/firelane/contract_verdict.py` 를 **집는다.** 안 집으면 선언이 있어도 샌다."""
    names = {p.name for p, _ in RT.owners()}
    assert "contract_verdict.py" in names


def test_the_declared_names_match_what_the_measure_returns():
    vals = CV.ratchet_values()
    assert set(CV.RATCHETS) == set(vals) == {"NO_CONTRACT_RATCHET", "CRS_DECLARED_RATCHET"}
    assert vals["NO_CONTRACT_RATCHET"] == CV.NO_CONTRACT_RATCHET and vals["CRS_DECLARED_RATCHET"] == CV.CRS_DECLARED_RATCHET


def test_the_directions_match_the_gates_own_verdict():
    """무계약은 **늘면** 운다(`down`) · crs 선언은 **줄면** 운다(`up`) — `contract.cmd_declared` 의 판정과 같은 방향이다."""
    assert CV.RATCHETS == {"NO_CONTRACT_RATCHET": "down", "CRS_DECLARED_RATCHET": "up"}
    assert RT.tightens("down", 10, 8) and not RT.tightens("down", 10, 12)
    assert RT.tightens("up", 10, 12) and not RT.tightens("up", 10, 8)


def test_the_real_rows_of_the_survey_carry_the_path_of_a_src_owner(monkeypatch):
    """`--write` 가 쓸 자리 — `src` 모듈의 래칫은 `tools/` 가 아니라 그 파일에 쓴다(`path`).

    ★ 전수 훑기(80개 도구를 다 잰다)를 안 돌린다 — 소유자를 이 모듈 하나로 갈아끼워 이 행만 만든다(묶음 시험이 느려지지 않게).
    """
    monkeypatch.setattr(RT, "owners", lambda: [(RT.SRC / "contract_verdict.py", CV)])
    rows = [r for r in RT.survey() if r.get("tool") == "contract_verdict.py" and "at" in r]
    assert {r["name"] for r in rows} == {"NO_CONTRACT_RATCHET", "CRS_DECLARED_RATCHET"}
    assert all(r["path"] == RT.SRC / "contract_verdict.py" for r in rows)


def test_a_replaced_tools_dir_does_not_pull_in_the_real_src(tmp_path, monkeypatch):
    """사본 트리를 훑는 시험이 실물 `src` 의 래칫을 같이 읽으면 그 시험의 기대(선언한 도구만)가 깨진다."""
    fake = tmp_path / "tools"
    fake.mkdir()
    monkeypatch.setattr(RT, "TOOLS", fake)
    assert RT.owners() == []


def test_real_counts_counts_fail_and_warn_and_adds_the_unknown_to_fail():
    """`contract.main` 과 같은 셈이 **한 곳**이다 — 실패에 대장에 없는 키 수를 더한다."""
    from firelane.contract_crs import FAIL, WARN
    reports = [SimpleNamespace(worst=FAIL), SimpleNamespace(worst=WARN), SimpleNamespace(worst=WARN), SimpleNamespace(worst="OK")]
    assert CV.real_counts(reports) == (1, 2)
    assert CV.real_counts(reports, unknown=3) == (4, 2)
    assert CV.real_counts([]) == (0, 0)
