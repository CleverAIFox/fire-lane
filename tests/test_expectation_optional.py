"""선택 컬럼 — 같은 칸이 단계에 따라 선택이고 필수다.  (DECISIONS §628)

IN    합성 산출물 · 합성 계보 (tmp)
OUT   없음
PARAM 없음
밖    실제 산출물은 안 읽는다. `z` 가 옳은 값인가는 안 본다 — 있어야 하는데 없는가만 본다.

★ `--only segments` 로 반쪽만 돌리면 `terrain` 이 `z` 를 안 덧쓴 산출물이 나온다. 스키마가 `z` 를 적었다고 그것을 「계약 위반 — 산출물을 믿지 마라」로
  울면 정상 반쪽 실행이 위반이 된다(2026-11-04 에 실제로 터졌다). 설명 문자열을 파싱하지 않고 스키마의 `optional_fields` 한 칸이 선언한다.
"""
from __future__ import annotations

import json

import pytest

from firelane import expectation as E


@pytest.fixture
def world(tmp_path, monkeypatch):
    P, W = tmp_path / "processed", tmp_path / "web"
    P.mkdir()
    W.mkdir()
    monkeypatch.setattr(E, "PROCESSED", P)
    monkeypatch.setattr(E, "WEB", W)

    def put(d, props, fields, optional=None):
        (d / "segments.geojson").write_text(json.dumps({"features": [{"properties": props}]}), encoding="utf-8")
        spec = {"fields": {k: "x" for k in fields}}
        if optional:
            spec["optional_fields"] = optional
        (d / "segments.schema.json").write_text(json.dumps(spec), encoding="utf-8")

    def lineage(seg_at, terrain_at=None):
        lin = {"segments": {"at": seg_at}}
        if terrain_at:
            lin["terrain"] = {"at": terrain_at}
        (P / "_lineage.json").write_text(json.dumps(lin), encoding="utf-8")

    return P, W, put, lineage


def test_an_optional_column_may_be_absent_when_its_stage_did_not_run_after_segments(world):
    P, W, put, lineage = world
    put(P, {"a": 1}, ["a", "z"], {"z": "terrain"})
    lineage("2026-11-04T10:00:00+09:00")
    assert E.verify_schema() == [], "terrain 이 안 돌았는데 선택 컬럼 z 의 부재를 위반으로 센다 — `--only segments` 가 위반이 된다"
    lineage("2026-11-04T10:00:00+09:00", "2026-11-03T09:00:00+09:00")
    assert E.verify_schema() == [], "terrain 이 segments 보다 **먼저** 돌았으면(그 뒤 segments 가 덮었다) 안 돈 것이다"


def test_an_optional_column_is_required_once_its_stage_ran_after_segments(world):
    P, W, put, lineage = world
    put(P, {"a": 1}, ["a", "z"], {"z": "terrain"})
    lineage("2026-11-04T10:00:00+09:00", "2026-11-04T10:05:00+09:00")
    bad = E.verify_schema()
    assert len(bad) == 1 and "z" in bad[0] and "terrain" in bad[0], f"단계가 돌았는데 선택 컬럼이 없는 것을 못 잡는다 — {bad}"


def test_an_undeclared_missing_column_is_always_a_defect(world):
    P, W, put, lineage = world
    put(P, {"a": 1}, ["a", "b"], {"z": "terrain"})
    lineage("2026-11-04T10:00:00+09:00")
    assert any("b" in x for x in E.verify_schema()), "선언 안 한 칸의 부재를 선택으로 봐준다"


def test_the_web_layer_has_no_optional_columns(world):
    """publish 가 칸을 싣는 자리다 — 스키마가 `z` 를 적었으면 산출물에 있어야 한다(없으면 publish 가 스키마에서 뺐어야 한다)."""
    P, W, put, lineage = world
    put(W, {"a": 1}, ["a", "z"], {"z": "terrain"})
    lineage("2026-11-04T10:00:00+09:00")
    assert any("z" in x and x.startswith("web") for x in E.verify_schema()), "web 에서 선택 컬럼 부재를 봐준다"


def test_the_real_schema_declares_z_as_optional():
    """카나리아 — 선언이 지워지면 위 시험들이 빈 그물이 된다."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    src = (root / "src/firelane/seg/report.py").read_text(encoding="utf-8")
    assert '"optional_fields": {"z": "terrain"}' in src
