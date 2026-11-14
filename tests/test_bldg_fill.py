"""
test_bldg_fill.py — `bldg_fill` 의 **고르는 규칙**(PLAN #244 · DECISIONS §786)을 합성 면으로 문다.

★ 레이크(대장 zip)를 안 읽는다 — 작은 사각형으로 규칙 ①~⑤ 가 각각 **한 면씩** 걸러내는지 본다. 실물 4,296면은 `python -m firelane.bldg_fill`(바이트 대조)이 든다.

IN    src/firelane/bldg_fill.py (순수 함수 `agreement` · `pick` · 쓰기 `write` · `report` · `move_bounds`)
OUT   없음
밖    **면이 항공뷰와 맞는가는 안 본다**(사람 눈 · PLAN #245 ②). **레이크에서 읽는 `load` · `main` 은 안 부른다** — zip 이 저장소에 없다.
"""
from __future__ import annotations

import geopandas as gpd
from shapely.geometry import box

from firelane import bldg_fill as B

CRS = 5186
X0, Y0 = 200_000.0, 550_000.0


def sq(x: float, y: float, w: float = 20.0, h: float = 20.0):
    return box(X0 + x, Y0 + y, X0 + x + w, Y0 + y + h)


def frame(rows):
    return gpd.GeoDataFrame(
        {"A26": [r[1] for r in rows], B.USE_COL: [r[2] for r in rows], B.NAME_COL: [r[3] for r in rows]},
        geometry=[r[0] for r in rows], crs=CRS)


MOVE = box(X0 - 10, Y0 - 10, X0 + 1000, Y0 + 1000)
DONG = box(X0 - 10, Y0 - 10, X0 + 100, Y0 + 1000)       # 동명동 = 왼쪽 띠
TL = gpd.GeoDataFrame(geometry=[sq(300, 300, 40, 40)], crs=CRS)   # 기존 건물 하나(300~340)


def test_agreement_measures_overlap_and_offset():
    al = gpd.GeoDataFrame(geometry=[sq(0, 0), sq(500, 500)], crs=CRS)
    tl = gpd.GeoDataFrame(geometry=[sq(5, 0)], crs=CRS)           # 5m 비껴 그린 같은 건물
    r = B.agreement(al, tl)
    assert list(r["i"]) == [0], "안 닿는 면은 행이 없어야 한다"
    row = r.iloc[0]
    assert abs(row.iou - (15 * 20) / (20 * 20 + 20 * 20 - 15 * 20)) < 1e-9
    assert abs(row.d - 5.0) < 1e-9 and abs(row.cover - 0.75) < 1e-9 and abs(row.dx + 5.0) < 1e-9


def test_pick_applies_each_rule_to_exactly_one_face():
    rows = [
        (sq(400, 0), 0, "근린생활시설", " 가게 "),            # ✓ 빠진 면 — 층수 0 → 1 · 이름은 앞뒤 공백을 뗀다
        (sq(500, 0), 7, "업무시설", None),                    # ✓ 이름 없음 → 빈 글자
        (sq(50, 0), 3, "업무시설", "동 안"),                  # ② 동명동 안 — `bldg_gap` 몫
        (sq(2000, 0), 3, "업무시설", "범위 밖"),              # ① 지도 이동 범위 밖
        (sq(300, 300, 40, 40), 3, "업무시설", "덮임"),        # ③ 기존 건물에 100% 덮임
        (sq(600, 600, 6, 6), 2, "업무시설", "어긋난 같은 건물"),   # ④ 아래 TL2 와 안 겹치지만(덮임 0) 무게중심 6.5m · 면적비 1
    ]
    tl = gpd.GeoDataFrame(geometry=list(TL.geometry) + [sq(600, 606.5, 6, 6)], crs=CRS)
    out, led = B.pick(frame(rows), MOVE, DONG, tl)
    assert (led["in_move"], led["outside_dong"], led["uncovered"], led["dup_suspect"], led["added"]) == (5, 4, 3, 1, 2), led
    assert led["added"] == len(out)
    assert sorted(out["nm"]) == ["", "가게"]
    assert out["flo"].min() >= 1 and set(out["src"]) == {B.SRC_TAG}
    assert out.crs.to_epsg() == 4326, "발행은 경위도다"


def test_pick_rejects_a_geographic_source_and_missing_columns():
    import pytest
    geo = frame([(sq(400, 0), 1, "x", "y")]).to_crs(4326)
    with pytest.raises(ValueError, match="좌표계"):
        B.pick(geo, MOVE, DONG, TL)
    with pytest.raises(ValueError, match="A26"):
        B.pick(frame([(sq(400, 0), 1, "x", "y")]).drop(columns=["A26"]), MOVE, DONG, TL)


def test_write_roundtrips_and_move_bounds_is_a_metric_box(tmp_path):
    out, _ = B.pick(frame([(sq(400, 0), 2, "업무시설", "이름")]), MOVE, DONG, TL)
    p = tmp_path / "x" / "fill.geojson"
    B.write(out, p)
    back = gpd.read_file(p)
    assert len(back) == 1 and back["nm"].iloc[0] == "이름" and back["flo"].iloc[0] == 2
    mb = B.move_bounds()
    assert mb.area > 1e6 and mb.bounds[2] - mb.bounds[0] > 1000, "지도 이동 범위가 미터 상자가 아니다"


def test_report_prints_the_four_agreement_bands(capsys):
    al = frame([(sq(0, 0), 1, "a", "b"), (sq(40, 0), 1, "a", "b")])
    tl = gpd.GeoDataFrame(geometry=[sq(2, 0)], crs=CRS)
    B.report(al, box(X0 - 10, Y0 - 10, X0 + 500, Y0 + 500), tl)
    o = capsys.readouterr().out
    assert "같은 건물" in o and "덮임 < 10%" in o and "EPSG:5186" in o


def test_load_reads_the_ledger_zip_with_the_move_bbox_and_the_dong_boundary(monkeypatch, tmp_path):
    """`load` 는 대장 zip 을 **지도 이동 범위 bbox** 로 읽고 동명동 경계를 EMD_CD 로 고른다 — 레이크 없이 읽기 호출만 바꿔 끼워 묻는다."""
    calls = []
    emd = gpd.GeoDataFrame({"EMD_CD": [B.EMD_CD, "99999999"]}, geometry=[DONG, box(X0 + 500, Y0, X0 + 600, Y0 + 10)], crs=CRS)
    al = frame([(sq(400, 0), 1, "업무시설", "이름")])

    def fake_read(path, **kw):
        calls.append((str(path), kw))
        if "vsizip" in str(path):
            return al
        return emd if "boundary" in str(path) else TL

    monkeypatch.setattr(B.bldg_gap, "source", lambda _src: tmp_path / "ledger.zip")
    monkeypatch.setattr(B.gpd, "read_file", fake_read)
    got_al, move, dong, tl = B.load()
    assert got_al is al and tl is TL
    assert dong.equals(DONG) or dong.symmetric_difference(DONG).area < 1e-6, "동명동 경계가 EMD_CD 로 안 골라졌다"
    zip_call = next(c for c in calls if "vsizip" in c[0])
    assert zip_call[1]["bbox"] == tuple(move.bounds), "대장을 지도 이동 범위로 안 잘랐다 — 전국 윤곽을 읽는다"
