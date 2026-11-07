#!/usr/bin/env python3
"""
test_eccentricity.py — 편심 칸(`ecc_rel_*` · `ecc_cov`)은 **판정선을 못 넘는다.** 계산은 정의대로이고 발행본에 실려 나간다.

── 왜 이 시험인가 ──────────────────────────────────
① **판정선.** 임계는 사람이 정한다(머리말). 판정(`classify.py` · `segments.py` · `geom.py`)이 이 칸을 읽으면 운다.
② **폐포 밖.** `firelane.eccentricity` 는 판정 폐포 밖이다 — 골든 코드 지문을 안 건드린다.
③ **정의.** 중앙값·최댓값 ÷ 반폭 · 못 내면 null(0 이 아니다) · `ecc_cov` 의 분모는 표본점 전부.

IN    firelane.eccentricity · src/firelane/seg/classify.py · src/firelane/segments.py · web/data/segments.geojson
OUT   없음 (검사)
PARAM 없음
밖    **편심이 괴리의 원인인가는 안 본다**(DECISIONS §556 이 든다) — 정의대로 나오는지, 판정이 안 읽는지, 발행본에 실리는지만 본다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from firelane.eccentricity import NAMES, columns, load, relative

ROOT = Path(__file__).resolve().parent.parent


def test_the_judgment_never_reads_the_eccentricity():
    for f in ("src/firelane/seg/classify.py", "src/firelane/segments.py", "src/firelane/seg/geom.py"):
        src = (ROOT / f).read_text(encoding="utf-8")
        for n in NAMES:
            assert n not in src, f"{f} 가 {n} 를 읽는다 — 임계는 사람이 정한다(머리말)"
        assert "firelane.eccentricity" not in src and "import eccentricity" not in src, f"{f} 가 eccentricity 를 끌어온다 — 판정 폐포가 늘어난다"


def test_eccentricity_stays_outside_the_judgment_closure():
    from firelane.shardseal import code_closure
    assert not any("eccentricity" in str(x) for x in code_closure("firelane.segments")), "eccentricity.py 가 판정 폐포 안이다 — 골든 코드 지문이 움직인다"


def test_relative_is_median_and_max_of_abs_over_half_width():
    med, mx, cov = relative([1.0, -3.0, 2.0], 8.0)                # |ecc| = 1 · 3 · 2 → 중앙 2 · 최대 3 · 반폭 4
    assert (med, mx, cov) == (0.5, 0.75, 1.0)


def test_missing_values_lower_only_the_coverage_and_a_missing_ratio_is_null_not_zero():
    med, mx, cov = relative([2.0, None, None, 2.0], 4.0)
    assert (med, mx) == (1.0, 1.0) and cov == 0.5                  # 반폭 2, |ecc| 2 → 비율 1
    assert relative([None, None], 4.0) == (None, None, 0.0)         # ecc 가 하나도 없다 → null · 0 이 아니다
    assert relative([1.0], None)[:2] == (None, None) and relative([1.0], 0.0)[:2] == (None, None)
    assert relative([], 4.0) == (None, None, 0.0)


def test_columns_align_with_the_segments_and_unknown_segments_are_null(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("seg_id,s_m,ecc_m\nA,1,1.0\nA,3,-1.0\nA,5,\nB,1,0.5\n", encoding="utf-8")
    c = columns(["A", "B", "Z"], [4.0, 2.0, 4.0], load(p))
    assert c["ecc_rel_med_m"] == [0.5, 0.5, None] and c["ecc_rel_max_m"] == [0.5, 0.5, None]
    assert c["ecc_cov"] == [0.667, 1.0, 0.0]


def test_published_segments_carry_the_columns():
    p = ROOT / "web" / "data" / "segments.geojson"
    if not p.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 이 없다")
    feats = [f["properties"] for f in json.loads(p.read_text(encoding="utf-8"))["features"]]
    assert all(n in feats[0] for n in NAMES), "발행본에 ecc_* 칸이 없다 — publish 를 돌려라"
    assert all(0.0 <= f["ecc_cov"] <= 1.0 for f in feats)
    assert sum(1 for f in feats if f["ecc_rel_med_m"] is not None) >= 1000, "편심이 거의 안 나왔다 — 표본 CSV 를 확인해라"
