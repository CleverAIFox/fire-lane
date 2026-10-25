"""PLAN §10-5 의 판 배분(A~F · 0판 없음)이 **기계가 읽는 표**이고 §1 의 행과 어긋나지 않는다.  (Zm23 · Zm28)

감사가 손으로 센 수가 틀린 것을 지적했다(「열린 59」가 실제 45). 그래서 배분은 표 하나로 두고 이 시험이 셈을 한다 —
① 배분 표의 행 번호 + 외부 회신 + 미배분이 §1 의 행 집합과 **정확히 같다**(빠짐 · 겹침 · 유령 번호 없음)
② 전건 관계가 실재하는 구획만 가리키고 **순환하지 않는다**
③ 재잠금 횟수가 선언대로다(A 1회 · B 2회 · 나머지 0)
④ (Zm28) 0판이 없다 · A 의 전건은 없음 · F 의 전건은 E · A 행이 완료/남은/보류를 가른다 · F 행이 「판정 불변」과 「E 를 다시 돈다」를 못 박는다

IN    docs/PLAN.md
OUT   없음 (검사)
PARAM 없음
밖    **배분이 옳은가**는 안 본다 — 사람이 정한 구조를 그대로 읽는다. 행이 닫혔는지도 안 본다(닫힌 행은 §1 에서 지워진다).
"""
from __future__ import annotations

import re
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "docs" / "PLAN.md"
BEGIN, END = "<!--plan-blocks-->", "<!--/plan-blocks-->"


def section1_rows() -> set[int]:
    text = PLAN.read_text(encoding="utf-8").split("\n")
    inside, out = False, set()
    for ln in text:
        if ln.startswith("## 1. "):
            inside = True
            continue
        if ln.startswith("## 2. "):
            break
        if inside and (m := re.match(r"^\| *(\d+) *\|", ln)):
            out.add(int(m.group(1)))
    return out


def blocks() -> dict[str, dict]:
    t = PLAN.read_text(encoding="utf-8")
    assert BEGIN in t and END in t, "PLAN 에 판 배분 표(`<!--plan-blocks-->`)가 없다"
    body = t.split(BEGIN, 1)[1].split(END, 1)[0]
    out: dict[str, dict] = {}
    for ln in body.split("\n"):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 6 and re.fullmatch(r"[A-F]|0|외부|미배분", c[0]):
            rows = [int(x) for x in re.findall(r"#(\d+)", c[2])]
            pre = [] if c[3] in ("없음", "—") else [x.strip() for x in re.split(r"[ ,·]+", c[3]) if x.strip()]
            relock = 0 if c[4] in ("0", "없음") else int(re.match(r"(\d+)", c[4]).group(1))
            out[c[0]] = {"name": c[1], "rows": rows, "pre": pre, "relock": relock, "cells": c}
    return out


def test_the_table_partitions_section_one_exactly() -> None:
    b = blocks()
    claimed = [r for v in b.values() for r in v["rows"]]
    dup = sorted({r for r in claimed if claimed.count(r) > 1})
    assert not dup, f"두 구획에 든 행: {dup}"
    live, said = section1_rows(), set(claimed)
    assert said == live, f"표에만 있는 번호 {sorted(said - live)} · §1 에만 있는 번호 {sorted(live - said)}"


def test_the_counts_are_derived_not_typed() -> None:
    b = blocks()
    total = sum(len(v["rows"]) for v in b.values())
    assert total == len(section1_rows()), f"구획 합 {total} ≠ §1 행 수 {len(section1_rows())}"


def test_prerequisites_exist_and_are_acyclic() -> None:
    b = blocks()
    names = set(b)
    for k, v in b.items():
        bad = [p for p in v["pre"] if p not in names]
        assert not bad, f"{k} 의 전건이 없는 구획이다: {bad}"
    seen: set[str] = set()

    def walk(k: str, stack: tuple[str, ...]) -> None:
        assert k not in stack, f"전건이 순환한다: {' → '.join((*stack, k))}"
        if k in seen:
            return
        for p in b[k]["pre"]:
            walk(p, (*stack, k))
        seen.add(k)

    for k in b:
        walk(k, ())


def test_relock_counts_are_as_declared() -> None:
    b = blocks()
    assert {k: v["relock"] for k, v in b.items() if k in "ABCDEF"} == {"A": 1, "B": 2, "C": 0, "D": 0, "E": 0, "F": 0}


def test_there_is_no_block_zero() -> None:
    """0판은 없어졌다 — 표에 다시 들어오면 A 의 전건이 현장 실측으로 되돌아간다(DECISIONS §573)."""
    assert "0" not in blocks()


def test_the_order_is_a_first_and_f_last() -> None:
    b = blocks()
    assert b["A"]["pre"] == [], "A 의 전건은 없음이다"
    assert b["F"]["pre"] == ["E"], "F 의 전건은 E 다"
    assert b["B"]["pre"] == ["A"] and b["C"]["pre"] == ["A"] and b["D"]["pre"] == ["B"] and b["E"]["pre"] == ["D"]
    # F 는 아무 구획의 전건도 아니다 — 맨 뒤다
    assert not [k for k, v in b.items() if "F" in v["pre"]]


def _a_groups() -> dict[str, list[int] | str]:
    """A 행 칸을 「완료 … · 남은 … · 보류 …」 세 토막으로 가른다."""
    cell = blocks()["A"]["cells"][2]
    out: dict[str, list[int] | str] = {}
    for part in (x.strip() for x in cell.split("·")):
        for tag in ("완료", "남은", "보류"):
            if part.startswith(tag):
                out[tag] = part if tag == "보류" else [int(x) for x in re.findall(r"#(\d+)", part)]
    return out


def test_a_separates_done_remaining_and_held() -> None:
    g = _a_groups()
    assert g["완료"] == [53, 17], "완료는 #53 #17 이다(Zm19 가 실행했다)"
    # ★ 2026-10-26 (Zm48 · DECISIONS §587). `#11` 은 코드 변경 없이 닫혔다(폴리곤이 원래 거기를 안 그렸다) — 남은 것은 다섯이다.
    assert len(g["남은"]) == 5 and sorted(g["남은"]) == [4, 70, 77, 173, 179], "남은 다섯"
    assert "[12]" in g["보류"], "보류는 규칙 [12] 다"
    assert sorted(g["완료"] + g["남은"]) == sorted(blocks()["A"]["rows"]), "A 의 행이 세 토막과 같다"


def test_f_is_decision_neutral_and_names_the_condition_for_going_back_to_e() -> None:
    f = blocks()["F"]["cells"][5]
    assert "판정 불변" in blocks()["F"]["name"] and "판정 불변" in f, "F 는 판정 불변이어야 한다"
    assert "E 를 다시" in f, "판정을 바꿔야 할 만큼 심각하면 E 를 다시 돈다는 조건이 F 행에 있어야 한다"
    assert "한계" in f and "신뢰도" in f, "실측 결과는 한계 · 신뢰도 절에 적는다"


def test_17_is_written_on_both_sides_a_and_f() -> None:
    """`#17` 이 0판 없이 실행됐고 F 에서 사후 검증한다는 것을 **양쪽에** 적는다(숨기지 않는다)."""
    b = blocks()
    assert "#17" in b["A"]["cells"][5] and "F" in b["A"]["cells"][5] and "실측 없이" in b["A"]["cells"][5]
    assert "#17" in b["F"]["cells"][5] and "사후" in b["F"]["cells"][5]
