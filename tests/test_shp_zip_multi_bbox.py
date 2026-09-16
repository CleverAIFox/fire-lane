#!/usr/bin/env python3
"""
test_shp_zip_multi_bbox.py — `shp_zip_multi` 가 **읽는 시점에** 거르는가, 그래도 산출이 같은가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-16. `jijeok` 은 zip 하나 안에 shp 7장 × 100만 필지다. 핸들러가 7장을 전부
메모리에 올린 뒤 `.cx` 로 24,183건을 잘랐고, 8GB 기계에서 그 자리가 OOM 이었다.
같은 zip 을 `tools/jijeok_probe.py --extract` 는 bbox 로 읽어 살아 있었다(DECISIONS §168).

★ 이 분기는 `ngii_road` · `ngii_road_center` 도 탄다. 판정 입력이다. 그래서 둘을 본다 —
  ① 읽을 때마다 bbox 가 걸리는가(메모리) ② 산출이 종전 방식(전량 → `.cx`)과 같은가(판정).
  ①만 보면 `.cx` 를 지워도 초록이다. OGR 필터는 외곽 사각형 기준이라 **외곽만 걸치는
  도형**이 새어 들어온다. ③ 그 도형이 산출에 없는지를 카나리아로 둔다.
"""
from __future__ import annotations

import zipfile

import geopandas as gpd
import pandas as pd
import pyogrio
import pytest
from shapely.geometry import Polygon, box

from firelane import ingest

X0, Y0 = 200_000.0, 500_000.0
BB = (X0, Y0, X0 + 100, Y0 + 100)
# 외곽 사각형(90..200)은 bbox 모서리(90..100)와 겹치는데 도형은 x+y=290 선 밖이라 안 겹친다
LEAK = Polygon([(X0 + 90, Y0 + 200), (X0 + 200, Y0 + 200), (X0 + 200, Y0 + 90)])


def _sq(x: float, y: float) -> Polygon:
    return box(X0 + x, Y0 + y, X0 + x + 5, Y0 + y + 5)


@pytest.fixture
def multi_zip(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    a = gpd.GeoDataFrame({"PNU": ["in1", "out1", "leak", "in2"]},
                         geometry=[_sq(10, 10), _sq(500, 500), LEAK, _sq(60, 40)],
                         crs="EPSG:5186")
    b = gpd.GeoDataFrame({"PNU": ["far1", "far2"]},
                         geometry=[_sq(900, 900), _sq(-800, 10)], crs="EPSG:5186")
    a.to_file(src / "T.shp", encoding="utf-8")
    b.to_file(src / "T(2).shp", encoding="utf-8")
    z = tmp_path / "t_multi.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in sorted(src.iterdir()):
            zf.write(f, f.name)
    return z


@pytest.fixture
def run(tmp_path, monkeypatch, multi_zip):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(ingest, "OUT", out)
    monkeypatch.setattr(ingest, "paths_for", lambda key, e: [multi_zip])
    monkeypatch.setattr(ingest, "bbox_in", lambda crs: BB)
    e = {"kind": "shp_zip_multi", "layer": "T.shp", "crs_native": 5186,
         "encoding": "utf-8", "files": ["t_multi.zip"], "parts": ["", "2"]}

    def _go():
        work = tmp_path / "work"
        work.mkdir(exist_ok=True)
        r = ingest.build("tmulti", e, work)
        # 산출은 pyogrio 로 직접 읽는다 — 첩자(spy)가 build 안의 호출만 세도록
        g = pyogrio.read_dataframe(out / "tmulti_5186.gpkg") if r.get("status") == "OK" else None
        return r, g
    return _go


def _eager(z, tmp_path):
    """종전 방식 — 전량을 읽고 `.cx` 로 자른다. 비교 기준이다."""
    d = tmp_path / "eager"
    with zipfile.ZipFile(z) as zf:
        zf.extractall(d)
    parts = [gpd.read_file(p, encoding="utf-8") for p in sorted(d.glob("T*.shp"))]
    g = pd.concat(parts).pipe(gpd.GeoDataFrame, crs=parts[0].crs)
    return g.cx[BB[0]:BB[2], BB[1]:BB[3]]


def test_every_part_is_read_with_bbox(run, monkeypatch):
    seen = []
    real = gpd.read_file

    def spy(p, *a, **kw):
        seen.append(kw.get("bbox"))
        return real(p, *a, **kw)
    monkeypatch.setattr(ingest.gpd, "read_file", spy)
    r, _ = run()
    assert r["status"] == "OK", r
    assert len(seen) == 2, f"조각 2장을 읽어야 한다 — {len(seen)}번 읽었다"
    assert all(b == BB for b in seen), (
        f"bbox 없이 읽은 조각이 있다 — {seen}\n"
        "  `jijeok` 은 조각 하나가 100만 필지다. 읽고 나서 거르면 8GB 기계에서 죽는다(DECISIONS §168).")


def test_output_equals_eager_read_then_cx(run, multi_zip, tmp_path):
    r, g = run()
    assert r["status"] == "OK", r
    ref = _eager(multi_zip, tmp_path)
    assert sorted(g["PNU"]) == sorted(ref["PNU"]) == ["in1", "in2"]
    assert r["features"] == len(ref)
    assert r["parts_read"] == ["T(2).shp", "T.shp"]


def test_envelope_only_driver_does_not_leak(run, monkeypatch):
    """카나리아 — `.cx` 를 지우면 여기가 운다.

    이 기계의 GDAL 은 GEOS 로 정확히 교차를 본다. 그래서 실물 드라이버로는 `.cx` 를 지워도
    초록이다(조작해서 확인했다 — 죽은 카나리아였다). GEOS 없이 빌드된 GDAL 은 **외곽 사각형**
    으로만 거른다. 그 드라이버를 흉내 내 새는 도형을 넣고, `.cx` 가 막는지 본다.
    """
    real = gpd.read_file

    def envelope_only(p, *a, bbox=None, **kw):
        g = real(p, *a, **kw)
        if bbox is None:
            return g
        b = g.geometry.bounds
        hit = ((b.minx <= bbox[2]) & (b.maxx >= bbox[0])
               & (b.miny <= bbox[3]) & (b.maxy >= bbox[1]))
        return g[hit]
    monkeypatch.setattr(ingest.gpd, "read_file", envelope_only)
    r, g = run()
    assert r["status"] == "OK", r
    assert "leak" not in set(g["PNU"]), (
        "외곽 사각형만 걸치는 도형이 산출에 들어왔다. bbox 필터는 드라이버에 따라 정확한 교차가\n"
        "  아니다 — 읽은 뒤 `.cx` 로 한 번 더 잘라야 한다.")
