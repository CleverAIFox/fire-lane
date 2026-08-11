"""
test_contract.py — GIS ↔ UI 계약 검증

UI(web/index.html)가 의존해도 되는 것만 여기서 고정한다.
값은 실측 후 바뀐다. 구조는 안 바뀐다. 그 경계가 이 파일이다.

깨지면: GIS 쪽이 UI를 말없이 부순 것이다. 머지하기 전에 UI 담당과 합의할 것.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"

VERDICTS = {"clear", "needs_cv", "blocked", "unknown"}
REQUIRED = {
    "seg_id": str,
    "width_min_m": (float, int, type(None)),
    "width_max_m": (float, int, type(None)),
    "verdict": str,
    "width_verified": bool,
    "midpoint_fallback": bool,
    "inherited": bool,
    "route_usage": int,
    "length_m": (float, int),
}


@pytest.fixture(scope="module")
def seg():
    return json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))


def test_files_exist():
    for n in ["segments", "buildings", "boundary", "hydrants", "stations"]:
        assert (WEB / f"{n}.geojson").exists(), f"web/data/{n}.geojson 없음 → publish_web.py 실행"


def test_crs_is_4326(seg):
    """좌표계는 4326으로 고정. 5186으로 내보내면 지도가 아프리카 앞바다로 간다."""
    for f in seg["features"][:200]:
        for lon, lat in _coords(f["geometry"]):
            assert 126.8 < lon < 127.1, f"경도 이탈 {lon} — CRS가 4326이 아니다"
            assert 35.0 < lat < 35.3, f"위도 이탈 {lat} — CRS가 4326이 아니다"


def test_fields_present_and_typed(seg):
    """UI가 읽는 필드는 이름도 타입도 바뀌지 않는다."""
    for f in seg["features"]:
        p = f["properties"]
        for k, t in REQUIRED.items():
            assert k in p, f"{p.get('seg_id')}: 필드 '{k}' 누락"
            assert isinstance(p[k], t), f"{p.get('seg_id')}: '{k}' 타입 {type(p[k])}"


def test_verdict_vocabulary(seg):
    """판정 문자열은 이 4개뿐이다. 늘리면 UI 색 매핑에 구멍이 난다."""
    got = {f["properties"]["verdict"] for f in seg["features"]}
    assert got <= VERDICTS, f"미정의 verdict: {got - VERDICTS}"


def test_seg_id_unique(seg):
    ids = [f["properties"]["seg_id"] for f in seg["features"]]
    assert len(ids) == len(set(ids)), "seg_id 중복. 불변 키가 깨졌다"


def test_width_band_is_ordered(seg):
    """하한 <= 상한. 뒤집히면 폭 산출 로직이 잘못된 것이다."""
    bad = [p["seg_id"] for f in seg["features"] if (p := f["properties"])
           and p["width_min_m"] is not None and p["width_max_m"] is not None
           and p["width_min_m"] > p["width_max_m"] + 0.01]
    assert not bad, f"width_min > width_max: {bad[:5]}"


def test_schema_matches_data(seg):
    s = json.loads((WEB / "segments.schema.json").read_text(encoding="utf-8"))
    assert s["count"] == len(seg["features"]), "schema.count 와 실제 건수 불일치"
    assert s["crs"] == "EPSG:4326"
    assert set(s["fields"]) >= set(REQUIRED)


def test_buildings_have_height():
    """3D extrusion 재료. h 가 없거나 0이면 건물이 납작해진다."""
    b = json.loads((WEB / "buildings.geojson").read_text(encoding="utf-8"))
    for f in b["features"]:
        assert f["properties"]["h"] >= 3.3, "0층 건물은 1층(3.3m)으로 클리핑되어야 한다"


def _coords(g):
    t, c = g["type"], g["coordinates"]
    if t == "Point":
        yield c
    elif t in ("LineString", "MultiPoint"):
        yield from c
    elif t in ("Polygon", "MultiLineString"):
        for r in c:
            yield from r
    elif t == "MultiPolygon":
        for p in c:
            for r in p:
                yield from r


# ── 웹 정적 검증 ──────────────────────────────────────────────
# ★ 미니맵이 하루 종일 안 뜬 원인이 여기 걸렸을 문제였다.
#   index.html 에서 지운 요소(#s-use)를 app.js 가 계속 참조했고,
#   거기서 예외가 나 그 뒤 코드(폭 밴드·미니맵)가 통째로 안 돌았다.
#   화면 일부가 비는 건 눈에 보이지만 "절반이 안 뜨는" 건 원인 찾기가 어렵다.

WEBDIR = ROOT / "web"


def _read(name):
    return (WEBDIR / name).read_text(encoding="utf-8")


def test_web_dom_refs_exist():
    """app.js 가 참조하는 DOM id 가 index.html 에 전부 있어야 한다."""
    import re
    html, js = _read("index.html"), _read("app.js")
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = (set(re.findall(r'\$\("#([^"]+)"\)', js))
            | set(re.findall(r'getElementById\("([^"]+)"\)', js)))
    missing = used - ids
    assert not missing, f"index.html 에 없는 id 를 app.js 가 참조한다: {sorted(missing)}"


def test_web_toggle_targets_handled():
    """패널 토글(data-t)이 app.js 에서 처리되어야 한다."""
    import re
    html, js = _read("index.html"), _read("app.js")
    for t in set(re.findall(r'data-t="([^"]+)"', html)):
        key = "m-" if t.startswith("m-") else t
        assert f'"{t}"' in js or f'"{key}"' in js, f"토글 '{t}' 가 app.js 에서 처리되지 않는다"


def test_web_assets_linked():
    """index.html 이 분리된 파일들을 참조해야 한다."""
    html = _read("index.html")
    for a in ("style.css", "config.js", "app.js"):
        assert a in html, f"index.html 이 {a} 를 참조하지 않는다"
    assert "<style>" not in html, "index.html 에 인라인 <style> 이 있다. style.css 로 옮길 것"


def test_web_data_files_referenced():
    """app.js 가 읽는 web/data 파일이 실제로 있어야 한다."""
    import re
    js = _read("app.js")
    m = re.search(r'\[([^\]]*?)\]\s*\n?\s*\.map\(n=>j\(`\./data/\$\{n\}\.geojson`\)\)', js)
    if not m:
        m = re.search(r'\[((?:"[\w_]+",?\s*)+)\]', js)
    for n in re.findall(r'"([\w_]+)"', m.group(1)):
        assert (WEBDIR / "data" / f"{n}.geojson").exists(), f"web/data/{n}.geojson 없음"


# ── ETL 스크립트 계약 ────────────────────────────────────────
# ★ 같은 회귀가 세 번 반복됐다. 스크립트가 paths.py 를 안 쓰고 자체 RAW 를 정의하면
#   FIRE_LANE_RAW 환경변수가 무시되고 원본을 못 찾는다(전부 MISSING).
#   패치를 적용할 때마다 되돌아갔으므로 테스트로 고정한다.

ETL = ROOT / "src" / "etl"


def test_etl_uses_paths_module():
    """ETL 스크립트는 경로를 자체 정의하지 않고 paths.py 를 써야 한다."""
    import re
    for f in ("ingest.py", "segments.py", "terrain.py", "ortho.py", "publish_web.py"):
        src = (ETL / f).read_text(encoding="utf-8")
        own = re.findall(r'^(?:RAW|OUT|PROCESSED|WEB)[\w,\s]*=\s*ROOT.*$', src, re.M)
        assert not own, f"{f} 가 경로를 자체 정의한다: {own}. paths.py 를 쓸 것"
        assert "from paths import" in src, f"{f} 가 paths.py 를 import 하지 않는다"


def test_publish_z_is_optional():
    """z 는 terrain.py 산출물이므로 필수 컬럼이면 DEM 없이 파이프라인이 죽는다."""
    src = (ETL / "publish_web.py").read_text(encoding="utf-8")
    assert '"unknown_reason","z","geometry"' not in src, \
        "publish_web.py 가 z 를 필수 컬럼으로 요구한다. 선택 컬럼으로 둘 것"
