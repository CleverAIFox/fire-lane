"""N1.1 — 목적지 검색 색인 · 건물 발행 범위 · zip 해제 격리 · 대장 layer 칸. (DECISIONS §181)

표본 `tests/fixtures/n1/` 은 사용자 기계의 processed 앞 20줄 · 민원행정기관 동명동 bbox 64 이다.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from firelane import destinations as D
from firelane import lake, ledger

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "tests" / "fixtures" / "n1"
MOVE = box(126.9095, 35.1431, 126.9438, 35.1593)       # view.maxBounds (2026-09-17 실측)
RD = dict(dtype=str, keep_default_na=False, encoding="utf-8-sig")


def _build():
    return pd.read_csv(FX / "navi_build.csv", **RD)


def _jibun():
    return pd.read_csv(FX / "navi_jibun.csv", **RD)


def _civil():
    c = pd.read_csv(FX / "civil_office.csv", dtype=str)
    return gpd.GeoDataFrame(c, geometry=gpd.points_from_xy(c["위치X"].astype(float), c["위치Y"].astype(float)),
                            crs=5179)


def test_column_numbers_match_guide():
    """§181-1 — 가이드 붙임 1 · 2 의 열 번호가 표본의 모양과 맞는다. 번호가 밀리면 여기서 운다."""
    b, j = _build(), _jibun()
    assert b.shape[1] == 33 and j.shape[1] == 20
    assert b[D.B_PK].str.fullmatch(r"\d{25}").all(), "c10 이 건물관리번호(25자리)가 아니다"
    assert set(b[D.B_APT]) <= {"0", "1", "2"}, "c17 이 공동주택구분이 아니다"
    for col, lo, hi in ((D.B_CX, 9.3e5, 9.7e5), (D.B_CY, 1.67e6, 1.70e6),
                        (D.B_EX, 9.3e5, 9.7e5), (D.B_EY, 1.67e6, 1.70e6)):
        v = pd.to_numeric(b[col], errors="coerce").dropna()
        assert len(v) and v.between(lo, hi).all(), f"{col} 이 EPSG:5179 좌표 범위 밖이다"
    assert j[D.J_PK].str.fullmatch(r"\d{25}").all(), "지번 c18 이 건물관리번호가 아니다"
    assert b[D.B_ROAD].str.len().gt(0).all() and b[D.B_MAIN].str.fullmatch(r"\d+").all()


def test_coordinate_fallback_and_exclusion_are_counted():
    """출입구 → 중심점 → 제외. 비공개 건물(좌표 빈 값)은 빼고 **센다**."""
    b = _build().head(3).copy()
    b.loc[1, [D.B_EX, D.B_EY]] = ""                                  # 출입구만 없다 → 중심점
    b.loc[2, [D.B_EX, D.B_EY, D.B_CX, D.B_CY]] = ""                  # 둘 다 없다 → 뺀다
    out, st = D.from_navi(b, None)
    assert (st["entrance"], st["center"], st["no_coord"]) == (1, 1, 1)
    assert len(out) == 2
    got = out.to_crs(5179).geometry.iloc[0]
    row0 = b.iloc[0]
    assert got.distance(Point(float(row0[D.B_EX]), float(row0[D.B_EY]))) < 0.01, "출입구가 먼저가 아니다"


def test_same_address_keeps_one_main_building_with_jibun():
    out, st = D.from_navi(_build(), _jibun())
    assert st["same_addr"] > 0
    assert not out.duplicated(["name", "addr"]).any()
    r = out[out["addr"].str.startswith("동구 필문대로 230 ")].iloc[0]
    assert "동명동 18-12" in r["alt"], "지번이 붙은 본건물이 남아야 한다"
    assert set(out["cat"]) <= {"건물", "주소"}
    assert (out.loc[out["cat"].eq("주소"), "name"] != "").all(), "이름 없는 건물은 주소가 이름이다"


def test_index_merges_three_sources_inside_map_bounds():
    store = gpd.GeoDataFrame({"name": ["가게", "밖"], "cat": ["음식"] * 2, "sub": ["한식"] * 2, "addr": ["x"] * 2},
                             geometry=[Point(126.926, 35.151), Point(126.99, 35.2)], crs=4326)
    out, st = D.build_index(store, _build(), _jibun(), _civil(), MOVE)
    assert st["store"] == 1, "지도 이동 범위 밖 상가가 남았다"
    assert 0 < st["civil"] < 64, "관공서가 범위로 안 잘렸다"
    assert set(out["src"]) == {"store", "build", "civil"}
    assert list(out.columns) == D.COLS
    assert out.within(MOVE).all()
    civ = out[out["src"].eq("civil")]
    assert set(civ["cat"]) <= {"학교", "관공서"} and civ["cat"].eq("학교").any()
    again, _ = D.build_index(store, _build(), _jibun(), _civil(), MOVE)
    assert out.drop(columns="geometry").equals(again.drop(columns="geometry")), "순서가 결정적이지 않다"


def _shp_zip(path: Path, inner: str, n: int):
    d = path.parent / f"_{path.stem}"
    d.mkdir()
    g = gpd.GeoDataFrame({"k": list(range(n))},
                         geometry=[Point(126.92 + i * 1e-4, 35.15) for i in range(n)], crs=4326).to_crs(5179)
    g.to_file(d / inner)
    with zipfile.ZipFile(path, "w") as z:
        for f in d.iterdir():
            z.write(f, f.name)


def test_unzip_is_isolated_per_zip(tmp_path):
    """§181-4 · G-22 — 앞 zip 이 푼 같은 이름의 shp 를 뒤 zip 이 읽지 않는다. 글롭은 정확히 하나."""
    from firelane import ingest
    work = tmp_path / "work"
    work.mkdir()
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    _shp_zip(a, "X.shp", 2)
    _shp_zip(b, "X.shp", 5)
    assert len(ingest.load_shp_in_zip(a, "X.shp", "EPSG:5179", "utf-8", work)) == 2
    assert len(ingest.load_shp_in_zip(b, "X.shp", "EPSG:5179", "utf-8", work)) == 5, "앞 zip 의 X.shp 를 읽었다"
    assert len(ingest.load_shp_in_zip(b, "*.shp", "EPSG:5179", "utf-8", work)) == 5, "글롭이 다른 zip 폴더까지 봤다"
    two = tmp_path / "two.zip"
    with zipfile.ZipFile(two, "w") as z:
        for f in (tmp_path / "_a").iterdir():
            z.write(f, "p/" + f.name)
            z.write(f, "q/" + f.name)
    with pytest.raises(ValueError, match="하나여야"):
        ingest.load_shp_in_zip(two, "*.shp", "EPSG:5179", "utf-8", work)


def test_ingest_has_no_shared_extract():
    src = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
    assert not re.search(r"extractall\(tmp\)", src), "공용 .work 에 푸는 자리가 돌아왔다(G-22)"


def test_ledger_layer_is_never_a_lake_layer():
    """§181-5 · G-21 — `layer` 는 zip 안 레이어 이름 칸이다. 레이크 층 이름(raw …)을 적으면
    shp_zip 으로 바꾸는 순간 계약 검사가 `raw 없음` 으로 운다."""
    y = ledger.load_sources()
    bad = [k for k, e in (y.get("datasets") or {}).items()
           if str((e or {}).get("layer", "")) in (*lake.LAYERS, *lake.ABOLISHED)]
    assert not bad, f"layer 칸에 레이크 층 이름 — {bad}"
    assert y["datasets"]["civil_office"]["kind"] == "shp_zip"


def test_publish_and_navi_are_wired_to_dest():
    pub = (ROOT / "src/firelane/publish_web.py").read_text(encoding="utf-8")
    assert 'W/"dest.geojson"' in pub and "build_index(" in pub
    assert "b.intersects(move)" in pub and "b.intersects(scope)" not in pub, "건물이 스코프로 잘린다"
    from firelane import pipeline
    pub_step = next(s for s in pipeline.STEPS if s.name == "publish")
    names = {p.name for p in pub_step.reads + pub_step.writes}
    assert {"navi_build.csv", "navi_jibun.csv", "civil_office.geojson", "dest.geojson"} <= names
    ds = (ROOT / "web/navi/src/infra/dataSource.ts").read_text(encoding="utf-8")
    assert '"dest.geojson"' in ds and '"poi.geojson"' not in ds
    se = (ROOT / "web/navi/src/domain/search.ts").read_text(encoding="utf-8")
    assert not re.search(r"hits\.length\s*>\s*limit", se), "넓은 질의에서 관공서를 자르던 조기 종료가 돌아왔다"


def test_no_doc_sends_people_to_old_pages_domain():
    """§181-6 — 배포 주소는 cleveraifox.github.io 다. 옛 조직 주소는 이관 전 배포라 낡은 지도를 보여준다.
    기록(DECISIONS) · 이관 전 등록 도메인 주석(web/config.js)만 허용한다."""
    allow = {"docs/DECISIONS.md", "web/config.js", "tests/test_n1.py"}
    skip = {".git", ".venv", "node_modules", "dist", "__pycache__", "baseline", "terrain", "ortho"}
    hits = []
    for p in ROOT.rglob("*"):
        if (not p.is_file() or skip & set(p.relative_to(ROOT).parts)
                or p.suffix not in {".md", ".py", ".js", ".ts", ".tsx", ".json", ".yml", ".yaml", ".sh",
                                    ".html", ".toml", ".example", ".txt"}
                or p.name.endswith(".geojson")):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in allow:
            continue
        try:
            if "woongtopia.github.io" in p.read_text(encoding="utf-8", errors="ignore"):
                hits.append(rel)
        except OSError:
            continue
    assert not hits, f"옛 배포 주소를 안내한다 — {hits}"
    assert "cleveraifox.github.io/fire-lane/navi/" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_deployed_surface_table_matches_web():
    """README 의 배포면 표가 **`web/` 실물과 같은가.**  (§258)

    ★ 2026-09-25 실제 사고. 2026-09-22 에 옛 GIS 지도(`web/js` · `style.css`)를
      걷어내면서 `web/index.html` 을 관제로 튕기는 `meta refresh` 한 줄로 바꿨다.
      그런데 README 와 MASTER 는 그 주소를 계속 **「지도」**라고 적었다. 세 달째
      쓰는 사람이 「지도」를 누르면 관제로 튕긴다.

      `doc_fsck ②` 는 **경로가 실재하는지만** 본다 — 리다이렉트도 실재하므로
      조용했다. 「범위가 이름보다 좁다」 그 족(W3-8)이고, **딱지의 참을 보는
      검사가 없으면 딱지는 조용히 낡는다.**

    두 방향으로 잰다.
      ㉠ 표가 드는 경로마다 `web/` 아래 실물이 있다.
      ㉡ 그 실물이 **리다이렉트**면 `build-navi` 가 그 자리에 빌드본을 앉힌다고
         선언돼 있어야 한다. 로컬에는 빌드본이 없으니 저장소 파일은 리다이렉트로
         남는 것이 정상이고, **아무도 안 채우는 리다이렉트를 화면이라 부르는 것**이
         결함이다.

    밖  화면의 내용이 딱지와 맞는지는 안 본다(그건 내비 시험 소관). 배포가 실제로
        앉히는지도 안 본다 — 그건 `deploy.yml` 시운전이 `__FL_VIEW` 로 잰다.
    """
    import re as _re

    md = (ROOT / "README.md").read_text(encoding="utf-8")
    block = _re.search(r"```\n((?:[^\n]*cleveraifox[^\n]*\n)+)```", md)
    assert block, "README 의 배포면 표를 못 찾았다 — 표기가 바뀌었으면 이 시험을 고쳐라"
    rows = [ln for ln in block.group(1).splitlines() if "cleveraifox" in ln]
    assert len(rows) >= 4, f"배포면이 {len(rows)}줄 — 표를 덜 읽었다"

    # ★ 리다이렉트가 화면 자리에 있어도 된다 — **배포가 그 자리에 빌드본을
    #   앉히는 경우에만.** 로컬 `serve.py` 에는 빌드본이 없으므로 저장소의
    #   루트 파일은 리다이렉트로 남는다. 그래서 여기서 보는 것은 「딱지가 거짓인가」
    #   가 아니라 **「누가 그 자리를 채우는가가 선언돼 있는가」** 다.
    seats = (ROOT / ".github/actions/build-navi/action.yml").read_text(encoding="utf-8")
    bad = []
    for ln in rows:
        # ★ 딱지에 공백이 있다(「협업 방침」) — 자리로 가르지 않고 주소를 찾는다.
        m = _re.search(r"cleveraifox\.github\.io/fire-lane/(\S*)", ln)
        assert m, ln
        label = ln[: m.start()].strip()
        url, path = m.group(0), m.group(1).split("?", 1)[0]
        f = ROOT / "web" / (path if path.endswith(".html") else path + "index.html")
        if not f.is_file():
            bad.append(f"  {label}  {url} → web/{f.relative_to(ROOT / 'web')} 이 없다")
            continue
        body = f.read_text(encoding="utf-8", errors="ignore")
        redirect = "http-equiv=\"refresh\"" in body or "http-equiv='refresh'" in body
        rel = f.relative_to(ROOT / "web").as_posix()
        if redirect and f"> {rel}" not in seats and f"> {rel}\n" not in seats:
            bad.append(f"  {label}  {url} 의 {rel} 은 리다이렉트인데 "
                       f"`build-navi` 가 그 자리에 빌드본을 앉히지 않는다")
    assert not bad, (
        "배포면 표가 실물과 다르다\n" + "\n".join(bad)
        + "\n  딱지를 실물에 맞춘다. 화면이 사라졌으면 그 줄을 지운다.\n"
        + "  리다이렉트를 화면 자리에 둘 거면 `build-navi` 가 거기에 빌드본을 앉혀야 한다.")


def test_contract_counts_navi_as_consumer():
    """§181-7 — 계약 테스트의 고아 검사가 내비를 소비자로 센다. 실물 web/data 없이도 여기서 운다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("contract_t", ROOT / "tests" / "test_contract.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    got = m.navi_reads()
    assert "dest.geojson" in got, "내비가 읽는 dest.geojson 을 못 본다 — 발행 기계에서 계약이 선다"
    assert {"navi_graph.json", "poi.geojson"} <= got, "프로브가 죽었다"


def test_destinations_are_clipped_to_dongmyeong_only():
    """§183-1 — 목적지는 동명동 경계(emd4)로 자른다. 건물 · 라벨은 지도 이동 범위(move)로 넓다."""
    pub = (ROOT / "src/firelane/publish_web.py").read_text(encoding="utf-8")
    call = pub[pub.index("_dest.build_index("):]
    call = call[:call.index("\n    dest.to_file")]
    assert call.rstrip().endswith("emd4)"), "목적지가 동명동이 아닌 범위로 잘린다"
    assert "b.intersects(move)" in pub, "건물은 지도 이동 범위 그대로여야 한다"
