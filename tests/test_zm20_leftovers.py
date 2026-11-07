"""요청서 N2 · N3 · N7 의 **발행본 시험** — 규칙 [8]~[11] 의 합이 맞고, 거둔 구간이 사유를 갖고, [8] 이 [10] 에 포함된다.  (Zm23)

Zm20 이 문구 · 태그 · 주석은 고쳤으나 이 세 시험은 안 넣었다(요청서 「확인」 칸). 여기서 넣는다.

IN    web/data/segments.geojson · src/firelane/seg/classify.py · tools/survey_queue.py
OUT   없음 (검사)
PARAM 없음
밖    **규칙이 옳은가**는 안 본다 — 발행본이 규칙대로 설명되는지, 포함 관계가 고정돼 있는지만 본다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import survey_queue as sq

from firelane.seg.classify import CLEAR_M, SPREAD_MAX, classify
from firelane.seg.params import TRUCK

SEG = Path(__file__).resolve().parents[1] / "web/data/segments.geojson"


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    if not SEG.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    return [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]


def _rule_hits(p: dict) -> list[int]:
    hits = []
    if p["width_min_any_m"] is not None and p["width_min_any_m"] < TRUCK:
        hits.append(8)
    if p["width_min_sym_m"] is not None and p["width_min_sym_m"] < TRUCK:
        hits.append(9)
    if (p["width_min_any_m"] is not None and p["width_min_any_m"] < CLEAR_M) or (p["clear_med_m"] is not None and p["clear_med_m"] < CLEAR_M):
        hits.append(10)
    if p["width_max_m"] and p["width_min_m"] and p["width_max_m"] / p["width_min_m"] >= SPREAD_MAX:
        hits.append(11)
    return hits


def test_needs_survey_is_explained_by_the_rules_and_the_split_sums(rows) -> None:
    """N2 — 발행본 needs_survey 의 사유를 규칙별로 센 합이 전체와 같고, 규칙 하나도 안 걸린 구간이 없다."""
    ns = [p for p in rows if p["unknown_reason"] == "needs_survey"]
    assert ns, "needs_survey 가 하나도 없다 — 이 시험이 빈 그물이다"
    first = {8: 0, 9: 0, 10: 0, 11: 0}
    for p in ns:
        h = _rule_hits(p)
        assert h, f"{p['seg_id']}: needs_survey 인데 규칙 [8]~[11] 어디에도 안 걸린다"
        first[h[0]] += 1
    assert sum(first.values()) == len(ns)
    only_source = sum(1 for p in ns if p["width_min_any_m"] is not None and p["width_min_any_m"] < TRUCK)
    assert only_source < len(ns) / 2, "소스 최솟값 < 3.0 이 needs_survey 의 대부분이라면 문구를 다시 읽어라"


def test_every_demoted_clear_has_at_least_one_survey_tag(rows) -> None:
    """N3 — 규칙 없이 `clear` 였는데 지금 `clear` 가 아닌 구간 전부가 태그를 하나 이상 갖는다."""
    demoted = [p for p in rows if p["verdict"] != "clear" and sq.was_clear(p)]
    assert len(demoted) > 100
    untagged = [p["seg_id"] for p in demoted if not ({"source_conflict", "sym_low", "median_low", "spread_high"} & set(sq.reasons_of(p, [])))]
    assert not untagged, f"태그가 없는 강등 구간: {untagged[:5]} ({len(untagged)}/{len(demoted)})"


def test_rule8_adds_nothing_beyond_rule10(rows) -> None:
    """N7 — [8] ⊂ [10]. [8] 이 걸리는 모든 구간은 [10] 도 걸리고 행선지가 같다 — 값을 [8] 선 바로 위로 올려도 판정이 같다."""
    assert TRUCK < CLEAR_M
    probe = TRUCK + 0.01
    assert probe < CLEAR_M
    n = both = 0
    for p in rows:
        if p["width_min_any_m"] is None or p["width_min_any_m"] >= TRUCK:
            continue
        n += 1
        kw = dict(wmin=p["width_min_m"], wmax=p["width_max_m"], nreg=p["n_sample"], road_bt=p["road_bt_m"], length_m=p["length_m"],
                  cctv_dist=p["cctv_dist_m"], wsym=p["width_min_sym_m"], clear_med=p["clear_med_m"])
        a, b = classify(**kw, wmin_any=p["width_min_any_m"]), classify(**kw, wmin_any=probe)
        assert a[0] == b[0], p["seg_id"]                                   # 판정은 [8] 이 없어도 같다
        if not (p["width_min_sym_m"] is not None and p["width_min_sym_m"] < TRUCK):
            assert a == b, p["seg_id"]                                     # 사유까지 같다 — [9] 가 같이 안 걸릴 때
        else:
            both += 1                                                      # [8] 과 [9] 가 같이 걸리면 [8] 이 **먼저**라 cv_reason 을 정한다
    assert n > 0, "소스 무관 최솟값 < 3.0 인 구간이 없다 — 이 시험이 아무것도 안 잰다"
    assert both <= n


def test_the_survey_tags_are_alive_on_synthetic_rows() -> None:
    """카나리아 — 태그 판별이 합성 입력에서 운다(강등된 구간)와 조용하다(멀쩡한 구간)를 둘 다 한다."""
    clean = dict(verdict="clear", width_min_m=9.0, width_max_m=None, n_sample=20, road_bt_m=8.0, length_m=50.0, cctv_dist_m=60.0,
                 width_min_any_m=9.0, width_min_sym_m=9.0, clear_med_m=12.0, n_subphys=0, nfa_access_listed=False, nfa_access_loose=None,
                 width_min_sample_idx=None)
    assert not sq.reasons_of(clean, [])
    assert sq.reasons_of({**clean, "verdict": "unknown", "clear_med_m": CLEAR_M - 1.0}, [])
