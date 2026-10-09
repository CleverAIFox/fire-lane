"""
test_write_stable.py — **휘발 칸 말고** 달라졌을 때만 쓰는가.
  (PLAN · DECISIONS §445)

★ 왜 이 시험이 있나 — 봉인 셋(`meta.json` · `eval.json` · `nfa_compare.json`)이
  매 실행 `as_of` · `git_sha` 만 바뀌어 **추적 파일이 더럽다**로 열차를 세웠다.
  `git_sha` 는 **직전 커밋**을 적으므로 커밋하면 또 바뀐다 — 도달할 수 없는
  고정점이다. 그 축이 여기서 양방향으로 운다.

밖    **무엇이 휘발인가는 안 본다** — 목록은 `firelane.hashing.VOLATILE` 이
      들고, 이 시험은 **그 목록대로 움직이는가**만 본다.
"""
from __future__ import annotations

import json

from firelane.hashing import VOLATILE, without, write_stable


def test_it_writes_when_the_file_is_new(tmp_path):
    p = tmp_path / "a.json"
    assert write_stable(p, {"n": 1}) is True
    assert json.loads(p.read_text(encoding="utf-8")) == {"n": 1}


def test_it_does_not_write_when_only_the_clock_moved(tmp_path):
    """정상 입력 — 수가 같으면 **조용하다.** 옛 시각이 남는다(그 수가 그때 것이다)."""
    p = tmp_path / "a.json"
    write_stable(p, {"as_of": "1", "git_sha": "aaa", "n": 1})
    assert write_stable(p, {"as_of": "2", "git_sha": "bbb", "n": 1}) is False
    got = json.loads(p.read_text(encoding="utf-8"))
    assert got["as_of"] == "1" and got["git_sha"] == "aaa"


def test_it_writes_when_a_real_number_moved(tmp_path):
    """합성 결함 — 수가 바뀌면 **운다.** 안 울면 봉인이 거짓을 들고 있게 된다."""
    p = tmp_path / "a.json"
    write_stable(p, {"as_of": "1", "n": 1})
    assert write_stable(p, {"as_of": "1", "n": 2}) is True
    assert json.loads(p.read_text(encoding="utf-8"))["n"] == 2


def test_it_writes_over_a_broken_file(tmp_path):
    """깨진 파일을 **조용히 두지 않는다** — 두면 영원히 남는다."""
    p = tmp_path / "a.json"
    p.write_text("{ 깨짐", encoding="utf-8")
    assert write_stable(p, {"n": 1}) is True


def test_it_only_strips_the_top_level(tmp_path):
    """아래쪽의 같은 이름은 **내용이다.** 떼면 진짜 변화를 못 본다."""
    a = {"as_of": "1", "rows": [{"git_sha": "x"}]}
    b = {"as_of": "2", "rows": [{"git_sha": "y"}]}
    assert without(a) != without(b), "중첩까지 떼면 행의 변화를 흘린다"
    p = tmp_path / "a.json"
    write_stable(p, a)
    assert write_stable(p, b) is True


def test_the_list_names_the_two_that_bit(tmp_path):
    """★ 빈 그물 금지 — 목록이 비면 모든 축이 조용히 통과한다."""
    assert {"as_of", "git_sha", "frozen_at"} <= set(VOLATILE), VOLATILE
