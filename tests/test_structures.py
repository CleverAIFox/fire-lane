#!/usr/bin/env python3
"""
test_structures.py — 입체 구조물 칸(`struct_kind` · `struct_dist_m`)은 **판정선을 못 넘는다.** 계산은 정의대로이고 발행본에 실려 나간다.

IN    firelane.structures · src/firelane/seg/classify.py · src/firelane/segments.py · web/data/segments.geojson
OUT   없음 (검사)
PARAM 없음
밖    **2D 가정이 깨지는가는 안 본다**(DECISIONS §563 이 든다) — 정의대로 나오는지, 판정이 안 읽는지, 발행본에 실리는지만 본다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import LineString, box

from firelane.structures import KINDS, NAMES, RADIUS_M, columns, nearest

ROOT = Path(__file__).resolve().parent.parent


def test_the_judgment_never_reads_the_structure_columns():
    for f in ("src/firelane/seg/classify.py", "src/firelane/segments.py", "src/firelane/seg/geom.py"):
        src = (ROOT / f).read_text(encoding="utf-8")
        for n in NAMES:
            assert n not in src, f"{f} 가 {n} 를 읽는다 — 이 칸은 진단이다(머리말)"
        assert "firelane.structures" not in src and "import structures" not in src, f"{f} 가 structures 를 끌어온다 — 판정 폐포가 늘어난다"


def test_structures_stays_outside_the_judgment_closure():
    from firelane.shardseal import code_closure
    assert not any("structures" in str(x) for x in code_closure("firelane.segments")), "structures.py 가 판정 폐포 안이다 — 골든 코드 지문이 움직인다"


def test_nearest_picks_the_closest_kind_within_the_radius_and_nothing_beyond():
    line = LineString([(0, 0), (10, 0)])
    layers = {"tunnel": [box(0, 30, 10, 40)], "bridge": [box(0, 10, 10, 20)], "overpass": []}
    assert nearest(line, layers) == ("교량", 10.0)                       # 터널 30m · 교량 10m → 가까운 교량
    assert nearest(line, {"tunnel": [box(0, RADIUS_M + 1, 10, RADIUS_M + 5)]}) == (None, None)   # 반경 밖은 없다
    assert nearest(line, {"bridge": [box(0, RADIUS_M, 10, RADIUS_M + 5)]}) == ("교량", RADIUS_M)   # 경계는 안이다
    assert nearest(line, {}) == (None, None)


def test_columns_align_with_the_lines():
    out = columns([LineString([(0, 0), (1, 0)]), LineString([(0, 500), (1, 500)])], {"tunnel": [box(0, 5, 1, 6)]})
    assert out["struct_kind"] == ["터널", None] and out["struct_dist_m"] == [5.0, None]
    assert [k for k, _ in KINDS] == ["tunnel", "overpass", "bridge"]       # 하천은 입체가 아니다 — 싣지 않는다


def test_published_segments_carry_the_columns():
    p = ROOT / "web" / "data" / "segments.geojson"
    if not p.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 이 없다")
    feats = [f["properties"] for f in json.loads(p.read_text(encoding="utf-8"))["features"]]
    assert all(n in feats[0] for n in NAMES), "발행본에 struct_* 칸이 없다 — publish 를 돌려라"
    assert all((f["struct_kind"] is None) == (f["struct_dist_m"] is None) for f in feats)
    assert all(f["struct_dist_m"] is None or 0.0 <= f["struct_dist_m"] <= RADIUS_M for f in feats)
