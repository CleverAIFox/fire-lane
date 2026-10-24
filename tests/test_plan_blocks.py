"""PLAN §10-5 의 판 배분(0 · A~E)이 **기계가 읽는 표**이고 §1 의 행과 어긋나지 않는다.  (Zm23)

감사가 손으로 센 수가 틀린 것을 지적했다(「열린 59」가 실제 45). 그래서 배분은 표 하나로 두고 이 시험이 셈을 한다 —
① 배분 표의 행 번호 + 외부 회신 + 미배분이 §1 의 행 집합과 **정확히 같다**(빠짐 · 겹침 · 유령 번호 없음)
② 전건 관계가 실재하는 구획만 가리키고 **순환하지 않는다**
③ 재잠금 횟수가 선언대로다(A 1회 · B 2회 · 나머지 0)

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
        if len(c) == 6 and re.fullmatch(r"[0A-E]|외부|미배분", c[0]):
            rows = [int(x) for x in re.findall(r"#(\d+)", c[2])]
            pre = [] if c[3] in ("없음", "—") else [x.strip() for x in re.split(r"[ ,·]+", c[3]) if x.strip()]
            relock = 0 if c[4] in ("0", "없음") else int(re.match(r"(\d+)", c[4]).group(1))
            out[c[0]] = {"name": c[1], "rows": rows, "pre": pre, "relock": relock}
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
    assert {k: v["relock"] for k, v in b.items() if k in "0ABCDE"} == {"0": 0, "A": 1, "B": 2, "C": 0, "D": 0, "E": 0}


def test_the_order_is_zero_then_a() -> None:
    b = blocks()
    assert b["A"]["pre"] == ["0"] and b["0"]["pre"] == [], "0판이 A 의 전건이다"
    assert "A" in b["B"]["pre"] and "A" in b["C"]["pre"] and "B" in b["D"]["pre"] and "D" in b["E"]["pre"]
