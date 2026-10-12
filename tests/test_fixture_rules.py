"""
test_fixture_rules.py — 커밋된 사본이 **어떻게 생겼는지**를 저장소가 아는가.
  (DECISIONS §444 · PLAN #134 ㉡)

★ 사본은 원본에서 멀어질수록 값이 아니라 **출처**가 자산이다. `tests/fixtures/n1/`
  의 셋은 석 주 동안 「앞 20줄」인지 「무작위 20줄」인지가 아무 데도 없었고,
  그것은 다시 떠야 하는 날 사람이 추측한다는 뜻이다 — 추측해 뜬 사본은
  같은 이름을 쓰면서 다른 것을 시험한다.

★ 도구의 자기검사와 **같은 판별식을 두 곳에서** 민다. 자기검사는 합성 입력으로
  그물이 비었나를 보고(`selftests.py` 가 돌린다), 이쪽은 **실물 폴더**에서 본다.

밖    **사본의 내용이 옳은가는 안 본다** — 그것은 그 사본을 먹는 시험이 든다.
      **다시 뜨지도 않는다**(원본이 레이크에 있다) — 규칙이 적혀 있는가만 본다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
N1 = ROOT / "tests" / "fixtures" / "n1"


def _mod():
    """★ `tools/` 를 `sys.path` 에 넣지 않고 경로로 집는다 — `test_dest_scope`
    와 같은 방식이다. `@dataclass` 가 모듈을 되짚으므로 등록은 한다(§258-10)."""
    spec = importlib.util.spec_from_file_location(
        "fixture_recut_rules", ROOT / "tools" / "fixture_recut.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def test_every_committed_fixture_declares_how_it_was_cut():
    """실물 — `n1/` 의 사본이 전부 `CUTS` 나 `UNCUT` 에 규칙을 들고 있다."""
    fr = _mod()
    real = fr.n1_files()
    assert real, f"{N1.relative_to(ROOT)} 에서 0장을 셌다 — 수집기를 의심하라"
    bad = fr.uncut_faults(fr.UNCUT, real)
    assert not bad, (
        "커밋된 사본이 **어떻게 잘렸는지**를 아무 데도 안 적는다\n  "
        + "\n  ".join(bad)
        + "\n  규칙을 `tools/fixture_recut.py` 의 `UNCUT` 에 적어라. "
          "다시 떠야 할 날에 사람이 추측하지 않도록.")


def test_the_rules_name_the_source_file():
    """규칙이 **무엇에서 떴는지**를 든다. 「20줄이다」만으로는 다시 못 뗀다."""
    fr = _mod()
    for rel, why in fr.UNCUT.items():
        assert len(why.strip()) >= 30, f"{rel} — 규칙이 너무 짧다"
        assert any(k in why for k in ("원본", "geojson", ".csv")), (
            f"{rel} — 규칙이 **출처**를 안 든다: {why[:60]}")


def test_the_axis_is_two_way():
    """합성 입력 — 선언 없는 사본과 **없는 파일을 가리키는 선언**을 둘 다 운다."""
    fr = _mod()
    rule = "원본 " + "가" * 40
    assert fr.uncut_faults({}, ["tests/fixtures/n1/x.csv"]), "선언 없는 사본을 안 운다"
    assert fr.uncut_faults({"tests/fixtures/n1/x.csv": rule}, []), "죽은 선언을 안 운다"
    assert not fr.uncut_faults({"tests/fixtures/n1/x.csv": rule},
                               ["tests/fixtures/n1/x.csv"]), "정상 입력에서 운다"


def test_the_check_speaks_this_axis_even_with_no_lake(capsys):
    """★ 이 축의 값은 **레이크 없이도 돈다**는 데 있다. 원본이 있어야 도는
    검사는 CI 에서 영영 건너뛰고, 건너뛴 검사는 없는 검사다(1족 · 무음 통과).

    그래서 rc 만 보지 않고 **`n1` 줄이 찍혔는지**를 본다 — 조용히 건너뛰면
    rc 도 0 이라 수치로는 통과와 구별이 안 된다.
    """
    fr = _mod()
    assert fr.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert "n1 사본" in out, f"`n1/` 축이 한 줄도 안 찍혔다 — 조용히 건너뛰었다\n{out}"
