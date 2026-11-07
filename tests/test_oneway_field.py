#!/usr/bin/env python3
"""
test_oneway_field.py — **사람이 확인한 일방통행 방향 표**가 `ow` 로 옮겨지는 규칙.  (DECISIONS §653)

① `ow=2`(방향 모름)인 구간에만 읽는다 — 표준노드링크가 정한 ±1 과 양방향(0)은 안 덮는다
② 표의 `use` 가 「적용」인 행만 읽는다 — 「보류(충돌)」 · 「참고」는 안 읽는다
③ 방향은 부호가 아니라 **좌표**로 정한다 — 구간 형상이 뒤집혀도 맞고 두 끝이 다 안 붙으면(낡은 표) **모름으로 둔다**
④ 모름의 사유 수는 **남은 모름**의 수다 — 표가 정하면 그 사유에서 빠진다(분할이 깨지지 않는다)
⑤ 실제 표가 실제 구간에 붙는다(칸 · 어휘 · 근거 · `seg_uid` 실재 · 좌표가 구간 끝점)

IN    합성 구간 · 합성 표 · `data/field/oneway_direction_2611.csv` · `data/processed/segments.geojson`
OUT   통과/실패
밖    **표의 방향이 옳은가는 안 본다** — 사람이 네이버 자동차 길찾기로 양방향 대조한 값이고 그 근거가 표에 있다. 여기는 그것이 **옮겨지는 규칙**만 문다.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

pytest.importorskip("geopandas", reason="레이크 없이도 도는 검사지만 gpd 는 필요하다")

import geopandas as gpd
from shapely.geometry import LineString

from firelane import publish_rules as PN

ROOT = Path(__file__).resolve().parents[1]
CRS = "EPSG:5186"
COLS = ["seg_uid", "sheet_row", "road", "start", "end", "ow_now", "use", "from_x", "from_y", "to_x", "to_y", "fwd_m", "rev_m", "ratio", "evidence", "method", "checked", "source"]


def _gdf(lines, **cols):
    return gpd.GeoDataFrame({**cols, "geometry": lines}, crs=CRS)


def _seg(x0, y0, x1, y1):
    return LineString([(x0, y0), (x1, y1)])


@pytest.fixture
def lake(tmp_path, monkeypatch):
    monkeypatch.setattr(PN, "P", tmp_path)
    return tmp_path


def _center(lake, lines):
    _gdf(lines, 일방통행=["일방통행"] * len(lines)).to_file(lake / "ngii1k_center_5186.gpkg", driver="GPKG")


def _table(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({**{c: "" for c in COLS}, **r})
    return path


SEG = _seg(0, 0, 200, 0)                       # 동 → 서가 아니라 서 → 동(시작 (0,0) · 끝 (200,0))
FWD = dict(from_x=0, from_y=0, to_x=200, to_y=0)       # 출발 = 시작점 → +1
REV = dict(from_x=200, from_y=0, to_x=0, to_y=0)       # 출발 = 끝점 → −1


def _run(lake, tmp_path, rows, uids=("U1",), lines=None):
    lines = lines or [SEG] * len(uids)
    _center(lake, lines)
    m = _gdf(lines, seg_uid=list(uids))
    return PN.oneway(m, field_path=_table(tmp_path / "t.csv", rows))


def test_a_table_row_decides_the_direction_by_coordinates_in_both_orientations(lake, tmp_path):
    out, s = _run(lake, tmp_path, [{"seg_uid": "U1", "use": "적용", **FWD}])
    assert out == [1] and s["dir_field"] == 1 and s["dir_known"] == 0, "표가 정한 수는 따로 센다(노드링크가 정한 수와 섞지 않는다)"
    out, s = _run(lake, tmp_path, [{"seg_uid": "U1", "use": "적용", **REV}])
    assert out == [-1], "출발점이 구간의 끝이면 −1"


def test_rows_not_marked_as_applied_are_never_read(lake, tmp_path):
    for use in ("보류(충돌)", "참고(이미 확정)", "", "적용 "):
        out, s = _run(lake, tmp_path, [{"seg_uid": "U1", "use": use, **FWD}])
        assert out == [2] and s["dir_field"] == 0, use


def test_only_unknown_direction_is_overwritten(lake, tmp_path):
    """`ow=2` 만 덮는다 — 노드링크가 정한 ±1 은 표가 안 덮고 양방향(0)은 일방통행 표지가 있어야 `ow` 가 선다."""
    _center(lake, [SEG])
    nl = _gdf([_seg(0, 0.5, 200, 0.5)], LINK_ID=["0"])            # 같은 방향 하나 → 노드링크가 +1 로 정한다
    nl.to_file(lake / "node_link_5186.gpkg", driver="GPKG")
    m = _gdf([SEG], seg_uid=["U1"])
    out, s = PN.oneway(m, field_path=_table(tmp_path / "t.csv", [{"seg_uid": "U1", "use": "적용", **REV}]))
    assert out == [1] and s["dir_known"] == 1 and s["dir_field"] == 0, "표(−1)가 노드링크(+1)를 덮지 않는다"
    both = _gdf([SEG, _seg(0, 100, 200, 100)], seg_uid=["U1", "U2"])
    _gdf([SEG], 일방통행=["일방통행"]).to_file(lake / "ngii1k_center_5186.gpkg", driver="GPKG")     # 둘째 구간은 일방통행 표지가 없다
    out, s = PN.oneway(both, field_path=_table(tmp_path / "t2.csv", [{"seg_uid": "U2", "use": "적용", **FWD}]))
    assert out[1] == 0 and s["dir_field"] == 0, "양방향(0)은 안 덮는다 — 충돌은 표에서 보류다"


def test_a_stale_table_row_is_skipped_and_counted_not_applied(lake, tmp_path):
    moved = dict(from_x=0, from_y=50, to_x=200, to_y=50)          # 구간이 옮겨졌다 — 두 끝이 다 안 붙는다
    half = dict(from_x=0, from_y=0, to_x=200, to_y=50)            # 한 끝만 붙는다
    for row in (moved, half):
        out, s = _run(lake, tmp_path, [{"seg_uid": "U1", "use": "적용", **row}])
        assert out == [2] and s["dir_field"] == 0 and s["dir_field_stale"] == 1, "낡은 표는 모름으로 둔다 — 틀린 확정은 모름보다 나쁘다"


def test_the_reason_counts_stay_a_partition_of_the_remaining_unknowns(lake, tmp_path):
    """표가 정한 구간은 사유 수에서 빠진다 — `사유 합 = 일방통행 − 방향 확정(노드링크 + 표)`."""
    lines = [SEG, _seg(0, 100, 200, 100), _seg(0, 200, 200, 200)]
    _center(lake, lines)
    _gdf([_seg(0, 0.5, 200, 0.5), _seg(0, 100.5, 200, 100.5), _seg(200, 99.5, 0, 99.5)], LINK_ID=["0", "1", "2"]).to_file(lake / "node_link_5186.gpkg", driver="GPKG")
    m = _gdf(lines, seg_uid=["A", "B", "C"])
    rows = [{"seg_uid": "B", "use": "적용", "from_x": 0, "from_y": 100, "to_x": 200, "to_y": 100}]      # C 는 표에 없다
    _, s = PN.oneway(m, field_path=_table(tmp_path / "t.csv", rows))
    unknown = s["oneway"] - s["dir_known"] - s["dir_field"]
    reasons = s["nl_twoway"] + s["nl_none"] + s["nl_split"] + s["nl_absent"]
    assert (s["dir_known"], s["dir_field"], reasons, unknown) == (1, 1, 1, 1), s    # A 는 노드링크 · B(양방향이 잡혔던)는 표 · C(링크 없음)는 모름으로 남는다 — 합이 맞는다


def test_without_a_table_or_without_seg_uid_nothing_changes(lake, tmp_path):
    _center(lake, [SEG])
    out, s = PN.oneway(_gdf([SEG]), field_path=tmp_path / "없다.csv")
    assert out == [2] and s["dir_field"] == 0
    out, s = PN.oneway(_gdf([SEG]), field_path=_table(tmp_path / "t.csv", [{"seg_uid": "U1", "use": "적용", **FWD}]))
    assert out == [2], "seg_uid 칸이 없는 구간표는 표를 안 읽는다"


# ── 실제 표 ─────────────────────────────────────────────────────
TABLE = ROOT / "data" / "field" / "oneway_direction_2611.csv"


def _real():
    with TABLE.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_the_real_table_has_its_columns_vocabulary_and_evidence():
    rows = _real()
    assert rows and set(rows[0]) == set(COLS)
    assert {r["use"] for r in rows} <= {"적용", "보류(충돌)", "참고(이미 확정)"}, "어휘 밖의 use 는 조용히 안 읽힌다"
    for r in rows:
        assert r["method"] and r["checked"] and r["evidence"], f"근거 없는 행 — {r['seg_uid']}"
        float(r["from_x"]), float(r["from_y"]), float(r["to_x"]), float(r["to_y"])
    for r in rows:
        if r["use"] == "적용":
            assert r["ow_now"] == "2", "적용은 방향 모름(ow=2)인 구간뿐이다 — 양방향과의 충돌은 보류다(§652)"
            assert float(r["ratio"]) >= 1.5 and float(r["rev_m"]) > float(r["fwd_m"]), "양방향 대조에서 역방향이 우회여야 한다"


def test_the_real_table_rows_exist_in_the_published_segments_and_touch_their_endpoints():
    segs = json.loads((ROOT / "data" / "processed" / "segments.geojson").read_text(encoding="utf-8"))
    g = gpd.GeoDataFrame.from_features(segs["features"], crs="EPSG:4326").to_crs(CRS)
    by = {u: geom for u, geom in zip(g["seg_uid"], g.geometry, strict=True)}
    for r in _real():
        assert r["seg_uid"] in by, f"표가 가리키는 구간이 발행에 없다 — {r['seg_uid']}"
        L = by[r["seg_uid"]]
        assert PN._field_sign(PN._line(L), r) in (1, -1), f"출발·도착 좌표가 구간 끝점에 안 붙는다(낡은 표) — {r['seg_uid']}"
        assert math.dist((float(r["from_x"]), float(r["from_y"])), (float(r["to_x"]), float(r["to_y"]))) > 1.0
