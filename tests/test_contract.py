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
    "seg_uid": str,
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
    """app.js 가 읽는 web/data 파일이 실제로 있어야 한다.

    ★ 정규식으로 fetch 배열을 긁던 방식은 폐기했다. app.js 의 표현이 조금만
      바뀌어도 엉뚱한 배열을 잡는다(2026-08-14 에 "a" 를 파일명으로 오인).
      이제 근거는 두 곳이다 — app.js 의 BASE 선언과 config.js 의 marker.data.
    """
    import re
    js = _read("app.js")
    cfg = _read("config.js")

    m = re.search(r'const\s+BASE\s*=\s*\[([^\]]*)\]', js)
    assert m, "app.js 에 const BASE = [...] 선언이 없다"
    names = set(re.findall(r'"([\w_]+)"', m.group(1)))

    # 마커 데이터는 config.js 의 spec.data 가 정본이다.
    names |= set(re.findall(r'\bdata\s*:\s*"([\w_]+)"', cfg))

    m2 = re.search(r'const\s+FILES\s*=\s*\{([^}]*)\}', js)
    alias = dict(re.findall(r'(\w+)\s*:\s*"([\w_]+)"', m2.group(1))) if m2 else {}

    assert names, "읽을 데이터 파일 목록이 비었다"
    for n in sorted(names):
        f = alias.get(n, n)
        assert (WEBDIR / "data" / f"{f}.geojson").exists(), \
            f"web/data/{f}.geojson 없음 (선언: {n})"


def test_marker_spec_self_contained():
    """마커 스펙이 자기 데이터·팝업을 들고 있어야 한다.

    ★ 2026-08-14 리팩의 계약이다. 가로등 마커 하나를 추가하는 데 6곳을
      고쳐야 했던 것이 계기였다. app.js 에 손딕셔너리가 되살아나면 여기서 걸린다.
    """
    import re
    js = _read("app.js")
    cfg = _read("config.js")
    assert "MK_SRC = {" not in js, "MK_SRC 손딕셔너리가 되살아났다. spec.data 를 쓸 것"
    assert "const POPUP={" not in js, "POPUP 손딕셔너리가 되살아났다. spec.popup 을 쓸 것"
    assert 'spec.id === "m-' not in js, "마커 id 특수분기가 생겼다. 선언으로 뺄 것"
    ids = re.findall(r'\bid\s*:\s*"(m-[\w-]+)"', cfg)
    assert len(ids) >= 5, f"마커 스펙이 부족하다: {ids}"
    for i in ids:
        assert f'"{i}"' not in _read("index.html"), \
            f"index.html 에 {i} 토글이 손으로 박혀 있다. app.js 가 생성한다"


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
def test_optional_layers_not_silently_empty(seg):
    """
    조용한 결측 방어.

    2026-08-14: raw 폴더를 gjcity/ 로 옮겼는데 segments.py 가 옛 경로를 읽고 있었다.
    glob 이 빈 리스트를 돌려줬고 `if _lp:` 가 그냥 지나가서
    light_count 가 전부 0 인 채 파이프라인이 "OK" 를 찍었다.
    '있어야 할 데이터가 0건'은 정상이 아니다.
    """
    P = [f["properties"] for f in seg["features"]]
    n = sum(1 for p in P if p.get("light_count"))
    assert n > 0, "light_count 전부 0 — 가로등 CSV 경로 확인 (RAW/gjcity/*streetlight*.csv)"


# ── seg_uid ──────────────────────────────────────────────────
# seg_id 는 실행마다 갈린다(1266→1087 때 전부 밀렸다). 외부(실측 DB·영상판정·
# 향후 DB PK)가 붙을 키는 seg_uid 하나뿐이므로 형식과 유일성을 계약으로 고정한다.
import re

SEG_UID_RE = re.compile(r"^[A-Z]{2}-\d{6}-\d{6}-[0-9A-Z]{4}$")


def test_seg_uid_format(seg):
    """형식이 깨지면 파싱하는 쪽(로그·DB·야장)이 전부 깨진다."""
    for f in seg["features"]:
        u = f["properties"]["seg_uid"]
        assert SEG_UID_RE.match(u), f"seg_uid 형식 위반: {u}"


def test_seg_uid_unique(seg):
    """
    중복은 중점이 1m 안에 겹치고 도로명도 같은 구간이 둘 이상이라는 뜻이다.
    접미사로 회피하면 다음 실행에 접미사 순서가 바뀌어 키가 또 갈린다.
    병합 규칙을 봐야 한다.
    """
    ids = [f["properties"]["seg_uid"] for f in seg["features"]]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"seg_uid 중복 {len(dup)}건: {sorted(dup)[:5]}"


def test_seg_uid_retention():
    """
    직전 실행 대비 유지율 90%. 무너지면 실측값이 미아가 된다.
    검증: NODE_TOL/SNAP_TOL 0.5 -> 0.6 에서 99.4% (2026-08-14)
    """
    import csv
    p = ROOT / "data" / "processed" / "seg_uid_map.csv"
    if not p.exists():
        pytest.skip("최초 실행 — 비교 대상 없음")
    prev = {r["seg_uid"] for r in csv.DictReader(p.open(encoding="utf-8"))}
    if not prev:
        pytest.skip("이력 없음")
    cur = {f["properties"]["seg_uid"]
           for f in json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))["features"]}
    ret = len(prev & cur) / len(prev)
    assert ret >= 0.90, f"seg_uid 유지율 {ret:.1%} — 키 규칙 재검토"
