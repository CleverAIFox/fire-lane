"""PLAN 의 표 셋이 **같은 행을 같은 식으로** 가리키는가 — `§1`(행) · `§10-1`(배치 표) · `§10-5`(구획 표).  (DECISIONS §656)

`#195` 가 `§10-5` 에만 들어가고 `§10-1` 에 안 들어갔다. 배치 표는 `tools/planclose.py` 가 읽고 구획 표는 `tests/test_plan_blocks.py` 가 읽는데
**둘이 서로를 몰랐다** — 그래서 푸시 직전(`.githooks/pre-push.gates` · `verify.sh`)에서야 걸렸다. 같은 구조가 `#170` · `#171` 을 넉 달 놓쳤다(§520).
`planclose` 는 pytest 밖에서만 돌았다. 이 시험이 그 검사를 pytest 안으로 들여 **행을 세운 판에서 바로** 빨개지게 한다.

IN    docs/PLAN.md (`planclose` 의 파서를 그대로 쓴다 — 사본을 안 만든다)
OUT   없음 (검사)
PARAM 없음
밖    **판 배정이 옳은지는 안 본다.** 어느 판이 어느 행을 닫는지는 사람의 판단이다.
PLAN 본문  규칙 — §1 행 · §10-1 배치 표 · §10-5 구획 표가 같은 행을 같은 식으로 가리켜야 한다
"""
from __future__ import annotations

import planclose as P
import test_plan_blocks as B


def test_every_open_row_is_in_a_batch_or_declared_unclosable() -> None:
    assert not P.orphans(), f"§10-1 배치 표에 없는 열린 행: {sorted(P.orphans())} — 구획 표(§10-5)만 고치면 이렇게 된다"


def test_every_open_row_is_promised_unconditionally_by_some_batch() -> None:
    """조건부에만 걸린 행은 조건이 깨졌을 때 받는 판이 없다."""
    gap = P.promised() ^ (P.open_rows() - P.cannot_close())
    assert not gap, f"어느 판도 무조건 닫겠다고 안 한 행: {sorted(gap)}"


def test_declared_close_counts_match_the_rows_counted() -> None:
    bad = {k: v for k, v in P.claims().items() if v[0] != v[1]}
    assert not bad, f"닫는 수가 센 수와 다른 판: {bad}"


def test_the_batch_table_has_no_ghost_rows() -> None:
    assert not P.ghosts(), f"판이 드는데 §1 에 없는 행: {sorted(P.ghosts())}"


def test_the_two_tables_cover_the_same_open_rows() -> None:
    """구획 표(§10-5)가 든 행 = 배치 표(§10-1)가 든 행 + 못 닫는 행 + 외부 회신 — 어느 쪽이든 빠지면 이름을 댄다."""
    blocks = {r for v in B.blocks().values() for r in v["rows"]}
    batch = P._taken() & P.open_rows()
    covered = batch | (P.cannot_close() & P.open_rows())
    only_blocks = sorted(blocks - covered)
    only_batch = sorted(covered - blocks)
    assert not only_blocks, f"구획 표에만 있는 행: {only_blocks}"
    assert not only_batch, f"배치 표 · 못 닫는 표에만 있는 행: {only_batch}"


# ── 카나리아 — 구멍을 **만들어** 밀어 우는 것을 본다(빈 그물은 구멍이 없어도 초록이다) ──────────
_SYNTH = (
    "## 1. 일\n| 1 | a |\n| 2 | b |\n| 3 | c |\n### 1-27. 측정\n"
    "| 판 | 성질 | 전건 | 드는 행 | 닫는 수 |\n|---|---|---|---|---|\n"
    "| `Za` | x | 없다 | `#1` `#2` | 2 |\n"
    "**합 2.**\n"
    "**물리적으로 못 닫는 하나 — 그리고 왜**\n\n| 행 | 왜 |\n| `#3` 바깥 | 외부다 |\n\n---\n")


def test_the_checks_are_quiet_on_a_complete_synthetic_plan() -> None:
    assert not P.orphans(_SYNTH)
    assert P.promised(_SYNTH) == {1, 2}


def test_the_checks_cry_when_a_row_is_missing_from_the_batch_table() -> None:
    """`#195` 의 꼴: 행은 열려 있는데 배치 표의 「드는 행」에 없다."""
    hole = _SYNTH.replace("`#1` `#2` | 2 |", "`#1` | 1 |")
    assert P.orphans(hole) == {2}


def test_the_checks_cry_when_a_row_is_only_mentioned_not_promised() -> None:
    """조건부에만 걸린 행은 약속이 아니다 — 받는 판이 없다."""
    soft = _SYNTH.replace("`#1` `#2` | 2 |", "`#1` `#2`(조건부) | 1 |")
    assert 2 not in P.promised(soft)
    assert P.claims(soft)["Za"] == (1, 1)
