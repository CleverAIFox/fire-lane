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


def _src(n: int, extra: dict[int, str] | None = None, head: int = 0) -> str:
    """비교 자리가 `n` 개인 소스 — 줄마다 다른 상수. `extra[i]` 는 `i` 번째 앞에 끼우는 줄, `head` 는 맨 위에 끼우는 주석 줄 수."""
    body = [f"def f{i}(x):\n    return x == {1000 + i}" for i in range(n)]
    for at, line in sorted((extra or {}).items(), reverse=True):
        body.insert(at, line)
    return "\n".join(["# 머리말"] * head + body) + "\n"


def _ident(src: str, got: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """표본의 정체 — (원문 줄, 바꾼 꼴). 줄 번호는 정체가 아니다."""
    lines = src.split("\n")
    return {(lines[int(w.split(": ")[0]) - 1].strip(), w.split(": ", 1)[1]) for w, _ in got}


def test_cap_passes_through_is_deterministic_and_reports_in_file_order():
    ten = [(f"{i}: a → b", "") for i in range(10)]
    assert M.pick(ten, 0) == ten and M.pick(ten, 99) == ten
    got = [w for w, _ in M.pick(ten, 3)]
    assert got == [w for w, _ in M.pick(ten, 3)] and len(got) == 3
    assert got == sorted(got, key=lambda w: int(w.split(":")[0])), "보고 순서는 파일 순서다"
    many = [(f"{i}: a → b", "") for i in range(200)]
    assert max(int(w.split(":")[0]) for w, _ in M.pick(many, 20)) >= 100, "앞에서 자르면 머리말만 흔든다 — 표본이 한쪽에 몰렸다"


def test_the_sample_does_not_move_when_lines_are_inserted_above():
    """★ PLAN #255 — 줄 번호를 키로 쓰면 위에 줄이 끼는 것만으로 표본이 갈린다(DECISIONS §817: `tonecheck` 4 중 2)."""
    a, b = _src(60), _src(60, head=7)
    assert M.mutants(a) and len(M.mutants(a)) == len(M.mutants(b))
    assert _ident(a, M.pick(M.mutants(a), 4, a)) == _ident(b, M.pick(M.mutants(b), 4, b))


def test_the_sample_barely_moves_when_sites_are_added():
    """★ PLAN #255 — 종전 규칙(`int(i * 자리수 / 4)`)은 자리가 129 → 136 으로 늘자 같은 자리가 1/4 만 남았다. 이 규칙은 자리 하나에 최대 하나만 바뀐다."""
    old = lambda n: {int(i * (n / 4)) for i in range(4)}      # 종전 규칙의 자리 번호 — 통제군
    assert len(old(129) & old(136)) <= 1, "통제군이 이미 안 갈리면 이 시험은 아무것도 안 잰다"
    base = _src(129)
    got = _ident(base, M.pick(M.mutants(base), 4, base))
    for at in (0, 40, 100, 129):
        src = _src(129, {at: "def g(x):\n    return x != 7"})
        assert len(got & _ident(src, M.pick(M.mutants(src), 4, src))) >= 3, f"자리 하나({at}번째 앞)가 표본을 둘 이상 갈랐다"
    seven = _src(129, {at: f"def h{at}(x):\n    return x < {at}" for at in (5, 30, 55, 80, 100, 120, 128)})
    assert len(M.mutants(seven)) - len(M.mutants(base)) >= 7
    assert len(got & _ident(seven, M.pick(M.mutants(seven), 4, seven))) >= 2, "일곱 자리가 늘어 표본이 거의 다 갈렸다"


def test_the_ledger_fingerprint_follows_the_sampling_rule(monkeypatch):
    """★ PLAN #255 의 둘째 구멍 — `catch_print` 가 `mutate.py` 를 안 해시해 `pick` 을 고쳐도 `--write --stale` 이 낡은 도구를 0 개로 냈다."""
    import mutatescope as MS
    was, rule = MS.catch_print("sizecheck"), MS.sampler_print()
    assert MS.catch_print("sizecheck") == was and MS.sampler_print() == rule
    monkeypatch.setattr(MS, "pick", lambda muts, cap, src=None: muts[:cap])      # 규칙이 바뀐다
    assert MS.sampler_print() != rule
    assert MS.catch_print("sizecheck") != was and MS.catch_print("planclose") != MS.catch_print("sizecheck")


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

    ★ 2026-10-14 (DECISIONS 532-3). `SILENCED` 는 **여기 없다** — 옆집
      `mutatesilent` 가 든다. 그 축을 아는 도구가 제 래칫을 드는 것이 이
      저장소의 꼴이고(`canary.NO_CANARY` · `sealcov.SEALED_FILES` ·
      `docseal.UNSEALED` …), `ratchet.py` 가 모은다. 아래에서 **같이** 본다 —
      옆집에 뒀다는 것이 「아무도 안 든다」가 되면 안 된다.
    """
    assert M.RATCHETS == {"SURVIVORS": "down", "MUTANTS": "up",
                          "UNCATCHABLE": "down", "UNSORTED": "down"}
    # ★ 2026-11-17 (DECISIONS §820). `RATCHET_HELD` 는 래칫이 아니다 — 새 표본에서 래칫 상수 56자리 중 1곳(1.8%)만 든다. 분류(`sort_survivors`)는 남는다.
    assert "RATCHET_HELD" not in M.RATCHETS and not hasattr(M, "RATCHET_HELD")
    held, rest = M.sort_survivors({"도구별": [{"도구": "sealcov", "생존": ["146: 0 → 1"]}]})
    assert [h[0] for h in held] == ["sealcov"] and rest == [], "분류는 남아야 한다 — 장부 읽는 쪽이 이 가름을 쓴다"


def test_the_silence_axis_is_held_next_door():
    """침묵 축이 **옆집에서** 래칫으로 서 있는가.

    ★ 2026-10-14 (DECISIONS 532-3). `mutate.py` 가 상한 600 에 서 있어 그
      축을 `mutatesilent` 로 내렸다. 내린 것이 **잃은 것**이 되지 않도록
      여기서 그 집을 가리킨다 — 「옆집에 있다」는 말은 그 집을 재는 자가
      있을 때만 참이다(§390).
    """
    import mutatesilent as S

    assert S.RATCHETS == {"SILENCED": "down"}, (
        f"침묵 축의 래칫 방향이 바뀌었다 — {S.RATCHETS}. 침묵은 **늘 수 없다**")
    assert isinstance(S.SILENCED, int) and S.SILENCED >= 0
    assert "SILENCED" not in M.RATCHETS, (
        "두 집이 같은 축을 든다 — 한쪽만 고치면 **갈린다**(MASTER §18-3)")
    # 판정 자체도 민다 — 침묵이 무엇인지 그 집이 안다
    assert S.is_silent(0, "", "   \n"), "rc=0 · 공백뿐 → 침묵이어야 한다"
    assert not S.is_silent(0, "x", ""), "글자가 있으면 침묵이 아니다"
    assert not S.is_silent(1, "", ""), "rc≠0 은 침묵이 아니라 **빨강**이다"
    assert S.label(["/abs/path/python3", "tools/x.py", "--selftest"]) == (
        "python tools/x.py --selftest"), "절대 경로가 장부로 새 나간다"


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
    # ★ 2026-10-09 (DECISIONS §445). `TOOLS` · `TESTS` 는 `mutatescope` 가
    #   들고 `mutate` 는 그것을 끌어온 **제 이름**을 갖는다. 흔드는 코드는
    #   양쪽에 있으므로(`shake` 는 `mutate` · `named_tests` 는 `mutatescope`)
    #   **쓰는 쪽마다** 갈아야 한다 — 한쪽만 갈면 시험이 실물 `tests/` 를
    #   훑는다. `mutate` 는 `TESTS` 를 **안 끌어온다**(쓰지 않으므로) —
    #   그래서 그 이름은 `mutatescope` 에만 있다.
    import mutatescope as S
    monkeypatch.setattr(M, "TOOLS", tools)      # `shake` 가 쓴다
    monkeypatch.setattr(S, "TOOLS", tools)      # `catch_print` 가 쓴다
    monkeypatch.setattr(S, "TESTS", tmp_path / "없는곳")   # `named_tests` 가 쓴다
    r = M.shake("toy", cap=2)
    assert (tools / "toy.py").read_text(encoding="utf-8") == src, "원본이 안 돌아왔다"
    assert r["붙잡이"] == 0, "자기검사가 없는 도구에 붙잡이가 생겼다"
    assert len(r["생존"]) == r["돌연변이"], "붙잡이가 0인데 뭔가 죽었다"


def test_the_ledger_fingerprint_follows_the_operator_table(monkeypatch, tmp_path):
    """★ DECISIONS §820 — 연산자 표에 `in → not in` · `is → is not` 을 더해도 지문이 달라진 도구가 0/37 이었다(자리 2,582 → 2,786 · 표본 6자리)."""
    import mutatescope as MS
    src = (ROOT / "tools/mutate.py").read_text(encoding="utf-8")
    was, rule = MS.catch_print("sizecheck"), MS.sampler_print()
    anchor = "_CMP = {ast.GtE:"
    assert src.count(anchor) == 1
    more = tmp_path / "mutate.py"
    more.write_text(src.replace(anchor, '_CMP = {ast.In: "not in", ast.Is: "is not", ast.GtE:'), encoding="utf-8")
    monkeypatch.setattr(MS, "MUTATE_SRC", more)
    assert MS.sampler_print() != rule and MS.catch_print("sizecheck") != was, "연산자를 더했는데 지문이 안 달라졌다"
    # 후보와 상관없는 줄(래칫 상수 · 주석)은 지문에 안 든다 — 상수 한 줄에 37 도구가 낡으면 값을 못 치른다
    same = tmp_path / "mutate_same.py"
    same.write_text(src.replace("UNCATCHABLE = 0", "UNCATCHABLE = 0  # 주석 한 줄", 1), encoding="utf-8")
    monkeypatch.setattr(MS, "MUTATE_SRC", same)
    assert MS.sampler_print() == rule
    # 후보 규칙을 못 찾으면 조용히 비우지 않고 운다
    broken = tmp_path / "mutate_broken.py"
    broken.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(MS, "MUTATE_SRC", broken)
    with pytest.raises(RuntimeError, match="못 찾았다"):
        MS.sampler_print()
