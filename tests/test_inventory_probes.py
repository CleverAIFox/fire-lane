#!/usr/bin/env python3
"""
test_inventory_probes.py — **원본에 무엇이 들어 있는지 재는 자들.** (§499)

── 왜 생겼나 ───────────────────────────────────────────────────
`firelane.inventory` 의 존재 이유는 머리말에 있다 — 같은 EDA 를 세 번 반복하고
그러다 **A0020000 의 도로폭·일방통행을 통째로 버리고 있던 걸** 뒤늦게
발견했다. 「버린 줄도 몰랐던 이유는 무엇이 있는지 적힌 곳이 없어서다.」

그 「적는 자」가 일곱(`probe_csv` · `probe_delim` · `probe_json` ·
`probe_shp_zip` · `probe_csv_in_zip` · `probe_ngi_dir` · `probe_raw_only`)이고
`tools/srccov.py` 가 전부 「시험이 이름으로도 안 부른다」로 셌다(§493 · §497).

★ 일곱이 **같은 규율 하나**를 진다 — **던지지 않는다.** 한 파일이 깨졌다고
  훑기가 죽으면 나머지 71종의 사실이 안 적히고, 그러면 이 도구는 **있으나
  없으나**가 된다. 깨진 것은 `error` 칸으로 적는다.

IN    없음 (합성 CSV · 텍스트 · JSON · zip)
OUT   없음 (검사)
PARAM 없음
밖    **`unused` 판정은 안 본다** — 「원본에 있는데 src 가 안 쓰는 속성」은
      `tools/unusedcheck.py` 와 대장 `feeds_why` 가 든다(§317).
      **대장에 적는 일도 안 본다** — AUTO 블록 쓰기는 `collect` 소관이고
      그쪽은 실물 레이크가 있어야 돈다.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from firelane import inventory as inv


def _cp949(p: Path, text: str) -> Path:
    p.write_bytes(text.encode("cp949"))
    return p


# ── 전수 관문 ────────────────────────────────────────────────
def test_every_probe_in_the_registry_has_a_test_that_names_it():
    """★ `kinds.Kind.probe` 가 가리키는 **모든** 재는 자를 시험이 부른다.

    새 kind 를 더하면 `_PROBE_FN` 에 재는 자가 붙고(머리말의 4번), 그 자를
    미는 자리도 같이 생겨야 한다 — 안 생기면 그 probe 는 **실물 레이크가
    붙은 기계에서 처음 돌 때** 사람이 발견한다.
    """
    root = Path(__file__).resolve().parents[1]
    hay = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((root / "tests").rglob("*.py")))
    names = {f.__name__ for f in inv._PROBE_FN.values()
             if getattr(f, "__name__", "<lambda>") != "<lambda>"}
    # ★ 람다로 싸인 것(`ngi_dir`)은 이름이 안 남는다 — 안을 집어서 본다
    names.add("probe_ngi_dir")
    assert len(names) == 7, f"재는 자가 {len(names)}종 — 표를 못 읽었다"
    gap = sorted(n for n in names if not re.search(rf"\b{re.escape(n)}\b", hay))
    assert not gap, "시험이 이름으로도 안 부르는 probe:\n  " + "\n  ".join(gap)


def test_every_kind_has_a_probe():
    """★ 빈 그물 — kind 가 늘었는데 재는 자가 없으면 그 소스는 **안 적힌다.**"""
    from firelane.kinds import ALL

    assert set(inv.PROBES) == set(ALL), sorted(set(ALL) - set(inv.PROBES))
    assert all(callable(f) for f in inv.PROBES.values())


# ── 던지지 않는다 ────────────────────────────────────────────
def test_a_broken_file_becomes_an_error_field_not_an_exception(tmp_path):
    """★ 본체. 일곱이 **같이 지는 규율** — 깨진 것은 `error` 로 적는다.

    던지면 그 한 파일 때문에 나머지 71종의 사실이 안 적힌다.
    """
    bad_csv = tmp_path / "b.csv"
    bad_csv.write_bytes(b"\xff\xfe\x00\x00\x01\x02")
    assert inv.probe_csv([bad_csv])["files"][0]["error"] == "인코딩 판별 실패"

    bad_json = tmp_path / "b.json"
    bad_json.write_text("{깨짐", encoding="utf-8")
    assert "JSONDecodeError" in inv.probe_json([bad_json])["files"][0]["error"]

    not_zip = tmp_path / "b.zip"
    not_zip.write_bytes(b"NOT A ZIP")
    assert "error" in inv.probe_raw_only([not_zip])["files"][0]
    assert "error" in inv.probe_csv_in_zip([not_zip])["files"][0]
    assert "error" in inv.probe_shp_zip([not_zip])["archives"][0]


# ── CSV · 구분자 텍스트 ──────────────────────────────────────
def test_probe_csv_counts_rows_without_the_header(tmp_path):
    """★ 머리 줄은 **행이 아니다.** 세면 모든 소스의 건수가 하나씩 많아진다."""
    p = _cp949(tmp_path / "a.csv", "이름,값\n가,1\n나,2\n")
    got = inv.probe_csv([p])["files"][0]
    assert got["rows"] == 2 and got["fields"] == ["이름", "값"]
    assert got["encoding"] == "cp949" and got["bytes"] == p.stat().st_size


def test_probe_delim_counts_columns_and_says_there_is_no_header(tmp_path):
    """★ 구분자 텍스트는 **헤더가 없다** — 열 수만 세고 그 사실을 적는다.

    csv 로 재면 첫 행을 컬럼명으로 먹고 1행을 잃는다. 컬럼명은 파일에 없고
    제공처 활용가이드에만 있다.
    """
    p = _cp949(tmp_path / "c.txt",
               "1221010800|동명로|6.0\n1221010800|충장로|12.5\n")
    got = inv.probe_delim([p])["files"][0]
    assert got["cols"] == 3 and got["note"] == "헤더 없음"
    assert "fields" not in got, "없는 컬럼명을 지어냈다"


def test_probe_delim_looks_inside_a_zip_and_says_which_member(tmp_path):
    """전국 전체분이 zip 안 시도별 파일로 온다 — 어느 것을 봤는지 적는다."""
    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("adrdc_gwangju.txt", "a|b|c\n".encode("cp949"))
        z.writestr("adrdc_seoul.txt", "a|b\n".encode("cp949"))
    got = inv.probe_delim([zp])["files"][0]
    assert got["members"] == 2 and got["source"] == "adrdc_gwangju.txt"
    assert got["cols"] == 3


# ── JSON ─────────────────────────────────────────────────────
def test_probe_json_reads_the_two_wrappers_and_a_bare_list(tmp_path):
    """★ `records`(표준데이터) · `Data`(건축행정시스템) · 맨 리스트 셋이다.

    `read/jsondoc.py` 와 **같은 어휘**를 본다 — 갈리면 재는 수와 읽는 수가
    달라지고, 그 차이를 아무도 설명할 수 없다.
    """
    rows = [{"a": 1, "b": 2}]
    for wrap in ({"records": rows}, {"Data": rows}, rows):
        p = tmp_path / "d.json"
        p.write_text(json.dumps(wrap), encoding="utf-8")
        got = inv.probe_json([p])["files"][0]
        assert got["rows"] == 1 and got["fields"] == ["a", "b"], wrap


def test_probe_json_on_an_empty_table_says_zero_not_nothing(tmp_path):
    """0행이면 `rows: 0` 이고 `fields` 는 빈 목록이다 — 칸을 빼지 않는다."""
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"records": []}), encoding="utf-8")
    got = inv.probe_json([p])["files"][0]
    assert got["rows"] == 0 and got["fields"] == []


# ── zip ──────────────────────────────────────────────────────
def test_probe_raw_only_counts_entries_and_samples_a_few(tmp_path):
    """읽지 않는 갈래도 **무엇이 담겼는지**는 적는다. 표본은 여덟까지."""
    zp = tmp_path / "f.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for i in range(10):
            z.writestr(f"m{i}.txt", "x")
    got = inv.probe_raw_only([zp])["files"][0]
    assert got["entries"] == 10 and len(got["sample"]) == 8


def test_probe_raw_only_on_a_plain_file_records_only_its_size(tmp_path):
    """zip 이 아니면 안을 안 본다 — DEM·PDF 가 그 자리다."""
    p = tmp_path / "h.pdf"
    p.write_bytes(b"%PDF-1.4\n")
    got = inv.probe_raw_only([p])["files"][0]
    assert set(got) == {"file", "bytes"} and got["bytes"] == 9


def test_probe_csv_in_zip_names_the_member_it_read(tmp_path):
    """`zip!member` 꼴로 적는다 — 어느 파일의 필드인지 안 적으면 못 쓴다."""
    zp = tmp_path / "g.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("inner.csv", "이름,값\n가,1\n".encode("cp949"))
        z.writestr("readme.md", "무시된다")
    got = inv.probe_csv_in_zip([zp])["files"]
    assert len(got) == 1, "csv·txt 아닌 것을 읽었다"
    assert got[0]["file"] == "g.zip!inner.csv"
    assert got[0]["fields"] == ["이름", "값"]


def test_probe_shp_zip_honours_the_declared_layer(tmp_path):
    """★ 대장 `layer:` 가 정본이다 — 안 보면 같은 zip 을 쓰는 다섯 데이터셋이
    **전부 같은 54개 속성**을 보고하고 「무엇을 안 쓰는가」가 무의미해진다.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    sd = tmp_path / "src"
    sd.mkdir()
    gpd.GeoDataFrame({"길이": [1]}, geometry=[Point(0, 0)], crs=5186).to_file(
        sd / "road.shp", encoding="cp949")
    gpd.GeoDataFrame({"높이": [2]}, geometry=[Point(1, 1)], crs=5186).to_file(
        sd / "bldg.shp", encoding="cp949")
    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for f in sorted(sd.iterdir()):
            z.write(f, f.name)

    both = inv.probe_shp_zip([zp])
    assert set(both["layers"]) == {"road", "bldg"}, both["layers"]
    one = inv.probe_shp_zip([zp], layer="road.shp")
    assert set(one["layers"]) == {"road"}, one["layers"]
    assert both["archives"][0]["shp"] == 2


