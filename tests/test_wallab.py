"""tools/wallab.py — 두 판의 갈림 · 측량 혼동표. 순수 함수만 문다(파이프라인 산출물을 읽지 않는다). (PLAN #53 · DECISIONS §709)

IN    합성 `segments.geojson` 꼴 입력(임시 파일 · 딕셔너리)
OUT   없음 (검사)
밖    **실제 산출물에서 측량을 붙이는 `survey_by_uid` 는 안 부른다** — 레이크 · 처리 산출물이 필요한 자리라 `tools/widthcross.py` 의 시험이 든다. **어느 판이 옳은가는 안 본다**(도구가 안 말한다).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import wallab as W


def _d(rows: dict[str, tuple[str, float | None]]) -> dict[str, dict]:
    return {u: {"verdict": v, "width_max_m": m} for u, (v, m) in rows.items()}


def test_transitions_count_only_changed_segments_and_refuse_different_sets() -> None:
    a = _d({"a": ("blocked", None), "b": ("clear", 9.0), "c": ("unknown", None)})
    b = _d({"a": ("unknown", 5.0), "b": ("clear", 9.0), "c": ("blocked", None)})
    assert W.transitions(a, b) == {("blocked", "unknown"): 1, ("unknown", "blocked"): 1}
    with pytest.raises(SystemExit, match="seg_uid 집합이 다르다"):
        W.transitions(a, _d({"a": ("clear", 1.0)}))


def test_counts_report_the_missing_wmax_as_missing_not_as_zero() -> None:
    c, miss = W.counts(_d({"a": ("blocked", None), "b": ("clear", 9.0), "c": ("clear", None)}))
    assert c == {"blocked": 1, "clear": 2} and miss == 2


def test_survey_class_puts_unknown_survey_in_its_own_bucket() -> None:
    assert [W.survey_class(x) for x in (None, 2.9, 3.0, 5.9, 6.0)] == ["측량 없음", "측량<3", "측량3~6", "측량3~6", "측량≥6"]


def test_moved_names_the_survey_class_of_freed_and_newly_blocked_segments() -> None:
    base = _d({"a": ("blocked", None), "b": ("blocked", None), "c": ("unknown", None), "d": ("clear", 8.0)})
    cur = _d({"a": ("unknown", 5.0), "b": ("blocked", None), "c": ("blocked", None), "d": ("unknown", 30.0)})
    m = W.moved(base, cur, {"a": 2.0, "c": 2.5, "d": 12.0})
    assert m["풀림"] == (1, {"측량<3": 1}) and m["새로 막힘"] == (1, {"측량<3": 1})
    assert m["바뀐 전체"] == (3, {"측량<3": 2, "측량≥6": 1})


def test_confusion_counts_only_segments_with_a_survey_and_flags_clear_on_a_narrow_survey() -> None:
    d = _d({"a": ("clear", 9.0), "b": ("blocked", None), "c": ("blocked", None), "d": ("unknown", None)})
    cf = W.confusion(d, {"a": 2.0, "b": 2.0, "c": 4.0})            # d 는 측량이 없어 안 센다
    assert cf == {"측량<3": {"clear": 1, "blocked": 1}, "측량≥3": {"blocked": 1}}


def test_load_refuses_a_segment_without_seg_uid(tmp_path: Path) -> None:
    p = tmp_path / "s.geojson"
    p.write_text(json.dumps({"features": [{"properties": {"verdict": "clear"}}]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="seg_uid"):
        W.load(p)
