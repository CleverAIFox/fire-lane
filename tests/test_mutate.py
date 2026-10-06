#!/usr/bin/env python3
"""
test_mutate.py — **돌연변이 관문이 제 할 일을 하는가.**  (DECISIONS §396 · PLAN #149)

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 흔들기가 **연산자·상수만** 건드린다 — 이름을 바꾸면 전부 죽고,
       전부 죽음은 아무것도 안 잰 것과 같다
    2. 주석이 살아남는다 — `ast.unparse` 로 다시 쓰면 변경이 「연산자 하나」가
       아니라 **파일 전체**가 된다
    3. 붙잡이를 **도출**한다. 기본은 자기검사만이고 `--deep` 이 시험을 더한다
    4. 대장이 낡으면 **0 을 내지 않는다** — `RuntimeError` 로 멈춘다
    5. 흔든 뒤 **원본이 되돌아온다**

★ 이 파일은 `mutate` 를 이름으로 들기 때문에 `--deep` 의 붙잡이이기도 하다 —
  이 시험을 깨뜨리는 돌연변이는 `--deep` 에서 죽는다.

밖    **생존이 적은 것이 좋은 것인지는 안 본다.** 정렬 키나 로그 문구처럼
      행동을 안 바꾸는 자리의 생존은 정상이고, 가르는 것은 사람이다.
      **흔든 결과의 수가 옳은지도 안 본다** — 그것은 `ratchet.py` 가 대장과
      대고, 대장이 낡으면 이 도구가 `RuntimeError` 로 멈춘다.
      그리고 **`--deep` 을 안 돌린다** — 실측 한 시간 넘어 시험이 못 든다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("_mut", ROOT / "tools/mutate.py")
    m = importlib.util.module_from_spec(spec)
    # ★ `@dataclass` 가 `cls.__module__` 로 되짚는다 — 없으면 터진다(지연 신관).
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


M = _mod()


def test_selftest_is_green():
    assert M.selftest() == 0


def test_mutation_touches_only_operators_and_constants():
    """이름·import 를 건드리면 `NameError` 로 전부 죽는다 — 그것은 측정이 아니다."""
    src = "import os\n\n\ndef f(a):\n    return os.sep if a >= 3 else None\n"
    got = [w for w, _ in M.mutants(src)]
    assert got, "멀쩡한 소스에 하나도 안 낸다"
    assert all("os" not in w and "import" not in w for w in got), got
    assert any(">=" in w for w in got) and any("3 → 4" in w for w in got)


def test_mutation_keeps_comments():
    """주석이 날아가면 변경이 연산자 하나가 아니라 파일 전체다."""
    src = '"""머리말."""\n# 꼬리 주석\nX = 1\n'
    bodies = [b for _, b in M.mutants(src)]
    assert bodies
    assert all("꼬리 주석" in b and "머리말" in b for b in bodies)


def test_mutation_is_deterministic():
    src = "def f(a, b):\n    return a > 1 and not b\n"
    assert [w for w, _ in M.mutants(src)] == [w for w, _ in M.mutants(src)]


def test_syntax_error_yields_nothing_rather_than_a_lie():
    assert M.mutants("def (:::") == []


def test_cap_samples_evenly_and_passes_through():
    """앞에서 자르면 머리말만 흔든다 — 거기는 행동이 없어 생존이 쏟아진다."""
    ten = [(str(i), "") for i in range(10)]
    assert [w for w, _ in M.pick(ten, 3)] == ["0", "3", "6"]
    assert M.pick(ten, 0) == ten and M.pick(ten, 99) == ten


def test_catchers_are_derived_and_pytest_is_opt_in():
    """★ 목록을 손으로 적으면 도구가 늘 때마다 빠진다(§285-2 · §284-4 · §286)."""
    shallow = M.catchers("mutate")
    assert any("--selftest" in c for c in shallow)
    assert not any("pytest" in c for c in shallow), (
        "기본에 pytest 가 들어갔다 — 실측 한 시간 넘어 안 끝난다")
    deep = M.catchers("mutate", deep=True)
    assert any("pytest" in c for c in deep), "--deep 이 이 파일을 안 집는다"


def test_the_ledger_refuses_to_answer_when_stale(tmp_path, monkeypatch):
    """★ 낡은 대장으로 **0 을 내지 않는다.** 자동으로 느슨해지면 관문이 죽는다."""
    fake = tmp_path / "mutation.json"
    monkeypatch.setattr(M, "LEDGER", fake)
    with pytest.raises(RuntimeError, match="없다"):
        M.ratchet_values()
    fake.write_text(json.dumps(
        {"돌연변이": 1, "생존": 0,
         "도구별": [{"도구": "mutate", "지문": "0" * 12}]}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="바뀌었다"):
        M.ratchet_values()


def test_the_ratchet_is_two_way():
    """생존만 잠그면 그물이 줄 때 같이 줄어 좋아 보인다 — 분모도 잠근다.

    ★ 2026-10-06 (DECISIONS §410). 가름 둘이 늘었다. `RATCHET_HELD` 가
      **올라가는 쪽**인 것이 뒤집힌 것처럼 보이지만 아니다 — 래칫을 하나 더
      다는 것이 좋은 일이고 그때 이 수가 오른다.
    """
    assert M.RATCHETS == {"SURVIVORS": "down", "MUTANTS": "up",
                          "UNCATCHABLE": "down",
                          "RATCHET_HELD": "up", "UNSORTED": "down"}


def test_survivors_held_by_a_ratchet_are_told_apart():
    """★ 2026-10-06 (DECISIONS §410). 생존 중 **래칫 상수**를 가른다.

    그 수를 흔들면 그 도구의 시험은 조용하고 `tools/ratchet.py` 가 운다.
    이 도구는 그 도구의 시험만 돌리므로 그 문을 못 본다 — **「안 붙들린다」와
    「이 문이 안 붙든다」는 다르다.**

    실물이 아니라 **합성 입력**으로 양방향을 민다(§230).
    """
    ln = M._ratchet_line("sealcov", "SEALED_FILES")
    synth = {"도구별": [{"도구": "sealcov",
                       "생존": [f"{ln}: 363 → 364", f"{ln + 900}: 1 → 2"]}]}
    held, rest = M.sort_survivors(synth)
    assert [t for t, _, _ in held] == ["sealcov"], f"래칫 상수를 안 가린다: {held}"
    assert held[0][2] == "SEALED_FILES", f"래칫 이름을 틀리게 읽는다: {held[0][2]}"
    assert len(rest) == 1, f"래칫이 아닌 생존을 래칫으로 센다: {rest}"
    # ★ 반대 방향 — 래칫 키가 아닌 이름은 안 든다
    synth2 = {"도구별": [{"도구": "sealcov", "생존": [f"{ln + 900}: 1 → 2"]}]}
    assert not M.sort_survivors(synth2)[0], "래칫이 아닌 것을 래칫으로 든다"


def test_shaking_restores_the_original(tmp_path, monkeypatch):
    """흔든 뒤 원본이 안 돌아오면 저장소가 돌연변이를 입은 채 남는다."""
    tools = tmp_path / "tools"
    tools.mkdir()
    src = "#!/usr/bin/env python3\nX = 1\n"
    (tools / "toy.py").write_text(src, encoding="utf-8")
    monkeypatch.setattr(M, "TOOLS", tools)
    monkeypatch.setattr(M, "TESTS", tmp_path / "없는곳")
    r = M.shake("toy", cap=2)
    assert (tools / "toy.py").read_text(encoding="utf-8") == src, "원본이 안 돌아왔다"
    assert r["붙잡이"] == 0, "자기검사가 없는 도구에 붙잡이가 생겼다"
    assert len(r["생존"]) == r["돌연변이"], "붙잡이가 0인데 뭔가 죽었다"
