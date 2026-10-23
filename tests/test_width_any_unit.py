#!/usr/bin/env python3
"""
test_width_any_unit.py — 폭 계측 칸을 만드는 **순수 함수**를 이름으로 부른다 (`width_any` · `_run_lengths`).

── 왜 ──────────────────────────────────────────────────────────
`segments.width_any` 는 표본 행에서 소스 무관 최솟값 · 대칭폭 최솟값 · 폴리곤 수 · 선택 사유를 만든다. `_run_lengths` 는 소스 런의 길이다.
판정 규칙 [8] · [9] 가 이 값을 읽으므로 **합성 입력으로 정의대로 나오는지** 여기서 민다(실물 산출물에만 기대면 산출물이 낡을 때 같이 낡는다).

IN    firelane.segments (width_any · _run_lengths)
OUT   없음 (검사)
PARAM 없음
밖    **폭이 참인가는 안 본다** — 합성 행에서 정의대로 계산되는가만 본다.
"""
from __future__ import annotations

from firelane.segments import CONFLICT_FOLD_M, _run_lengths, width_any


def _row(s, w, src="ngii1k", v3=None, left=None, right=None, poly=None, inside=True):
    r = {"s": s, "w": w, "src": src, "drop": None, "v3": v3 or (w, None, None)}
    if left is not None:
        r.update(left=left, right=right, poly=poly, inside=inside, rule="carve")
    return r


def test_any_min_comes_from_every_source_value_not_the_adopted_one():
    rows = [_row(1.0, 9.0, v3=(9.0, None, 2.0), left=4.5, right=4.5, poly="ngii1k:1"),
            _row(3.0, 8.0, v3=(8.0, None, 7.5), left=4.0, right=4.0, poly="ngii1k:1")]
    out = width_any(rows, 8.0, "ngii1k", {"ngii1k": 1.0})
    assert out["width_min_any_m"] == 2.0 and out["width_min_any_src"] == "silpok" and out["width_min_any_s_m"] == 1.0
    assert out["width_source_conflict_m"] == 6.0          # 8.0 − 2.0


def test_conflict_below_fold_is_zero_and_missing_wmin_is_none():
    rows = [_row(1.0, 5.0, v3=(5.0, None, 4.97), left=2.5, right=2.5)]
    assert width_any(rows, 5.0, "ngii1k", {"ngii1k": 1.0})["width_source_conflict_m"] == 0.0     # 0.03 < CONFLICT_FOLD_M
    assert CONFLICT_FOLD_M == 0.05
    assert width_any(rows, None, None, None)["width_source_conflict_m"] is None
    assert "폭 미산출" in width_any(rows, None, None, None)["width_selection_reason"]


def test_symmetric_width_min_and_poly_count_and_subphys():
    rows = [_row(1.0, 6.0, left=0.2, right=5.8, poly="a"), _row(3.0, 0.8, left=0.4, right=0.4, poly="b")]
    out = width_any(rows, 0.8, "ngii1k", {"ngii1k": 1.0})
    assert out["width_min_sym_m"] == 0.4                   # 2·min(0.2,5.8)=0.4 · 2·min(0.4,0.4)=0.8
    assert out["n_poly"] == 2 and out["n_subphys"] == 1


def test_sample_index_is_the_min_sample_even_when_it_is_outside():
    """`inside = 0` 은 「남의 도로」가 아니라 「대표로 고르지 않은 폴리곤」이다(DECISIONS §546-2) — 좁은 값을 발행에서 빼지 않는다."""
    rows = [_row(1.0, 3.0, left=1.0, right=2.0, inside=False), _row(3.0, 4.0, left=2.0, right=2.0, inside=True)]
    assert width_any(rows, 3.0, "ngii1k", {"ngii1k": 1.0})["width_min_sample_idx"] == 0


def test_run_lengths_break_at_gaps_and_source_changes():
    rows = [_row(1, 5.0, "a"), _row(3, 5.0, "a"), _row(5, 5.0, "b"), {"s": 7, "w": None, "src": None, "drop": "xsec"},
            _row(9, 5.0, "b")]
    assert _run_lengths(rows) == [2, 2, 1, None, 1]
