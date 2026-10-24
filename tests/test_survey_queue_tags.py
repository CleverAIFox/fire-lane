"""`survey_queue` 의 사유 태그가 규칙 [10] 의 중앙값 축과 [11] 폭 급변을 덮는다.  (감사 N3 · Zm20)

태그는 [8]~[10] 의 소스·대칭 축만 있었다 — Zm19 가 넓힌 두 갈래(내접원 중앙값 · 폭 급변)로
내려간 구간은 `was_clear` 인데 어느 태그에도 안 걸려 현장 대장에서 빠졌다.

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **태그 문턱이 옳은가**는 안 본다 — 문턱은 판정 규칙의 것이다. 어느 구간에 태그가 붙는지만 본다.
"""
from __future__ import annotations

import survey_queue as sq

from firelane.seg.classify import CLEAR_M, SPREAD_MAX

BASE = dict(seg_id="D1", seg_uid="u1", verdict="clear", width_min_m=9.0, width_max_m=None, n_sample=20,
            road_bt_m=8.0, length_m=50.0, cctv_dist_m=60.0, width_min_any_m=9.0, width_min_sym_m=9.0,
            clear_med_m=12.0, n_subphys=0, nfa_access_listed=False, nfa_access_loose=None,
            width_min_sample_idx=None, occ_pressure_rank=None, occ_pressure=None, in_emd=False)
ROWS = [{"w_m": "9.0", "src": "ngii1k", "w_rule": "carve", "s_m": "1.0"}]


def test_median_low_tags_a_demoted_clear() -> None:
    p = {**BASE, "verdict": "unknown", "clear_med_m": CLEAR_M - 0.5}
    assert "median_low" in sq.reasons_of(p, ROWS)


def test_median_low_ignores_a_segment_that_was_never_clear() -> None:
    p = {**BASE, "verdict": "blocked", "width_min_m": 2.0, "clear_med_m": CLEAR_M - 0.5, "road_bt_m": 2.0}
    assert not sq.reasons_of({**p, "road_bt_m": 2.0}, ROWS)


def test_spread_high_tags_a_demoted_clear() -> None:
    p = {**BASE, "verdict": "unknown", "width_min_m": 8.0, "width_max_m": 8.0 * SPREAD_MAX + 0.5}
    assert "spread_high" in sq.reasons_of(p, ROWS)


def test_spread_high_needs_wmax() -> None:
    """wmax 가 없으면 「균일하다」가 아니라 모른다 — 태그를 달지 않는다."""
    p = {**BASE, "verdict": "unknown", "width_max_m": None}
    assert not sq.reasons_of(p, ROWS)


def test_every_tag_has_a_surveyor_sentence() -> None:
    assert {"median_low", "spread_high"} <= set(sq.TAGS)


def test_selftest_is_alive() -> None:
    assert sq.selftest() == 0
