"""
test_turn_restriction_filter.py — 회전제한은 동명동 노드 산출물 없이 전국분을 내지 않는다.

2026-09-22 (DECISIONS §217-1). `ingest.build` 의 `dbf_in_zip` 은 `node_point_5186.gpkg`
(산출물)로 거른다. 종전엔 그것이 **없으면 거르지 않고** 전국 44,125행을 냈다 — 그날 verify 가
turn_restriction 재빌드에서 빨개진 자리다. 지금은 원인 자리에서 멈춘다. 있으면 거른다.
"""
from __future__ import annotations

import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import Point

from firelane import ingest


def _zip(tmp_path):
    g = gpd.GeoDataFrame({"NODE_ID": ["A", "B", "C"], "TURN": ["1", "2", "3"]},
                         geometry=[Point(0, 0)] * 3, crs=5186)
    d = tmp_path / "shp"
    d.mkdir()
    g.to_file(d / "TURNINFO.shp")
    zp = tmp_path / "turn.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for f in d.iterdir():
            z.write(f, f.name)
    return zp


def _run(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    zp = _zip(tmp_path)
    monkeypatch.setattr(ingest, "OUT", out)
    monkeypatch.setattr(ingest, "paths_for", lambda key, e: [zp])
    e = {"kind": "dbf_in_zip", "layer": "TURNINFO.dbf", "file": "turn.zip"}
    work = tmp_path / "work"
    work.mkdir()
    return out, lambda: ingest.build("turn_restriction", e, work)


def test_missing_node_point_stops(tmp_path, monkeypatch):
    _, go = _run(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError, match="node_point_5186.gpkg"):
        go()


def test_node_point_filters(tmp_path, monkeypatch):
    out, go = _run(tmp_path, monkeypatch)
    gpd.GeoDataFrame({"NODE_ID": ["B"]}, geometry=[Point(0, 0)], crs=5186).to_file(
        out / "node_point_5186.gpkg", driver="GPKG")
    rec = go()
    assert rec["status"] == "OK" and rec["features"] == 1, rec
