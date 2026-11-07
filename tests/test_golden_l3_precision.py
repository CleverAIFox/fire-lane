"""L3 기하 지문이 0.0005° 이동을 본다.  (감사 1-3 · Zm20 · B — 사람이 잠그기 전)

`_round_geom` 의 기본 `nd=3` 은 EPSG:4326 에서 **0.001° ≈ 55~100 m** 격자다. 머리말은 「mm 로 반올림」이라
적었지만 호출이 기본값을 써서 L3 가 기하가 반 격자 이동해도 같은 값을 냈다 — 지문이 기하 변경을 못 잡는다.
호출을 `nd=7`(≈ 1 cm)로 올렸다.

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **골든을 잠그지 않는다** — L3 가 이동을 보는지만 본다. 재잠금은 사람이 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import golden


def _feature(lon: float) -> dict:
    return {"type": "Feature",
            "properties": {"seg_uid": "DM-1-1-AAAA", "verdict": "clear", "width_min_m": 8.0, "width_max_m": None,
                           "width_src": "ngii1k", "unknown_reason": None, "length_m": 10.0, "route_usage": 0},
            "geometry": {"type": "LineString", "coordinates": [[lon, 35.15], [lon + 0.0001, 35.1501]]}}


def _l3(tmp_path: Path, monkeypatch, lon: float) -> str:
    p = tmp_path / "seg.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": [_feature(lon)]}), encoding="utf-8")
    monkeypatch.setattr(golden, "SEG", p)
    return golden.fingerprint()["L3"]


def _moved(tmp_path, monkeypatch, lon_a: float, lon_b: float) -> bool:
    return _l3(tmp_path, monkeypatch, lon_a) != _l3(tmp_path, monkeypatch, lon_b)


def test_half_a_thousandth_of_a_degree_moves_l3(tmp_path, monkeypatch) -> None:
    # 127.1197 → 127.1202 는 nd=3 에서 둘 다 127.120 으로 접힌다(같은 격자 칸) — 옛 지문은 이 이동을 못 봤다.
    assert _moved(tmp_path, monkeypatch, 127.1197, 127.1202), "0.0005° 이동을 L3 가 못 본다 — 호출이 기본 nd 를 쓴다"


def test_the_same_geometry_is_stable(tmp_path, monkeypatch) -> None:
    assert not _moved(tmp_path, monkeypatch, 127.1197, 127.1197)


def test_the_call_site_names_its_precision() -> None:
    src = (Path(golden.__file__)).read_text(encoding="utf-8")
    assert "_round_geom(f[\"geometry\"], nd=7)" in src
