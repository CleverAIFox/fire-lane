#!/usr/bin/env python3
"""
test_shardseal.py — 샤드 봉인지가 **찢어져야 할 때 찢어지고, 붙어야 할 때 붙는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-16. ingest 는 매 실행 65종을 전부 다시 빌드했고, 이 8GB 기계에서
`ngii_road` 는 다시 빌드하면 거의 반드시 `Errno 12` 로 죽는다. 소스 하나 단위로
봉인지(raw · cfg · code · out)를 붙여 **찢어진 샤드만** 다시 빌드한다(DECISIONS §165).

★ 재사용은 **실패로 안 보인다.** 봉인지가 항상 "일치" 를 내면 raw 가 바뀌어도
  옛 산출물로 판정이 나고 전 게이트가 초록이다. 그래서 칸마다 **찢는 대조**를 둔다.
  그리고 항상 "불일치" 를 내는 고장도 잡으려고 붙는 쪽(양성)을 먼저 확인한다(§159).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from firelane import shardseal
from firelane.guards import quarantine_stale

ROOT = Path(__file__).resolve().parents[1]
CFG = {"layers": {"raw": {}}, "datasets": {"road": {"files": ["road.zip"]},
                                           "road_center": {"files": ["c.zip"]}}}


@pytest.fixture
def shard(tmp_path):
    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir()
    out.mkdir()
    (raw / "road.zip").write_bytes(b"raw-v1")
    (out / "road.geojson").write_text("{}", encoding="utf-8")
    (out / "road_5186.gpkg").write_bytes(b"gpkg-v1")
    hits = [raw / "road.zip"]
    seal = shardseal.make(CFG, "road", hits, out, ["road.geojson", "road_5186.gpkg"], "code-v1")
    rec = {"key": "road", "status": "OK", "outputs": ["road.geojson", "road_5186.gpkg"],
           "seal": seal}
    return {"raw": raw, "out": out, "hits": hits, "rec": rec}


def test_same_everything_reuses(shard):
    """★ 양성 대조. 이것이 실패하면 아래 찢는 대조는 전부 무의미하다."""
    ok, why = shardseal.check(shard["rec"], CFG, "road", shard["hits"], shard["out"], "code-v1")
    assert ok, why


@pytest.mark.parametrize("how, reason", [
    ("raw", "raw 가 바뀌었다"),
    ("code", "ingest 코드가 바뀌었다"),
    ("cfg", "sources.yaml 설정이 바뀌었다"),
    ("out_gone", "산출물 파일이 없다"),
    ("out_changed", "산출물이 봉인과 다르다"),
    ("old_record", "봉인지가 없다"),
    ("failed", "OK 가 아니다"),
    ("raw_gone", "raw 를 못 쟀다"),
])
def test_each_cell_tears_the_seal(shard, how, reason):
    rec, hits, out, code = dict(shard["rec"]), shard["hits"], shard["out"], "code-v1"
    cfg = CFG
    if how == "raw":
        hits[0].write_bytes(b"raw-v2")
    elif how == "code":
        code = "code-v2"
    elif how == "cfg":
        cfg = {**CFG, "datasets": {**CFG["datasets"], "road": {"files": ["road2.zip"]}}}
    elif how == "out_gone":
        (out / "road_5186.gpkg").rename(out / "road_5186.gpkg.stale_20260916")
    elif how == "out_changed":
        (out / "road_5186.gpkg").write_bytes(b"gpkg-v2")
    elif how == "old_record":
        rec.pop("seal")
    elif how == "failed":
        rec["status"] = "FAIL"
    elif how == "raw_gone":
        hits = []
    ok, why = shardseal.check(rec, cfg, "road", hits, out, code)
    assert not ok, f"{how} 인데 봉인지가 안 찢어졌다 — 옛 산출물로 판정이 난다"
    assert reason in why, why


def test_other_sources_config_does_not_tear(shard):
    """다른 소스 항목만 바뀌면 이 샤드는 그대로다 — 안 그러면 한 줄에 65종이 다시 돈다."""
    cfg = {**CFG, "datasets": {**CFG["datasets"], "road_center": {"files": ["c2.zip"]}}}
    ok, why = shardseal.check(shard["rec"], cfg, "road", shard["hits"], shard["out"], "code-v1")
    assert ok, why


def test_make_refuses_when_unmeasurable(tmp_path):
    """못 재면 봉인하지 않는다. 빈 봉인지는 다음 대조에서 조용히 통과할 수 있다."""
    assert shardseal.make(CFG, "road", [], tmp_path, ["x.gpkg"], "c") is None
    (tmp_path / "r.zip").write_bytes(b"r")
    assert shardseal.make(CFG, "road", [tmp_path / "r.zip"], tmp_path, ["없음.gpkg"], "c") is None
    assert shardseal.make(CFG, "road", [tmp_path / "r.zip"], tmp_path, [], "c") is None


def test_code_closure_follows_ingest_imports_not_segments():
    """ingest 샤드의 code 칸은 ingest 가 **실제로 import 하는** 모듈만이다."""
    names = {p.relative_to(ROOT / "src" / "firelane").as_posix()
             for p in shardseal.code_closure()}
    assert "ingest.py" in names
    assert "guards.py" in names, "함수 안의 늦은 import(quarantine_stale)를 못 따라간다"
    assert "hashing.py" in names
    assert not any(n.startswith("seg/") for n in names), \
        "segments 쪽이 ingest 샤드에 섞였다 — 판정 코드 한 줄에 ingest 전량이 다시 돈다"
    assert "segments.py" not in names


def test_code_closure_moves_with_an_imported_module(tmp_path, monkeypatch):
    pkg = tmp_path / "src" / "firelane"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "ingest.py").write_text("def f():\n    from firelane.guards import g\n", encoding="utf-8")
    (pkg / "guards.py").write_text("X = 1\n", encoding="utf-8")
    (pkg / "segments.py").write_text("Y = 1\n", encoding="utf-8")
    monkeypatch.setattr(shardseal, "PKG", pkg)
    monkeypatch.setattr(shardseal, "ROOT", tmp_path)
    a = shardseal.code_print()
    (pkg / "segments.py").write_text("Y = 2\n", encoding="utf-8")
    assert shardseal.code_print() == a, "import 안 하는 모듈이 ingest 샤드를 찢는다"
    (pkg / "guards.py").write_text("X = 2\n", encoding="utf-8")
    assert shardseal.code_print() != a, "import 하는 모듈이 바뀌었는데 봉인지가 그대로다"


def test_quarantine_spares_a_longer_named_source(tmp_path):
    """★ 2026-09-16 실사고. `ngii_road` 격리가 `ngii_road_center` 를 같이 개명했다."""
    for n in ("ngii_road.geojson", "ngii_road_5186.gpkg",
              "ngii_road_center.geojson", "ngii_road_center_5186.gpkg"):
        (tmp_path / n).write_text("x", encoding="utf-8")
    staled = quarantine_stale(tmp_path, "ngii_road", tag="20260916",
                              keys=["ngii_road", "ngii_road_center"])
    assert sorted(staled) == ["ngii_road.geojson", "ngii_road_5186.gpkg"], staled
    assert (tmp_path / "ngii_road_center_5186.gpkg").exists(), "옆 소스 산출물이 격리됐다"


def test_quarantine_without_keys_still_bites_neighbours(tmp_path):
    """카나리아 — keys 없이 부르면 옛 동작(옆 소스까지)이다. ingest 가 keys 를 넘겨야 하는 이유."""
    for n in ("ngii_road.geojson", "ngii_road_center.geojson"):
        (tmp_path / n).write_text("x", encoding="utf-8")
    assert "ngii_road_center.geojson" in quarantine_stale(tmp_path, "ngii_road", tag="1")


def test_ingest_is_wired():
    src = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
    assert "shardseal.check(" in src, "ingest 가 샤드 봉인지를 대조하지 않는다"
    assert 'r["seal"] = _s' in src, "새로 빌드한 샤드에 봉인지를 안 붙인다"
    assert 'quarantine_stale(OUT, key, keys=' in src, "격리가 옆 소스 이름을 모른다"


# ── 하류 덧쓰기 (2026-09-16 · DECISIONS §165-6) ─────────────────
def test_terrain_mutations_are_declared():
    """terrain.LAYERS 의 산출물이 파이프라인 선언 `mutates` 에 전부 있는가.

    ★ 모듈이 f"{key}_5186.gpkg" 로 써서 리터럴 대조(test_declaration_reality)가
      못 봤다. terrain 을 무겁게 import 하지 않으려고 AST 로 LAYERS 를 읽는다.
    """
    import ast
    tree = ast.parse((ROOT / "src/firelane/terrain.py").read_text(encoding="utf-8"))
    layers = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                  if isinstance(n, ast.Assign)
                  and any(getattr(t, "id", "") == "LAYERS" for t in n.targets))
    assert "building" in layers, "LAYERS 를 못 읽었다 — 카나리아가 죽었다"
    from firelane.pipeline import STEPS
    ter = next(s for s in STEPS if s.name == "terrain")
    declared = {p.name for p in ter.mutates}
    want = {f"{k}_5186.gpkg" for k in layers} | \
           {f"{k}.geojson" for k in layers}
    assert not want - declared, f"terrain 이 덧쓰는데 선언이 없다: {sorted(want - declared)}"


def test_reseal_out_touches_only_the_out_cell(shard):
    rec = shard["rec"]
    before = {k: v for k, v in rec["seal"].items() if k != "out"}
    (shard["out"] / "road_5186.gpkg").write_bytes(b"gpkg-with-z")   # 하류가 z 를 덧썼다
    ok, why = shardseal.check(rec, CFG, "road", shard["hits"], shard["out"], "code-v1")
    assert not ok and "산출물이 봉인과 다르다" in why          # 덧쓰기 직후엔 찢어진다
    fixed, missing = shardseal.reseal_out([rec], shard["out"])
    assert fixed == ["road"] and missing == []
    assert {k: v for k, v in rec["seal"].items() if k != "out"} == before, \
        "reseal_out 이 raw · cfg · code 를 건드렸다 — 거짓 봉인 경로다"
    ok, why = shardseal.check(rec, CFG, "road", shard["hits"], shard["out"], "code-v1")
    assert ok, f"out 을 고쳤는데도 찢어진다 — 매 실행 재빌드가 계속된다: {why}"
    assert shardseal.reseal_out([rec], shard["out"]) == ([], []), "두 번째 호출이 또 고친다 — 멱등이 아니다"


def test_reseal_out_does_not_seal_a_raw_change(shard):
    """out 만 고치므로 raw 가 바뀐 샤드는 여전히 찢어진다 — `--from` 부분 실행의 안전선."""
    rec = shard["rec"]
    shard["hits"][0].write_bytes(b"raw-v2")
    shardseal.reseal_out([rec], shard["out"])
    ok, why = shardseal.check(rec, CFG, "road", shard["hits"], shard["out"], "code-v1")
    assert not ok and "raw 가 바뀌었다" in why


def test_reseal_out_skips_missing_and_unsealed(shard, tmp_path):
    rec = shard["rec"]
    (shard["out"] / "road.geojson").unlink()
    plain = {"key": "plain", "status": "OK", "outputs": ["x.gpkg"]}
    fixed, missing = shardseal.reseal_out([rec, plain], shard["out"])
    assert fixed == [] and missing == ["road"]
    assert "seal" not in plain


def test_pipeline_reseals_after_terrain():
    src = (ROOT / "src/firelane/pipeline.py").read_text(encoding="utf-8")
    i = src.index('s.name == "terrain"')
    assert '"--reseal-out"' in src[i:i + 900], "terrain 뒤에 out 재봉인을 안 부른다"


def test_code_print_ignores_comments_and_docstrings(tmp_path, monkeypatch):
    """★ 머리말 한 줄에 40 샤드가 찢어지면 이 기계에서는 OOM 이다. 로직만 센다."""
    pkg = tmp_path / "src" / "firelane"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    body = 'def build(x):\n    """옛 설명"""\n    return x + 1  # 옛 주석\n'
    (pkg / "ingest.py").write_text('"""머리말 v1"""\n' + body, encoding="utf-8")
    monkeypatch.setattr(shardseal, "PKG", pkg)
    monkeypatch.setattr(shardseal, "ROOT", tmp_path)
    a = shardseal.code_print()
    (pkg / "ingest.py").write_text('"""머리말 v2 — 예: building.geojson"""\n'
                                   + body.replace("옛 설명", "새 설명").replace("옛 주석", "새 주석"),
                                   encoding="utf-8")
    assert shardseal.code_print() == a, "주석 · docstring 만 바꿨는데 샤드가 찢어진다"
    (pkg / "ingest.py").write_text('"""머리말 v2"""\n' + body.replace("x + 1", "x + 2"),
                                   encoding="utf-8")
    assert shardseal.code_print() != a, "로직을 바꿨는데 봉인지가 그대로다 — 카나리아가 죽었다"


def test_gpkg_print_is_content_not_bytes(tmp_path):
    """★ 같은 내용을 다시 쓰면 같고, z 가 바뀌면 다르다. 바이트는 매번 다르다(last_change)."""
    import time

    import geopandas as gpd
    from shapely.geometry import Point

    from firelane.hashing import sha256
    g = gpd.GeoDataFrame({"z": [1.5, 2.5]}, geometry=[Point(0, 0), Point(1, 1)], crs=5186)
    a, b = tmp_path / "a.gpkg", tmp_path / "b.gpkg"
    g.to_file(a, driver="GPKG", layer="x")
    time.sleep(1.1)
    g.to_file(b, driver="GPKG", layer="x")
    assert sha256(a) != sha256(b), "바이트가 같게 나왔다 — 이 검사의 전제(last_change)가 사라졌다"
    assert shardseal.gpkg_print(a) == shardseal.gpkg_print(b), "같은 내용인데 지문이 다르다 — 매 실행 봉인지가 흔들린다"
    g["z"] = [1.5, 9.9]
    g.to_file(b, driver="GPKG", layer="x")
    assert shardseal.gpkg_print(a) != shardseal.gpkg_print(b), "z 가 바뀌었는데 지문이 같다 — 카나리아가 죽었다"


def test_seal_logic_itself_is_not_in_code_print():
    names = {p.name for p in shardseal.code_closure()}
    assert "shardseal.py" in names, "닫힘 계산이 shardseal 을 못 찾는다 — 아래 제외 대조가 무의미하다"
    assert "shardseal.py" in shardseal.NOT_PRODUCERS


def test_gpkg_print_does_not_crash_on_a_broken_file(tmp_path):
    p = tmp_path / "broken.gpkg"
    p.write_bytes(b"not-a-database")
    got = shardseal.gpkg_print(p)
    assert got.startswith("bytes:"), "깨진 gpkg 에 죽거나 내용 지문인 척한다"
    p.write_bytes(b"not-a-database-v2")
    assert shardseal.gpkg_print(p) != got