def test_probe_ngi_dir_samples_a_few_sheets_and_merges_layers(tmp_path):
    """★ 도엽 묶음은 **표본만** 본다(`NGI_SAMPLE`) — 3,102 파일을 다 파싱하면
    인벤토리가 몇 분씩 걸린다. 그리고 레이어는 도엽을 넘어 **합친다.**
    """
    sheet = ('<LAYER_START>\n$LAYER_NAME\n"A0020000"\n<DATA>\n$RECORD 1\n'
             'LINESTRING\n2\n0 0\n1 1\n<LAYER_END>\n')
    for i in range(inv.NGI_SAMPLE + 2):
        (tmp_path / f"s{i}.ngi").write_bytes(sheet.encode("cp949"))
    got = inv.probe_ngi_dir(tmp_path)
    assert got["file_count"] == {"ngi": inv.NGI_SAMPLE + 2, "shp": 0}
    assert got["sampled_sheets"] == inv.NGI_SAMPLE
    lay = got["layers"]["A0020000"]
    assert lay["sheets"] == inv.NGI_SAMPLE and lay["n_sample"] == inv.NGI_SAMPLE
    assert lay["geom_type"] == "LINESTRING"


# ── 적는 자 (DECISIONS §500) ─────────────────────────────────
def test_write_block_puts_the_scan_in_interim_and_only_a_pointer_in_the_ledger(
        tmp_path):
    """★ 2026-08-26 의 수선을 못박는다 — **스캔 결과는 `interim` 이 제자리다.**

    종전에는 `sources.yaml` 하단 AUTO 블록을 교체했고, 그 블록 하나가 대장
    2,986줄 중 **1,434줄**이었다. 사람이 쓰는 선언과 도구가 만드는 사실이
    한 파일에 섞여 있었다. 대장에는 `at` 만 남는다 — 어디를 보라는 안내다.
    """
    led = tmp_path / "sources.yaml"
    led.write_text("datasets:\n  a:\n    kind: csv_table\n"
                   "inventory:\n  at: 옛시각\n  path: interim/inventory.json\n",
                   encoding="utf-8")
    interim = tmp_path / "interim"
    inv.write_block({"at": "2026-10-12T00:00:00+09:00", "datasets": {"a": {"x": 1}}},
                    interim=interim, sources=led)

    got = json.loads((interim / "inventory.json").read_text(encoding="utf-8"))
    assert got["datasets"]["a"] == {"x": 1}

    text = led.read_text(encoding="utf-8")
    assert "  at: 2026-10-12T00:00:00+09:00" in text, "대장의 시각이 안 갱신됐다"
    assert "datasets" in text and "x: 1" not in text, (
        "스캔 결과가 대장에 들어갔다 — 그것이 2026-08-26 에 걷은 것이다")


def test_write_block_touches_exactly_one_line_of_the_ledger(tmp_path):
    """★ `count=1` 이다 — 다른 `at:` 줄까지 고치면 **남의 칸을 덮는다.**"""
    led = tmp_path / "sources.yaml"
    led.write_text("inventory:\n  at: 옛시각\nretired:\n  b:\n    at: 지난기록\n",
                   encoding="utf-8")
    inv.write_block({"at": "새시각", "datasets": {}},
                    interim=tmp_path / "i", sources=led)
    text = led.read_text(encoding="utf-8")
    assert "  at: 새시각" in text and "    at: 지난기록" in text, text
    assert text.count("새시각") == 1
