#!/usr/bin/env python3
"""
test_read_branches.py — **갈래 전부가 밀린다.** (§498)

── 왜 생겼나 ───────────────────────────────────────────────────
`firelane.read.READERS` 는 `kind` → 갈래 함수 표이고, 72종 데이터셋 전부가
그 중 하나를 지난다. `tests/test_read_dispatch.py` 는 **배선**을 든다 —
표가 kind 를 빠뜨리지 않았나 · 도형/표 선언이 맞나. 갈래 **안**은 안 봤다.

§493 · §497 이 그 분모를 세자 여섯이 남았다 —
`unzip_own` · `csv_points_in_zip` · `csv_table` · `json_points` ·
`json_table` · `shp_zip_multi`. 전부 **조용히 0건이 되는** 꼴을 들고 있다.
그중 하나는 실제로 그렇게 났다: `shp_zip_multi` 가 zip 하나당 shp 하나를
가정해 첫 장만 읽었고, 그 장이 bbox 밖이라 **970MB 를 읽고 0건에 status
OK** 였다(2026-08-30).

IN    없음 (합성 zip · CSV · JSON · shapefile)
OUT   없음 (검사)
PARAM 없음
밖    **실물 레이크를 안 읽는다.** `read_ngii1k` 은 도엽 묶음(74+143)을
      열어야 돌아서 여기 못 든다 — 아래 전수 관문이 그것을 **사유와 함께**
      예외로 적는다(§69). 그리고 **좌표가 옳은가도 안 본다** — 절단 상자와
      좌표계는 `_io` 쪽이고 `tests/test_read_dispatch.py` 가 든다.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from firelane.read import READERS
from firelane.read._io import BBOX_4326
from firelane.read.ctx import Ctx

#: 상자 **안**의 한 점. 수를 손으로 적지 않는다.
LON = (BBOX_4326[0] + BBOX_4326[2]) / 2
LAT = (BBOX_4326[1] + BBOX_4326[3]) / 2


def _ctx(tmp_path: Path, e: dict, src: Path, hits: list[Path] | None = None) -> Ctx:
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    return Ctx(key="k", e=e, src=src, hits=hits or [src], crs="EPSG:5186",
               tmp=tmp_path, out=out, rec={"key": "k"}, save=lambda *a, **k: {})


# ── 전수 관문 ────────────────────────────────────────────────
#: 여기서 못 미는 갈래. **사유 없이 넣지 않는다**(§69).
UNPUSHABLE = {
    "read_ngii1k": "도엽 묶음(SHP 74 + NGI 143)을 열어야 돈다 — 레이크가 "
                   "있어야 하고, 합성으로 지으면 그 합성이 실물과 다른 꼴이 된다",
}


def test_every_dispatch_branch_has_a_test_that_names_it():
    """★ 본체. `READERS` 의 **모든** 갈래를 어느 시험이 이름으로 부른다.

    새 kind 를 표에 더하면 그 갈래를 미는 자리가 같이 생겨야 한다 — 안
    생기면 그 갈래는 **처음 돌는 날** 사람이 발견한다(이 저장소가 그렇게
    `shp_zip_multi` 와 `text_table` 을 겪었다).
    """
    import re

    root = Path(__file__).resolve().parents[1]
    hay = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((root / "tests").rglob("*.py")))
    names = {f.__name__ for f in READERS.values()}
    assert len(names) >= 10, f"갈래가 {len(names)}개 — 표를 못 읽었다"
    gap = sorted(n for n in names
                 if n not in UNPUSHABLE
                 and not re.search(rf"\b{re.escape(n)}\b", hay))
    assert not gap, ("시험이 이름으로도 안 부르는 갈래:\n  " + "\n  ".join(gap)
                     + "\n  ★ 못 미는 것이면 `UNPUSHABLE` 에 **사유와 함께** 적어라")
    # ★ 예외표가 실재하는 갈래만 든다 — 죽은 예외는 다음 사람을 속인다
    assert set(UNPUSHABLE) <= names, sorted(set(UNPUSHABLE) - names)


# ── zip 을 **그 zip 만의 빈 폴더**에 푼다 ────────────────────
def test_unzip_own_gives_each_zip_its_own_empty_folder(tmp_path):
    """★ §181-4 — 종전에는 모두 `.work` 한 곳에 풀고 `rglob` 로 찾았다.

    앞 소스가 푼 같은 이름의 shp 가 남아 있으면 **엉뚱한 판을 조용히 읽는다**
    (`next()` 가 첫 것을 집는다). 그래서 폴더가 zip 마다 다르고, 풀기 전에
    비운다.
    """
    from firelane.read._io import unzip_own

    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    with zipfile.ZipFile(a, "w") as z:
        z.writestr("same.txt", "A")
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("same.txt", "B")
    da = unzip_own(a, tmp_path / "work")
    db = unzip_own(b, tmp_path / "work")
    assert da != db, "두 zip 이 같은 폴더에 풀린다"
    assert (da / "same.txt").read_text(encoding="utf-8") == "A"
    assert (db / "same.txt").read_text(encoding="utf-8") == "B"


def test_unzip_own_wipes_what_was_there_before(tmp_path):
    """★ 다시 풀면 **앞 실행의 잔재가 없다.** 남으면 그것이 읽힌다."""
    from firelane.read._io import unzip_own

    zp = tmp_path / "a.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("new.txt", "새것")
    d = unzip_own(zp, tmp_path / "work")
    (d / "옛것.txt").write_text("남은 것", encoding="utf-8")
    again = unzip_own(zp, tmp_path / "work")
    assert sorted(p.name for p in again.iterdir()) == ["new.txt"]


# ── zip 안 대용량 CSV ────────────────────────────────────────
def test_csv_points_in_zip_finds_a_member_whose_name_was_mangled(tmp_path):
    """★ zip 내부 한글 이름이 **CP437 로 깨져** 들어온다 — 되돌려 매칭한다.

    되돌리지 않으면 「zip 안에 그 파일이 없다」가 되고, 실제로 있는데
    없다고 하는 그 자리가 juso zip 이다.
    """
    from firelane.read.delimited import read_csv_points_in_zip

    body = f"이름,경도,위도\n소방서,{LON},{LAT}\n".encode()
    mangled = "소방시설.csv".encode("cp949").decode("cp437")
    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr(mangled, body)
    g = read_csv_points_in_zip(_ctx(tmp_path, {
        "inner_contains": "소방시설", "x_col": "경도", "y_col": "위도"}, zp))
    assert len(g) == 1 and g["이름"].tolist() == ["소방서"]


def test_csv_points_in_zip_reads_the_declared_encoding(tmp_path):
    """★ 대장의 `encoding` 을 읽는다 — 하드코딩하면 대장이 무엇을 적든 무시된다."""
    from firelane.read.delimited import read_csv_points_in_zip

    body = f"이름,경도,위도\n충장로,{LON},{LAT}\n".encode("cp949")
    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("a.csv", body)
    g = read_csv_points_in_zip(_ctx(tmp_path, {
        "inner_contains": "a.csv", "encoding": "cp949",
        "x_col": "경도", "y_col": "위도"}, zp))
    assert g["이름"].tolist() == ["충장로"]


def test_csv_points_in_zip_dies_when_the_member_is_missing(tmp_path):
    """없으면 **죽고 내부 목록을 보여 준다** — 빈 표를 내지 않는다."""
    from firelane.read.delimited import read_csv_points_in_zip

    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("other.csv", b"a\n1\n")
    with pytest.raises(FileNotFoundError, match="없는것"):
        read_csv_points_in_zip(_ctx(tmp_path, {
            "inner_contains": "없는것", "x_col": "x", "y_col": "y"}, zp))


# ── 표 갈래 둘 ───────────────────────────────────────────────
def test_csv_table_keeps_every_column_as_text(tmp_path):
    """★ `dtype=str` — 법정동코드 `0100` 이 `100` 이 되면 조인이 깨진다."""
    from firelane.read.delimited import read_csv_table

    p = tmp_path / "a.csv"
    p.write_text("코드,값\n0100,1\n0200,2\n", encoding="utf-8")
    c = _ctx(tmp_path, {}, p)
    got = read_csv_table(c)
    assert got["features"] == 2 and got["columns"] == ["코드", "값"]
    text = (c.out / "k.csv").read_text(encoding="utf-8-sig")
    assert "0100" in text.splitlines()[1], text


def test_json_table_accepts_the_two_declared_wrappers(tmp_path):
    """★ `records`(표준데이터) · `Data`(건축행정시스템) **둘만** 받는다.

    머리말이 「셋째가 나오면 그때 대장에 선언하게 하지 코드가 추측하지
    않는다」를 적는다. 그 선택을 못박는다 — 모르는 래퍼는 **0행**이고,
    0행은 아래 `ingest` 가 보는 수다.
    """
    from firelane.read.jsondoc import read_json_table

    rows = [{"a": "1"}, {"a": "2"}]
    for wrap in ({"records": rows}, {"Data": rows}, rows):
        p = tmp_path / "t.json"
        p.write_text(json.dumps(wrap, ensure_ascii=False), encoding="utf-8")
        assert read_json_table(_ctx(tmp_path, {}, p))["features"] == 2, wrap

    p = tmp_path / "t.json"
    p.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    assert read_json_table(_ctx(tmp_path, {}, p))["features"] == 0, (
        "모르는 래퍼를 추측해서 읽었다")


def test_json_points_cuts_by_the_box_and_drops_bad_coordinates(tmp_path):
    """상자 밖과 숫자가 아닌 좌표는 떨어진다 — CSV 갈래와 **같은 규율**이다."""
    from firelane.read.jsondoc import read_json_points

    p = tmp_path / "t.json"
    p.write_text(json.dumps({"records": [
        {"이름": "안", "경도": LON, "위도": LAT},
        {"이름": "밖", "경도": 127.5, "위도": 36.5},
        {"이름": "글자", "경도": "없음", "위도": "없음"},
    ]}, ensure_ascii=False), encoding="utf-8")
    g = read_json_points(_ctx(tmp_path, {"x_col": "경도", "y_col": "위도"}, p))
    assert g["이름"].tolist() == ["안"]
    assert g.crs.to_epsg() == 4326


# ── zip 하나에 shp 여럿 ──────────────────────────────────────
def test_shp_zip_multi_reads_every_piece_not_just_the_first(tmp_path):
    """★ 본체. zip 안 조각 **전부**를 읽는다.

    2026-08-30 — 첫 장만 읽었고 그 장이 bbox 밖이라 **970MB 를 읽고 0건에
    status OK** 였다. 대장이 `parts` 로 조각 수를 이미 적고 있었는데
    읽는 곳이 없었다 — 「선언이 있는데 읽는 곳이 없으면 그 선언은 주석이다」.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    from firelane.read.shapefile import read_shp_zip_multi

    sd = tmp_path / "src"
    sd.mkdir()
    # ★ 첫 조각은 **상자 밖**이다 — 첫 장만 읽으면 0건이 된다
    far = gpd.GeoDataFrame({"이름": ["먼곳"]},
                           geometry=[Point(100000, 100000)], crs=5186)
    near = gpd.GeoDataFrame({"이름": ["동명동"]},
                            geometry=[Point(192700, 283600)], crs=5186)
    far.to_file(sd / "a_1.shp", encoding="cp949")
    near.to_file(sd / "a_2.shp", encoding="cp949")
    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for f in sorted(sd.iterdir()):
            z.write(f, f.name)

    c = _ctx(tmp_path, {"layer": "a.shp", "encoding": "cp949"}, zp)
    got = read_shp_zip_multi(c)
    assert got is not None, "아무것도 안 냈다"
    names = got["이름"].tolist() if hasattr(got, "columns") else []
    assert "동명동" in names, f"뒤 조각을 안 읽었다 — {names}"


