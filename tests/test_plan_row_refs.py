"""PLAN 안의 `#N` 이 **실체 없는 행**을 맨몸으로 가리키지 않는가 — `tools/plan_renumber.py::unresolved_row_refs`.  (PLAN #208)

★ 양성 대조 — 같은 합성 PLAN 에서 죽은 번호를 맨몸으로 적으면 걸리고 · 표시(`닫힘` · `결번`)를 달면 · 산 행이면 통과한다.
  **줄 단위**(사람이 골랐다)라서 생기는 느슨함 — 긴 행에 `닫힘` 이 하나라도 있으면 다른 죽은 번호도 통과한다 — 도 **시험으로 못 박아 숨기지 않는다**.

밖    **살아 있는 행의 안쪽**(`#69` 의 「`#5` 질의 ④」 — 그 행에 ④ 가 없다)은 안 본다 — 죽은 번호가 아니다. 사람이 읽는다(PLAN #208 행).
      `§N` 쪽은 `tests/test_declaration_sync.py` 가 든다.
"""
from __future__ import annotations

from pathlib import Path

import plan_renumber as P

ROOT = Path(__file__).resolve().parents[1]
HEAD = "## 1. 남은 일\n\n| 1 | a |\n| 2 | b |\n\n### 끝\n\n"     # 산 행 둘(#1 · #2)


def refs(body: str) -> list[str]:
    return P.unresolved_row_refs(HEAD + body)


def test_a_bare_dead_number_is_caught_with_its_line():
    assert refs("그 칸을 채울 원천이 #3 이다\n") == ["L8 #3"]


def test_a_mark_on_the_line_passes():
    assert refs("`#3`(닫힘) 에서 옮겼다\n") == []
    assert refs("넷(#8 · #74 — 전부 결번)\n") == []
    assert refs("그 행은 닫혀 있다 — #9\n") == []


def test_a_live_row_passes_and_so_do_section_run_guides():
    assert refs("전건 — #1 · #2\n") == []
    assert refs("### 8-7. 위생 → §1 #100 · #103\n") == []          # `§1 #…` 길잡이는 이 판이 안 본다(`_guides` 소관)


def test_line_level_looseness_is_real_and_pinned():
    """한 줄에 표시가 하나 있으면 같은 줄의 다른 죽은 번호도 통과한다. 줄 단위의 대가 — 숨기지 않고 못 박는다."""
    assert refs("#3(닫힘) 와 #9 가 한 줄\n") == []
    assert refs("#3 와 #9 가 한 줄\n") == ["L8 #3", "L8 #9"]       # 표시가 아예 없으면 둘 다 걸린다


def test_the_real_plan_has_no_bare_dead_row_reference():
    text = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    assert P.unresolved_row_refs(text) == []


def test_the_prepush_runs_the_tool_that_holds_the_judge():
    gates = (ROOT / ".githooks" / "pre-push.gates").read_text(encoding="utf-8")
    assert "tools/plan_renumber.py" in gates
