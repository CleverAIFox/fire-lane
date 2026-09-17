"""다판 소스의 vintage 선언 — 선언 안은 결함이 아니고, 선언 밖은 여전히 결함이다. (DECISIONS §179-5)

★ 2026-09-17. 단속이력 두 판(20240108 · 20250226)을 csv_table_multi 로 복귀하자 vintage_check 가 V1 · V2 로 울었다.
  이 도구는 "같은 stem 에 판이 둘이면 두 벌" 로만 봤다 — 기간별로 나뉘어 오는 표가 정상인 경우를 몰랐다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _vc():
    spec = importlib.util.spec_from_file_location("vc_multi", ROOT / "tools/vintage_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_declared_editions_are_not_defects():
    vc = _vc()
    d = frozenset({"20240108", "20250226"})
    assert vc.judge({"20240108", "20250226"}, "20250226", d) == ([], False)


def test_undeclared_edition_still_cries():
    vc = _vc()
    d = frozenset({"20240108", "20250226"})
    assert vc.judge({"20240108", "20250226", "20260101"}, "20250226", d) == (["20260101"], True)
    assert vc.judge({"20240108", "20250226"}, "20250226", frozenset()) == (["20240108"], True), "선언 없는 종전 규칙이 죽었다"


def test_vintage_selftest_is_green():
    assert _vc().selftest() == 0