# ── 같은 파일종은 **같은 기본값**으로 읽는다 (§498) ───────────
def test_branches_of_one_file_family_share_their_encoding_default():
    """★ `shp` 갈래 둘의 인코딩 기본값이 같은가.

    §498 까지 갈려 있었다 — `shp_zip` 은 `cp949`, `shp_zip_multi` 는
    `utf-8`. **같은 파일종**(국내 shp 의 dbf · 거의 전부 CP949)을 읽는
    자리이고, `utf-8` 로 읽으면 `UnicodeDecodeError` 로 터지거나 글자가
    깨진다. 지금은 세 항목이 전부 `encoding` 을 적어서 안 돌지만,
    **안 적은 항목이 하나 들어오면 그날 터진다.**

    ★ 기본값을 손으로 적은 자리가 일곱이고 답이 셋이다. 이 시험이 드는 것은
      그중 **한 족(shp)이 한 답을 쓰는가**다. 나머지 족은 쓰는 법이 달라
      (`read_csv_any` 가 되돌리므로 첫 추측일 뿐) 같은 잣대로 못 묶는다 —
      묶으려면 `ledger.delimiter_of` 처럼 **대장 모듈에 문 하나**를 세우는
      배치가 필요하고, 그것은 이 배치 밖이다.
    """
    import re

    src = (Path(__file__).resolve().parents[1]
           / "src/firelane/read/shapefile.py").read_text(encoding="utf-8")
    got = set(re.findall(r'e\.get\("encoding",\s*"([^"]+)"\)', src))
    assert got == {"cp949"}, f"shp 갈래의 기본값이 갈렸다 — {sorted(got)}"
    assert len(re.findall(r'e\.get\("encoding"', src)) == 2, (
        "읽는 자리 수가 바뀌었다 — 새 갈래가 생겼으면 그 기본값도 같은지 보라")
