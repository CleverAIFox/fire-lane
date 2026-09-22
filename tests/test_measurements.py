"""
test_measurements.py — 측정 대장(docs/MEASUREMENTS.yaml)이 형식을 지키는가 (PLAN §13-4 가드 6).

2026-09-22 (DECISIONS §218-6). 측정은 강제할 수 없어서 **재기 전에** 물음 · 판정 기준 · 봉인 자리를
적게 한다. 여기서 보는 것 —
  ① 항목마다 question · criterion · sealed_log · metrics 가 비어 있지 않다
  ② plan_row 가 적혀 있으면 PLAN §1 에 그 행이 실재한다(행이 지워졌는데 측정이 남으면 운다)
  ③ 오염된 지표를 criterion · metrics 에 되쓰지 않는다
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _doc():
    return yaml.safe_load((ROOT / "docs" / "MEASUREMENTS.yaml").read_text(encoding="utf-8"))


def _plan_rows() -> set[int]:
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    s1 = plan[plan.index("\n## 1."):plan.index("\n## 2.")]
    return {int(n) for n in re.findall(r"^\| (\d+) \|", s1, re.M)}


def test_entries_are_complete():
    d = _doc()
    ids = [m["id"] for m in d["measurements"]]
    assert len(ids) == len(set(ids)), "측정 id 가 겹친다"
    for m in d["measurements"]:
        for k in ("question", "criterion", "sealed_log"):
            assert str(m.get(k) or "").strip(), f"{m['id']}: {k} 가 비었다 — 재기 전에 적는다"
        assert m.get("metrics"), f"{m['id']}: metrics 가 비었다"


def test_plan_rows_exist():
    rows = _plan_rows()
    gone = [(m["id"], m["plan_row"]) for m in _doc()["measurements"]
            if m.get("plan_row") is not None and m["plan_row"] not in rows]
    assert not gone, f"PLAN §1 에 없는 행을 잇는다: {gone}"


def test_contaminated_metrics_are_not_gates():
    d = _doc()
    bad = [(m["id"], k) for m in d["measurements"] for k in d["contaminated"]
           if k in m.get("metrics", []) or k in str(m.get("criterion", ""))]
    assert not bad, f"오염된 지표를 게이트로 되쓴다: {bad}"
