#!/usr/bin/env python3
"""
test_ledger_contract.py — 대장 `contract:` 판정이 **손판과 한 건도 안 달라졌는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24 (PLAN §13 W6-1 닫힘 · DECISIONS §227). `src/firelane/contract.py` 의
  `required_cols` · `rows` · `scope_min` 판정을 손으로 짠 `if` 에서
  `pandera.DataFrameSchema` 로 옮겼다. W6-1 의 수용 조건이 **「판정 불변을
  증명해야 닫힌다」** 였다 — 계약은 판정 상류라 여기서 한 건이 달라지면
  `ingest` 가 받는 행이 달라지고, 그러면 구간 1,281 이 움직인다.

★ 그래서 **옛 판정을 이 파일 안에 남긴다**(`hand_verdict`). 옮긴 코드와
  나란히 돌려 경계에서 한 글자도 안 달라졌음을 본다. 「같게 짰다」는
  주장이 아니라 **같은 입력에 같은 답**을 매 실행 확인한다.

  옛 판은 이랬다 —
      lo, hi = want * (1 - tol), want * (1 + tol)
      if not (lo <= len(d) <= hi):          ← **닫힌 구간**
      if n < smin:                          ← 미만일 때만 실패

IN    src/firelane/contract.py
OUT   없음 (검사)
밖    **파일 인코딩 · zip 레이어 · 컬럼 추가 경고는 안 본다.** 셋은 Pandera 로
      안 옮겼고 `contract.py` 머리말의 `밖` 칸이 그 이유를 적는다. 여기서
      드는 것은 **옮긴 세 판정**뿐이다. 실물 `sources.yaml` 36개 블록에
      대해 도는 것은 `verify.sh` 의 「대장 선언 ↔ raw 실물」 단계다(레이크 필요).
"""
from __future__ import annotations

import pandas as pd
import pytest

from firelane.contract import frame_schema, schema_failures


def hand_verdict(c: dict, d: pd.DataFrame, scope_n: int | None) -> set[str]:
    """★ 2026-09-24 **이전**의 판정. 옮기기 전 `check_one` 에서 그대로 떼왔다."""
    bad: set[str] = set()
    for col in (c.get("required_cols") or []):
        if col not in d.columns:
            bad.add("컬럼")
    want = c.get("rows")
    if want is not None:
        tol = float(c.get("rows_tolerance", 0.30))
        lo, hi = want * (1 - tol), want * (1 + tol)
        if not (lo <= len(d) <= hi):
            bad.add("건수")
    smin = c.get("scope_min")
    if smin is not None and scope_n is not None and scope_n < smin:
        bad.add("스코프")
    return bad


def new_verdict(c: dict, d: pd.DataFrame, scope_n: int | None) -> set[str]:
    got = set()
    for line in schema_failures(frame_schema(c, scope_n), d):
        if line.startswith("컬럼 소실"):
            got.add("컬럼")
        elif line.startswith("건수"):
            got.add("건수")
        elif line.startswith("스코프"):
            got.add("스코프")
        else:  # pragma: no cover - 새 갈래가 생기면 여기서 터뜨린다
            raise AssertionError(f"분류 못 하는 실패 줄: {line}")
    return got


def frame(n: int, cols=("a", "b")) -> pd.DataFrame:
    return pd.DataFrame({c: ["x"] * n for c in cols})


# ── 건수 경계 ───────────────────────────────────────────────────
@pytest.mark.parametrize("n", [0, 1, 69, 70, 71, 99, 100, 101, 129, 130, 131, 500])
@pytest.mark.parametrize("tol", [None, 0.0, 0.1, 0.3, 0.5])
def test_row_count_boundary_is_unchanged(n, tol):
    c = {"rows": 100}
    if tol is not None:
        c["rows_tolerance"] = tol
    d = frame(n)
    assert hand_verdict(c, d, None) == new_verdict(c, d, None), (
        f"건수 판정이 달라졌다 — n={n} tol={tol}")


# ── 스코프 하한 경계 ────────────────────────────────────────────
@pytest.mark.parametrize("scope_n", [0, 1, 4, 5, 6, 100])
@pytest.mark.parametrize("smin", [0, 1, 5])
def test_scope_min_boundary_is_unchanged(scope_n, smin):
    c = {"scope_min": smin}
    d = frame(3)
    assert hand_verdict(c, d, scope_n) == new_verdict(c, d, scope_n), (
        f"스코프 판정이 달라졌다 — n={scope_n} min={smin}")


# ── 컬럼 소실 ───────────────────────────────────────────────────
@pytest.mark.parametrize("need", [[], ["a"], ["a", "b"], ["a", "zz"], ["zz"],
                                  ["zz", "yy"]])
def test_required_columns_are_unchanged(need):
    c = {"required_cols": need}
    d = frame(3)
    assert hand_verdict(c, d, None) == new_verdict(c, d, None), (
        f"컬럼 판정이 달라졌다 — {need}")


# ── 셋이 함께 ───────────────────────────────────────────────────
@pytest.mark.parametrize("n,scope_n", [(3, 0), (3, 9), (500, 0), (100, 9)])
def test_all_three_together_are_unchanged(n, scope_n):
    c = {"required_cols": ["a", "zz"], "rows": 100, "scope_min": 5}
    d = frame(n)
    assert hand_verdict(c, d, scope_n) == new_verdict(c, d, scope_n)


# ── 빈 그물이 아닌가 ────────────────────────────────────────────
def test_the_probe_actually_fails_somewhere():
    """0건이 청결인지 죽음인지 가른다 — 세 갈래가 **실제로 운다.**"""
    d = frame(3)
    assert new_verdict({"required_cols": ["zz"]}, d, None) == {"컬럼"}
    assert new_verdict({"rows": 100}, d, None) == {"건수"}
    assert new_verdict({"scope_min": 5}, d, 0) == {"스코프"}
    assert new_verdict({}, d, None) == set()


def test_missing_column_names_survive_into_the_message():
    """어느 컬럼이 없는지 메시지에 남는가. 안 남으면 사람이 못 고친다."""
    lines = schema_failures(frame_schema({"required_cols": ["zz", "yy"]}), frame(3))
    assert lines and "zz" in lines[0] and "yy" in lines[0], lines


def test_schema_is_not_strict():
    """컬럼 **추가**는 스키마가 실패로 안 본다 — 경고는 `check_one` 이 낸다."""
    d = frame(3, cols=("a", "b", "c"))
    assert new_verdict({"required_cols": ["a"]}, d, None) == set()
