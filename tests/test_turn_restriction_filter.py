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
    with pytest.raises(FileNotFoundError, match=r"node_point_5186\.gpkg"):
        go()


def test_node_point_filters(tmp_path, monkeypatch):
    out, go = _run(tmp_path, monkeypatch)
    gpd.GeoDataFrame({"NODE_ID": ["B"]}, geometry=[Point(0, 0)], crs=5186).to_file(
        out / "node_point_5186.gpkg", driver="GPKG")
    rec = go()
    assert rec["status"] == "OK" and rec["features"] == 1, rec


# ── 필터가 **조용히 사라지는** 네 갈래 (PLAN §1 #13 · DECISIONS §273-7) ──
# ★ §217-1 은 파일 부재만 막았다. 남은 셋은 전부 「status 는 OK 인데 거른 것이
#   없다」다 — 이 저장소가 계속 잡는 조용한 통과다.
def _df(**cols):
    import pandas as pd
    return pd.DataFrame(cols)


def _nodes(tmp_path, ids, col="NODE_ID"):
    import geopandas as gpd
    from shapely.geometry import Point
    p = tmp_path / "node_point_5186.gpkg"
    gpd.GeoDataFrame({col: list(ids)},
                     geometry=[Point(i, i) for i in range(len(ids))],
                     crs=5186).to_file(p, driver="GPKG")
    return p


def test_a_missing_key_column_is_not_a_silent_passthrough(tmp_path):
    """★ 칸 이름이 바뀌면 거르는 코드가 통째로 안 돈다. 전국분이 그대로 나간다."""
    import pytest

    from firelane.guards import subset_by_nodes
    df = _df(OTHER_ID=[1, 2, 3])
    with pytest.raises(ValueError, match="NODE_ID"):
        subset_by_nodes(df, _nodes(tmp_path, [1]), "turn_restriction")


def test_an_empty_node_set_cries_on_its_own_arm(tmp_path):
    """★ 팔을 **따로** 세운다.

    처음에 `match="0개"` 로 썼더니 이 팔을 죽여도 시험이 초록이었다 — 노드가
    비면 결과가 0행이 되어 「다 걸림」 팔이 대신 울고, 그 메시지에도 「0개」가
    들어 있었다. **팔 하나가 죽었는데 옆 팔이 가렸다.** 셋이 한꺼번에 울면
    어느 팔이 살아 있는지 모른다(test_evalgen 머리말과 같은 규율).
    """
    import pytest

    from firelane.guards import subset_by_nodes
    with pytest.raises(ValueError, match="거르면 전부"):
        subset_by_nodes(_df(NODE_ID=[1, 2]), _nodes(tmp_path, []), "turn_restriction")


def test_a_filter_that_removes_nothing_cries(tmp_path):
    """거르기 전후가 같으면 **거른 것이 아니다.** 열쇠가 어긋난 자리다."""
    import pytest

    from firelane.guards import subset_by_nodes
    with pytest.raises(ValueError, match="같다"):
        subset_by_nodes(_df(NODE_ID=[1, 2]), _nodes(tmp_path, [1, 2]), "turn_restriction")


def test_a_filter_that_removes_everything_cries(tmp_path):
    """0행을 정상으로 적으면 하류가 「회전제한 없음」으로 읽는다."""
    import pytest

    from firelane.guards import subset_by_nodes
    with pytest.raises(ValueError, match="0행"):
        subset_by_nodes(_df(NODE_ID=[8, 9]), _nodes(tmp_path, [1, 2]), "turn_restriction")


def test_the_normal_case_still_filters(tmp_path):
    from firelane.guards import subset_by_nodes
    got = subset_by_nodes(_df(NODE_ID=[1, 2, 3, 4]), _nodes(tmp_path, [2, 3]), "x")
    assert list(got["NODE_ID"]) == [2, 3]


def test_ingest_calls_the_gate_rather_than_filtering_by_hand():
    """★ 관문이 있어도 `ingest` 가 손으로 거르면 아무 소용이 없다."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "firelane" / "ingest.py") \
        .read_text(encoding="utf-8")
    i = src.index('elif kind == "dbf_in_zip"')
    block = src[i:i + 2000]
    assert "subset_by_nodes" in block, "dbf_in_zip 분기가 관문을 안 부른다"
    assert ".isin(ids)" not in block, "관문을 두고 손으로 또 거른다 — 정본이 둘이다"
