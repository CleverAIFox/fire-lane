#!/usr/bin/env python3
"""
test_clearance.py — 내접원 칸(`clear_*`)은 **판정선을 못 넘는다.** 계산은 정의대로이고 발행본에 실려 있다. (Zm7 · DECISIONS §549)

── 왜 이 시험인가 ──────────────────────────────────────────────
① **판정선.** `src/firelane/seg/classify.py`(와 `segments.py`)가 `clear_min_m` · `clear_med_m` · `clear_max_m` · `clear_src` · `clear_cov` 를 읽으면 실패한다.
   사유 — 현장 16점 대조로 축은 단순 내접원(R=0)으로 좁혀졌으나 **대표값을 min 으로 할지 med 로 할지 아직 정하지 않았다.** 동계천로95번길에서 실측 3.2m 인 목을 내접원 대표값이 6.32m(2.0배)로 냈다 —
   대표값으로는 최악 지점을 못 잡는다. 판정은 사람이 현장 측정을 더 모은 뒤 정한다. 그 전에 판정이 이 칸을 읽으면 정하지 않은 것이 정해진다.
② **폐포 밖.** `firelane.clearance` 는 판정 폐포(`segments.py` 가 끌어오는 파일) 밖이다 — 골든 코드 지문을 안 건드린다.
③ **정의.** 내접원 지름 = 2 × 점에서 도로 경계까지의 거리 · 안 덮이는 표본은 min·med·max 에 안 들어가고 `clear_cov` 로만 남는다.

IN    firelane.clearance · src/firelane/seg/classify.py · src/firelane/segments.py · web/data/segments.geojson
OUT   없음 (검사)
PARAM 없음
밖    **내접원이 참인가는 안 본다** — 합성 기하에서 정의대로 나오는지, 판정이 안 읽는지, 발행본에 실렸는지만 본다.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString, box

from firelane.clearance import columns, inscribed, robust_union, sample_positions

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("clear_min_m", "clear_med_m", "clear_max_m", "clear_src", "clear_cov")


def test_the_judgment_reads_only_the_median_of_the_inscribed_circle():
    """Zm19(DECISIONS §564) 부터 판정이 내접원을 읽는다 — **중앙값 하나만**이다. `clear_min` · `clear_max` 는 `2·min(좌,우)` 꼴이라
    중심선 편심에 노출돼 판정에 안 쓴다(제봉로 DM00115: 법선 26.53 · c_med 23.80 · 대장 30.0 으로 셋이 맞는데 c_min 만 1.15).
    이전 시험(「판정이 `clear_*` 를 읽으면 운다」)은 대표값을 정하기 전의 약속이었고, 사람이 `clear_med_m` 으로 정했다."""
    cls = (ROOT / "src/firelane/seg/classify.py").read_text(encoding="utf-8")
    assert "clear_med" in cls, "판정이 clear_med 를 안 읽는다 — 규칙 [10] 확장이 빠졌다"
    for f in ("src/firelane/seg/classify.py", "src/firelane/segments.py", "src/firelane/seg/geom.py"):
        src = (ROOT / f).read_text(encoding="utf-8")
        body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))      # 주석은 이유를 적는다 — 코드만 본다
        for n in ("clear_min_m", "clear_max_m"):
            assert n not in body, f"{f} 가 {n} 를 읽는다 — 편심에 노출된 칸이다(위 사유)"


def test_clearance_is_now_inside_the_judgment_closure():
    from firelane.shardseal import code_closure
    assert any("clearance" in str(x) for x in code_closure("firelane.segments")), "clearance.py 가 폐포 밖이다 — 판정이 그것을 읽는다(§564)"


def test_diameter_is_twice_the_distance_to_the_boundary():
    road = box(-100, -2, 200, 2)                                # 폭 4m 직선로(끝이 멀어 끝 마개가 안 닿는다)
    d, cov = inscribed(LineString([(0, 0), (100, 0)]), road)    # 한가운데
    assert cov == 1.0 and np.allclose(d, 4.0)
    d, _ = inscribed(LineString([(0, 1), (100, 1)]), road)      # 경계에서 1m — 단순 내접원은 **가까운 쪽**을 본다(R=0)
    assert np.allclose(d, 2.0)


def test_uncovered_samples_are_nan_and_only_lower_the_coverage():
    road = box(-100, -2, 50, 2)                                 # 절반만 덮는다(x ≤ 50)
    d, cov = inscribed(LineString([(0, 0), (100, 0)]), road)
    assert 0.4 < cov < 0.6 and np.isnan(d).any() and np.nanmax(d) == pytest.approx(4.0)
    row = columns([LineString([(0, 0), (100, 0)])], road)[0]
    assert row["clear_max_m"] == 4.0 and row["clear_src"] == "road_rw" and 0.4 < row["clear_cov"] < 0.6
    none = columns([LineString([(0, 50), (100, 50)])], road)[0]          # 아예 안 덮는다 → null · cov 0
    assert none["clear_min_m"] is None and none["clear_src"] is None and none["clear_cov"] == 0.0


def test_sample_positions_match_the_width_engine():
    assert list(sample_positions(10.0)) == [1.0, 3.0, 5.0, 7.0]       # 양끝 1m 안쪽 · 2m 간격
    assert list(sample_positions(1.0)) == [0.25]                      # 짧으면 양끝 `0.25·길이` 안쪽 한 점(엔진 `_ts` 와 같다)


def test_robust_union_repairs_an_invalid_polygon_instead_of_returning_a_wrong_union():
    """무효 도형(나비매듭)을 그대로 합치면 예외가 아니라 **틀린 답**이 나온다 — `make_valid` 뒤에 합쳐 넓이가 맞아야 한다."""
    from shapely.geometry import Polygon
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])            # 자기교차 — 무효
    assert not bowtie.is_valid
    u = robust_union([bowtie, box(10, 0, 12, 2), None])
    assert u.is_valid and u.area == pytest.approx(2.0 + 4.0)      # 나비매듭 두 삼각형(각 1) + 상자 4, None 은 버린다


def test_published_segments_carry_the_columns():
    p = ROOT / "web" / "data" / "segments.geojson"
    if not p.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 이 없다")
    feats = [f["properties"] for f in json.loads(p.read_text(encoding="utf-8"))["features"]]
    assert all(n in feats[0] for n in NAMES), "발행본에 clear_* 칸이 없다 — publish 를 돌려라"
    assert all(0.0 <= f["clear_cov"] <= 1.0 for f in feats)
    assert sum(1 for f in feats if f["clear_min_m"] is not None) >= 1000, "내접원이 거의 안 나왔다 — 실폭도로가 안 덮는다"
