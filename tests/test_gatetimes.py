"""tools/gatetimes.py — `pre-push.gates` 셋째 열(**훅 안에서 잰** 벽시계 초)을 재고 쓴다.  (PLAN #210)

★ 양성 대조 — ① 훅이 찍는 줄을 읽는다(초록 · 빨강 · 이름에 공백) ② **빨간 게이트가 하나라도 있으면 안 쓴다**(빨강의 초는 값이 아니다) ③ 줄을 못 읽은 게이트가 있어도
  안 쓴다(빈 열은 거짓) ④ 쓸 때 **셋째 열만** 바뀌고 주석 · 이름 · 명령은 글자 그대로다 ⑤ 두 번 써도 같다 ⑥ 실제 훅의 출력 서식과 읽는 정규식이 맞는다.

IN    `tools/gatetimes.py` · 합성 훅 출력 · 합성 게이트 파일
OUT   없음 (검사)
PARAM 없음
밖    **훅을 실제로 돌려 재는 것은 안 한다**(수십 초 걸리고 기계마다 다른 수다 — 사람이 손으로 돌린다). 여기서는 읽기 · 합치기 · 쓰기만 본다.
"""
from __future__ import annotations

import gatetimes as G

GREEN = "  ✓ deadcheck 래칫           28.9초\n  ✓ 봉인 덮임                2.1초\n"
RED = "\x1b[31m  ✗ 문서 말투                 5.0초\x1b[0m\n"


def test_the_line_the_hook_prints_is_read_green_red_and_with_spaces_in_the_name():
    got = G.parse(GREEN + RED)
    assert got == {"deadcheck 래칫": (True, 28.9), "봉인 덮임": (True, 2.1), "문서 말투": (False, 5.0)}


def test_a_text_that_is_not_the_hook_output_reads_as_nothing():
    """정상 입력은 조용하다 — 훅 출력이 아닌 글에서 게이트를 만들어 내지 않는다(위 시험의 합성 결함 쪽과 짝)."""
    assert not G.parse("아무 줄도 아니다\n✓ 이름만 있고 초가 없다\n")


def test_the_hook_print_format_and_the_regex_agree():
    """훅의 `printf '  ✓ %-22s %5.1f초\\n'` 서식이 이 정규식에 읽히는가 — 서식이 바뀌면 여기서 먼저 운다."""
    line = f"  ✓ {'이름이 스물두 글자를 넘는 게이트 이름입니다':<22} {3.0:5.1f}초"
    assert G.parse(line) == {"이름이 스물두 글자를 넘는 게이트 이름입니다": (True, 3.0)}
    assert 'printf \'  ✓ %-22s %5.1f초\\n\'' in G.HOOK.read_text(encoding="utf-8"), "훅의 서식이 바뀌었다 — 읽는 정규식을 같이 고친다"


def test_the_median_of_the_runs_is_taken_per_gate():
    runs = [{"a": (True, 10.0), "b": (True, 1.0)}, {"a": (True, 30.0), "b": (True, 2.0)}, {"a": (True, 20.0), "b": (True, 3.0)}]
    assert G.merge(runs, ["a", "b"]) == {"a": 20.0, "b": 2.0}


def test_a_red_gate_in_any_run_refuses_to_write():
    runs = [{"a": (True, 10.0)}, {"a": (False, 1.0)}]
    res = G.merge(runs, ["a"])
    assert isinstance(res, str) and "빨간 게이트" in res and "a" in res


def test_a_gate_whose_line_was_not_read_refuses_to_write():
    """빈 열은 거짓이다 — 일부만 쓰지 않는다."""
    res = G.merge([{"a": (True, 1.0)}], ["a", "b"])
    assert isinstance(res, str) and "b" in res


def test_write_changes_only_the_third_column_and_is_idempotent(tmp_path):
    g = tmp_path / "g.gates"
    original = "# 주석 한 줄\n\n이름 하나\tuv run python tools/a.py --x\n이름 둘\tuv run python tools/b.py\t99.9\n"
    g.write_text(original, encoding="utf-8")
    G.write({"이름 하나": 3.0, "이름 둘": 4.5}, g)
    once = g.read_text(encoding="utf-8")
    assert once == "# 주석 한 줄\n\n이름 하나\tuv run python tools/a.py --x\t3.0\n이름 둘\tuv run python tools/b.py\t4.5\n"
    G.write({"이름 하나": 3.0, "이름 둘": 4.5}, g)
    assert g.read_text(encoding="utf-8") == once                     # 두 번 써도 같다


def test_the_real_gate_file_names_are_the_ones_the_tool_expects():
    assert G.names() and all(n.strip() for n in G.names())
