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


LAKE_FREE = {"NO_CONTRACT_RATCHET", "CRS_DECLARED_RATCHET"}


def test_the_declared_names_match_what_the_measure_returns():
    vals = CV.ratchet_values()
    assert set(CV.RATCHETS) == set(vals) == LAKE_FREE
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
    assert {r["name"] for r in rows} == LAKE_FREE
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


# ── PLAN #213 — 결손 선언(`ABSENT`) · 실물 갈래 둘을 선언 안으로 ─────────────────────────────

def test_absent_count_counts_only_the_declared_absence_and_not_the_warnings():
    from firelane.contract_crs import ABSENT, FAIL, WARN
    reports = [SimpleNamespace(worst=ABSENT), SimpleNamespace(worst=ABSENT), SimpleNamespace(worst=WARN), SimpleNamespace(worst=FAIL), SimpleNamespace(worst="OK")]
    assert CV.absent_count(reports) == 2
    assert CV.real_counts(reports) == (1, 1), "결손이 경고에 센다 — 등급이 둘로 샌다"
    assert CV.absent_count([]) == 0


def test_a_missing_declaration_is_graded_absent_by_the_one_criterion_and_nothing_else_is(tmp_path):
    """★ 가르는 기준은 **하나**다 — 대장이 `status: missing` 이라고 선언했느냐. 입력이 제자리에 있느냐 · 사유가 비었느냐는 등급을 안 바꾼다."""
    from firelane import contract as C
    from firelane.contract_crs import ABSENT, FAIL, WARN
    base = {"kind": "raw_only", "stem": "zz_probe", "ext": ["zip"], "contract": {"rows": 1}}
    assert C.check_one("p", {**base, "status": "missing", "missing_why": "받지 않기로 했다"}, tmp_path, None).worst == ABSENT
    assert C.check_one("p", {**base, "status": "missing"}, tmp_path, None).worst == ABSENT          # 사유가 비어도 선언은 선언이다 — 문구가 「사유 미기재」를 말한다
    assert C.check_one("p", {**base, "awaiting": "2026-10-07 — 아직 안 왔다"}, tmp_path, None).worst == WARN   # 반입 대기는 결손이 아니다
    assert C.check_one("p", dict(base), tmp_path, None).worst == FAIL                                # 선언도 실물도 없으면 실패다


def test_real_measure_counts_the_three_grades_from_a_synthetic_ledger_and_refuses_without_a_lake(tmp_path, monkeypatch):
    import pytest

    from firelane import contract as C
    from firelane import paths
    base = {"kind": "raw_only", "stem": "zz", "ext": ["zip"], "contract": {"rows": 1}}
    ds = {"a": {**base, "status": "missing", "missing_why": "x"}, "b": {**base, "awaiting": "y"}, "c": dict(base), "d": {**base, "status": "missing", "missing_why": "z"}}
    monkeypatch.setattr(C, "_load_ds", lambda: (ds, None))
    monkeypatch.setattr(paths, "RAW", tmp_path)
    with pytest.raises(FileNotFoundError):
        C.real_measure()                                  # gjcity 가 없다 = 레이크가 없다
    (tmp_path / "gjcity").mkdir()
    assert C.real_measure() == (1, 1, 2)                  # 실패 c · 경고 b · 결손 a d


def test_the_real_ratchets_are_omitted_without_a_lake_and_never_written_as_zero(monkeypatch):
    from firelane import contract as C

    def no_lake():
        raise FileNotFoundError("레이크가 없다")
    monkeypatch.setattr(C, "real_measure", no_lake)
    assert C.ratchet_values() == {}
    monkeypatch.setattr(C, "real_measure", lambda: (7, 56, 10))
    assert C.ratchet_values() == {"REAL_FAIL_RATCHET": 7, "REAL_WARN_RATCHET": 56}


def test_ratchet_skips_a_lake_only_name_with_its_reason_but_a_name_without_the_declaration_is_still_red(monkeypatch):
    """★ 건너뛰는 길이 **선언한 이름에만** 열린다 — 「안 냈으면 봐 준다」가 되면 어떤 결함도 통과한다(§318)."""
    p = RT.SRC / "contract.py"
    declared = SimpleNamespace(RATCHETS={"GHOST": "down"}, LAKE_ONLY={"GHOST": "레이크가 있어야 잰다"}, ratchet_values=lambda: {})
    monkeypatch.setattr(RT, "owners", lambda: [(p, declared)])
    rows = RT.survey()
    assert [("skip" in r, "err" in r) for r in rows] == [(True, False)] and "레이크" in rows[0]["skip"]
    undeclared = SimpleNamespace(RATCHETS={"GHOST": "down"}, ratchet_values=lambda: {})
    monkeypatch.setattr(RT, "owners", lambda: [(p, undeclared)])
    rows = RT.survey()
    assert [("skip" in r, "err" in r) for r in rows] == [(False, True)]


def test_the_real_ratchets_live_in_contract_and_are_declared_lake_only_and_the_scan_picks_them_up():
    """★ 집이 `contract.py` 다(순환을 피해) — 훑기가 그 파일을 **실제로** 집고 두 이름이 `LAKE_ONLY` 에 든다."""
    from firelane import contract as C
    assert set(C.RATCHETS) == set(C.LAKE_ONLY) == {"REAL_FAIL_RATCHET", "REAL_WARN_RATCHET"}
    assert {p.name for p, _ in RT.owners()} >= {"contract.py", "contract_verdict.py"}
    assert (C.REAL_FAIL_RATCHET, C.REAL_WARN_RATCHET) == (7, 57)


def test_on_a_lake_machine_the_real_ratchets_equal_the_measure():
    """레이크가 있는 기계에서만 — 선언 56 · 7 이 실측과 같다. 없으면 건너뛴다(CI)."""
    import pytest

    from firelane import contract as C
    vals = C.ratchet_values()
    if not vals:
        pytest.skip("환경skip(레이크) — raw 가 없어 실물 갈래를 못 잰다")
    assert vals == {"REAL_FAIL_RATCHET": C.REAL_FAIL_RATCHET, "REAL_WARN_RATCHET": C.REAL_WARN_RATCHET}
