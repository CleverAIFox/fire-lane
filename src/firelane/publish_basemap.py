#!/usr/bin/env python3
"""
publish_basemap.py — 내비 바탕 지도의 **면**을 낸다. 도로면 · 보도.

IN    data/processed/ngii1k_5186.gpkg (수치지형도 1:1,000 도로경계 면)
      data/processed/road_rw_5186.gpkg (도로명주소 실폭도로 면)
      data/processed/ngii1k_walk_5186.gpkg (보도 면)
      data/processed/vworld_uq153_5186.gpkg (도시계획시설 — 공원 · 녹지 · 광장 · 공공공지 면 · 행 144 · 닫힘)
      data/processed/vworld_uq164_5186.gpkg (도시계획시설 — 학교 · 청사 · 문화 · 복지 · 대학 면 · UQV 분류 · DECISIONS §768)
      data/processed/jijeok_5186.gpkg (연속지적도 필지 — 지목은 `A5` 끝 글자 · 지목별로 합쳐 칠한다 · DECISIONS §768)
      web/data/view.json (maxBounds — 자르는 틀)
OUT   web/data/road_area.geojson · web/data/sidewalk.geojson · web/data/landuse.geojson · web/data/daeji.geojson
PARAM 단순화 SIMPLIFY_M · 좌표 자릿수 PREC · 크기 상한 SIZE_MAX · LANDUSE_SIZE_MAX · GREEN_WORDS

── 왜 생겼나 (2026-09-22 · DECISIONS §213-4) ─────────────────────
「대비가 없다」. 내비가 도로를 **판정 구간의 중심선**(1,281개)으로만 그렸다.
흰 선 위에 흰 건물이라 길과 블록이 안 갈렸고, 스코프 밖 길은 아예 없었다.
와이어프레임 09-21 은 짙은 아스팔트 면 위에 밝은 건물이다.

면 데이터는 **이미 있었다** — 폭 판정이 쓰는 수치지형도 도로경계 면과, 그것이
못 그리는 최협소 골목을 메우는 실폭도로 면(sources.yaml `road_rw.note`). 판정에만
쓰고 화면에 안 올렸을 뿐이다. 새로 들이는 데이터는 없다.

★ **판정과 무관하다.** 여기서 내는 면은 색칠용이다. 폭은 여전히
  `segments.geojson` 의 `width_min_m` 이 말한다. 면의 모양으로 폭을 읽게 하지 않는다
  — 두 소스가 합쳐지고 0.4m 단순화된 면이다.

★ 두 소스를 **합친다(union).** 도엽 경계에서 겹치고, 실폭도로가 수치지도 위에
  반쯤 겹친다. 합치지 않으면 반투명일 때 겹친 자리가 짙게 보이고 파일이 두 배다.

★ 결정적이어야 한다. `커밋된 web/data 가 최신인가` 가 재실행과 바이트 대조를
  한다 — 좌표를 자릿수로 자르고 조각을 면적 · 중심으로 정렬한다.
"""
from __future__ import annotations

import json

import geopandas as gpd
import shapely
from shapely.geometry import MultiPolygon, box, mapping
from shapely.geometry.polygon import orient

from firelane.cli import no_args
from firelane.paths import ROOT

P = ROOT / "data" / "processed"
W = ROOT / "web" / "data"

#: 단순화(m). 0.4m 면 골목 모서리가 살고 파일이 1/3 이 된다
SIMPLIFY_M = 0.4
#: 좌표 자릿수. publish_web · publish_navi 와 같은 6자리(약 11cm)
PREC = 6
#: 산출 상한(두 파일 합). web/data 40MB 예산 안에서 이 몫을 못박는다
SIZE_MAX = 2 * 1024 * 1024

SOURCES = {
    "road_area": ["ngii1k_5186.gpkg", "road_rw_5186.gpkg"],
    "sidewalk": ["ngii1k_walk_5186.gpkg"],
}


#: 토지이용 면의 원천(`sources.yaml` 의 `vworld_uq153` · `ingest` 가 `<키>_5186.gpkg` 로 낸다). 대장의 `feeds` 가 이 파일을 소비처로 적는다 —
#: 그 선언이 참이려면 **이 코드가 그 키를 실제로 읽어야** 하고 `tests/test_basemap_geometry.py` 가 그것을 문다.
LANDUSE_STEM = "vworld_uq153"
LANDUSE_FILE = f"{LANDUSE_STEM}_5186.gpkg"
#: 토지이용 면 산출 상한 — 41면이 약 100KB 다. 도로면(`SIZE_MAX`)과 따로 못박는다(합치면 한쪽이 부풀어도 안 보인다)
LANDUSE_SIZE_MAX = 256 * 1024
#: `DGM_NM`(시설명)에 이 낱말이 들면 녹지 계열이고 나머지(공공공지 · 광장)는 포장 공지로 칠한다. **색의 갈래일 뿐 판정이 아니다.**
GREEN_WORDS = ("공원", "녹지", "유원지")

#: ★ 2026-11-13 (DECISIONS §768 · PLAN #231). 토지이용 면을 둘 더 읽는다 — 도시계획시설 `uq164`(분류 코드 `MNUM` 안의 `UQVnn`)와 연속지적도(지목 = `A5` 끝 글자).
INST_STEM = "vworld_uq164"
PARCEL_STEM = "jijeok"
#: 칠하지 않고 **경계선만** 내는 `UQVnn` — 대학(캠퍼스 안에 길이 있다). 그 밖에도 **면 하나의 전체 면적이 틀의 `BIG_FRAC` 를 넘으면** 경계선만이다(같은 이유).
CAMPUS_UQV = frozenset({"35"})
BIG_FRAC = 0.10
#: 지목(끝 글자) → 칠 갈래. **도로(`도`)는 뺀다**(도로면이 따로 그려진다) · **대지(`대`)는 `daeji.geojson` 이 따로 든다**(크기 — 합친 면의 약 3분의 2).
JM_BUCKET = {
    "임": "forest", "전": "farm", "답": "farm", "과": "farm", "목": "farm", "염": "farm", "광": "farm",
    "천": "water", "구": "water", "유": "water", "제": "water", "양": "water",
    "학": "inst", "종": "inst", "사": "inst", "묘": "inst",
    "공": "green", "체": "green", "원": "green",
}  # 그 밖(`차` `주` `창` `장` `철` `수` `잡` …)은 `paved` — `_jm_bucket`
#: 지목 면의 단순화(m) — 합친 면이라 골목 모서리가 아니라 **마당 · 필지 경계**다. 1m 로 0.04% 만 변한다(DECISIONS §768).
PARCEL_SIMPLIFY_M = 1.0
#: 대지 면은 더 거칠게(m) — 마당 · 필지 경계는 정보가 아니라 바탕이다. 파일 하나라 상한을 맞추는 자리가 여기뿐이다(DECISIONS §768)
DAEJI_SIMPLIFY_M = 2.0
#: 대지 파일의 상한 — 지목 하나라 지목별로 더 못 쪼개고(대지가 합친 면의 약 3분의 2) 타일은 고정 틀(약 2×2km)에 과하다. 단순화 2m 로 **325KB**(DECISIONS §768)라 384KB 로 못박는다
DAEJI_SIZE_MAX = 384 * 1024


def _frame() -> object:
    v = json.loads((W / "view.json").read_text(encoding="utf-8"))
    (x0, y0), (x1, y1) = v["maxBounds"]
    return gpd.GeoSeries([box(x0, y0, x1, y1)], crs=4326).to_crs(5186).iloc[0]


def _round(obj):
    if isinstance(obj, float):
        return round(obj, PREC)
    if isinstance(obj, (list, tuple)):
        return [_round(x) for x in obj]
    return obj


def union(name: str, frame):
    """`SOURCES[name]` 를 틀 안에서 합친 면(5186 · 단순화 전). 건물 발행도 이것을 쓴다(§217-3)."""
    parts = []
    for f in SOURCES[name]:
        path = P / f
        if not path.exists():
            raise SystemExit(f"★ {path} 가 없다 — ingest 를 먼저 돌려라. 빈 바탕을 조용히 내지 않는다")
        g = gpd.read_file(path)
        g = g[g.intersects(frame)]
        parts.extend(g.geometry.make_valid().intersection(frame))
    return gpd.GeoSeries(parts, crs=5186).union_all()


def _polys(geom):
    """어떤 기하에서든 **폴리곤만** 재귀로 꺼낸다.

    ★ 2026-09-26 (§260). `GeoSeries.explode()` 는 **한 겹만** 푼다.
      `make_valid` 가 내는 `GeometryCollection` 안에 `MultiPolygon` 이 들어 있으면
      한 번 풀어도 `MultiPolygon` 이 남고, `geom_type == "Polygon"` 거름망이
      그것을 **통째로 버린다.** 실제로 그렇게 도로면 1.22km² 가 0.03km² 가 됐다 —
      고치려던 자리에서 더 큰 것을 깨뜨렸다.
    """
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if hasattr(geom, "geoms"):
        return [q for g in geom.geoms for q in _polys(g)]
    return []                                        # 선·점은 면이 아니다


def _order(polys):
    """발행 순서. **바이트 안정성**이 목적이라 면적·중심으로 못박는다."""
    return sorted(polys, key=lambda p: (-round(p.area, 9),
                                        round(p.centroid.x, 9), round(p.centroid.y, 9)))


def rfc7946(p):
    """RFC 7946 §3.1.6 — 외곽은 반시계, 구멍은 시계. (§260-4)

    ★ 지금 쓰는 렌더러는 감김을 안 본다. 그래서 **화면으로는 안 드러나는** 위반이고,
      드러나지 않는 위반은 다음 소비자가 생길 때까지 조용하다. 벡터 타일러나
      다른 파서가 붙는 날 알아차리는 것보다 지금 한 줄이 싸다.

    ★ 건물은 `MultiPolygon` 이 섞여 온다 — `orient` 는 `Polygon` 만 받으므로 편다.
    """
    if p.geom_type == "MultiPolygon":
        return MultiPolygon([orient(q, sign=1.0) for q in p.geoms])
    return orient(p, sign=1.0) if p.geom_type == "Polygon" else p


def snap_orient(g, prec: int = PREC):
    """격자 스냅 → 유효화 → RFC 7946 감김. 폴리곤이 안 남으면 None. (§260-4)

    ★ **쓰기 직전에 이 순서로** 한다. 반올림은 기하를 깨뜨리므로 반올림보다 먼저
      고치면 소용이 없다 — §260 의 결함이 정확히 그것이었다. `publish_web` 이
      `COORDINATE_PRECISION=6` 으로 드라이버에게 반올림을 맡기는데, 그 반올림이
      shapely 가 맞춰 놓은 감김을 여섯 건 도로 뒤집었다. 여기서 격자에 먼저
      앉히면 드라이버의 반올림은 이미 격자 위인 수를 다시 쓸 뿐이다.

    ★ 두 발행기가 **같은 문**으로 이것을 한다. 두 벌이면 한 쪽만 고쳐진다.

    ★ 2026-10-12 (DECISIONS §495). **격자 앞에도 유효화가 온다.**
      `set_precision` 은 **유효한 기하만** 받는다 — 자기교차 폴리곤을 주면
      `TopologyException: side location conflict` 로 **터진다.** 지적·수치지도
      원본에 자기교차는 흔하고(`tools/jijeok_probe.py` 는 그래서 `buffer(0)` 을
      먼저 한다), 한 건만 있어도 발행이 멈춘다. 어느 피처인지도 안 말한다.
      그래서 `유효화 → 격자 → 유효화` 다. 머리말이 적은 §260 의 순서는
      그대로다 — **마지막이 격자 뒤의 유효화**이고, 거기가 요점이었다.
      ★ 유효한 기하에는 `make_valid` 가 **글자 그대로 같은 것**을 돌려준다
        (WKT 일치 · 아래 시험이 그것을 든다). 그래서 발행물은 안 바뀐다.
    """
    ps = _polys(shapely.make_valid(
        shapely.set_precision(shapely.make_valid(g), 10 ** -prec)))
    if not ps:
        return None
    return rfc7946(ps[0] if len(ps) == 1 else MultiPolygon(ps))


def build(name: str, frame) -> dict:
    polys = [g for g in _polys(union(name, frame).simplify(SIMPLIFY_M)) if g.area >= 1.0]
    out = gpd.GeoSeries(_order(polys), crs=5186).to_crs(4326)

    # ★ 2026-09-26 (§260). **반올림을 기하로 한다 — 좌표를 글자로 깎지 않는다.**
    #   `_round` 가 6자리(약 11cm)로 깎는데, 그 안쪽의 두 점이 같은 점이 되면
    #   작은 고리가 점 셋 이하로 찌그러지고 폴리곤 전체가
    #   `Too few points in geometry component` 로 무효가 된다. 실제로
    #   `road_area` 가 그랬다 — 외곽 1 + 구멍 826 중 하나가 찌그러져 전체가
    #   무효였고, 렌더러가 구멍 파기를 포기해 **외곽 4.2km² 가 통째로 칠해졌다.**
    #   화면에 도로망 대신 회색 슬래브가 떴다.
    #   격자에 먼저 스냅하면 `_round` 는 이미 격자 위인 수를 다시 쓸 뿐이다.
    #
    #   하중재는 `set_precision` 이다 — 그 한 줄을 빼면 아래 관문이 운다.
    #   `make_valid` 는 스냅이 고리를 무너뜨릴 때를 위한 안전벨트고, 이 데이터로는
    #   빼도 초록이다. 단순화 **직후**에도 한 번 걸어 뒀었는데 빼도 초록이라
    #   걷어냈다 — 첫 오진(「단순화가 범인」)의 잔해였다.
    # ★ 조각마다 따로 스냅하면 안 된다. 그렇게 했더니 이웃한 두 조각의 공유 경계가
    #   따로 움직여 3.9e-12 만큼 **겹쳤고**, 건물 몫을 도로면마다 더하는 아래 검사가
    #   같은 자리를 두 번 셌다(`test_road_polygons_do_not_overlap_each_other`).
    #   통째로 넘기면 GEOS 가 전체를 한 번에 노딩해 겹침 없는 결과를 보장한다.
    snapped = _order(_polys(snap_orient(shapely.union_all(list(out)))))

    # ★ 무효면 **조용히 내보내지 않는다.** 화면이 도로망 대신 슬래브를 그리는
    #   것이 정확히 그 대가였다. 이 관문이 없어서 결함이 커밋까지 갔다.
    if (bad := sum(0 if q.is_valid else 1 for q in snapped)):
        raise SystemExit(f"★ {name}: 무효 기하 {bad}건 — 조용히 발행하지 않는다")
    return {
        "type": "FeatureCollection",
        "name": name,
        "features": [
            {"type": "Feature", "properties": {},
             "geometry": _round(mapping(p))}
            for p in snapped
        ],
    }


def landuse_class(name: object) -> str:
    """시설명 → 칠 갈래. 낱말이 없거나 비면 `plaza` 다(없다고 녹지로 칠하지 않는다)."""
    return "green" if isinstance(name, str) and any(w in name for w in GREEN_WORDS) else "plaza"


def _jm_bucket(ch: object) -> str | None:
    """지목 끝 글자 → 칠 갈래. 도로(`도`)는 `None`(안 칠한다) · 대지(`대`)는 `daeji` 가 든다."""
    if not isinstance(ch, str) or not ch or ch in ("도", "대"):
        return None
    return JM_BUCKET.get(ch, "paved")


def _read(stem: str):
    path = P / f"{stem}_5186.gpkg"
    if not path.exists():
        raise SystemExit(f"★ {path} 가 없다 — `ingest` 를 먼저 돌려라(`--only {stem}`). 빈 토지이용 면을 조용히 내지 않는다")
    return gpd.read_file(path)


def _fc(items, lines, name: str) -> dict:
    """(갈래, 5186 폴리곤) 와 (갈래, 5186 선) 목록 → 결정적 FeatureCollection(4326 · 격자 · 감김 · 유효화)."""
    items.sort(key=lambda t: (-round(t[1].area, 9), round(t[1].centroid.x, 9), round(t[1].centroid.y, 9), t[0]))
    feats = []
    for cls, q in items:
        out = gpd.GeoSeries([q], crs=5186).to_crs(4326).iloc[0]
        fixed = snap_orient(out)
        if fixed is None:
            continue
        if not fixed.is_valid:
            raise SystemExit(f"★ {name}: 무효 기하 — 조용히 발행하지 않는다 ({cls})")
        feats.append({"type": "Feature", "properties": {"cls": cls}, "geometry": _round(mapping(fixed))})
    lines.sort(key=lambda t: (t[0], -round(t[1].length, 6), round(t[1].centroid.x, 6)))
    for cls, ln in lines:
        out = gpd.GeoSeries([ln], crs=5186).to_crs(4326).iloc[0]
        feats.append({"type": "Feature", "properties": {"cls": cls}, "geometry": _round(mapping(out))})
    return {"type": "FeatureCollection", "name": name, "features": feats}


def _lines(geom):
    """경계선 — 틀 안에서 자른 `LineString` 조각들."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    return [x for part in getattr(geom, "geoms", []) for x in _lines(part)]


def build_landuse(frame) -> dict:
    """토지이용 면 — 도시계획시설 둘(`uq153` · `uq164`)과 연속지적도 **지목별로 합친 면**(대지 · 도로 제외). (행 144 · 231)

    ★ 도시계획시설은 합치지(union) 않는다 — 합치면 갈래가 사라진다. 면마다 따로 격자 · 유효화 · 감김을 건다(`snap_orient`).
    ★ 지적도는 **필지마다가 아니라 지목마다 합친다** — 필지마다면 모자이크이고 경계선이 467km 다(DECISIONS §768). 도로 지목은 뺀다(도로면이 따로 그려진다).
    ★ `uq164` 의 **대학(UQV35)과 면 하나가 틀의 `BIG_FRAC` 를 넘는 면은 칠하지 않고 경계선만** 낸다(`campus` — 캠퍼스 안에 길이 있다).
    ★ **판정과 무관하다.** 폭에는 안 쓴다(`sources.yaml` 의 `used_for`). 칠하는 면일 뿐이다.
    ★ 원천이 없으면 죽는다 — 빈 바탕을 조용히 내지 않는다(`union` 과 같은 규율).
    """
    path = P / LANDUSE_FILE
    if not path.exists():
        raise SystemExit(f"★ {path} 가 없다 — `ingest` 를 먼저 돌려라. 빈 토지이용 면을 조용히 내지 않는다")
    g = gpd.read_file(path)
    g = g[g.intersects(frame)]
    items: list = []
    lines: list = []
    for geom, name in zip(g.geometry.make_valid().intersection(frame), g.get("DGM_NM", [None] * len(g)), strict=False):
        for q in _polys(geom.simplify(SIMPLIFY_M)):
            if q.area >= 1.0:
                items.append((landuse_class(name), q))
    # ── uq164 — UQV 분류 ──
    u = _read(INST_STEM)
    u = u[u.intersects(frame)]
    for geom, mnum in zip(u.geometry.make_valid(), u["MNUM"], strict=False):
        code = (str(mnum).split("UQV")[-1][:2]) if "UQV" in str(mnum) else ""
        clipped = geom.intersection(frame)
        if geom.area > BIG_FRAC * frame.area or code in CAMPUS_UQV:
            lines += [("campus", ln) for ln in _lines(geom.boundary.intersection(frame)) if ln.length >= 1.0]
            continue
        for q in _polys(clipped.simplify(SIMPLIFY_M)):
            if q.area >= 1.0:
                items.append(("inst", q))
    # ── 지적도 — 지목별로 합친 면(대지 · 도로 제외) ──
    p = _read(PARCEL_STEM)
    p = p[p.intersects(frame)].copy()
    p["_b"] = [_jm_bucket(x[-1:] if isinstance(x, str) and x[-1:].isalpha() else None) for x in p["A5"].astype(str)]
    for b, grp in p[p["_b"].notna()].groupby("_b"):
        merged = grp.geometry.make_valid().intersection(frame).union_all()
        for q in _polys(merged.simplify(PARCEL_SIMPLIFY_M)):
            if q.area >= 1.0:
                items.append((f"jm_{b}", q))
    return _fc(items, lines, "landuse")


def build_daeji(frame) -> dict:
    """대지(지목 `대`)를 **한 덩어리로 합친** 면 — 마당 · 주차장 · 공터(빈 공간 45.0% 의 29.3%p). 필지 경계가 사라진다.

    ★ 따로 낸다 — 합친 면의 약 3분의 2 라 `landuse.geojson` 에 같이 두면 상한을 못 맞춘다. 가장 낮은 바탕이라 **겹치는 자리에서는 `landuse` 가 위**다.
    """
    p = _read(PARCEL_STEM)
    p = p[p.intersects(frame)].copy()
    sel = p[[isinstance(x, str) and x[-1:] == "대" for x in p["A5"].astype(str)]]
    merged = sel.geometry.make_valid().intersection(frame).union_all()
    items = [("daeji", q) for q in _polys(merged.simplify(DAEJI_SIMPLIFY_M)) if q.area >= 1.0]
    return _fc(items, [], "daeji")


def main() -> None:
    frame = _frame()
    total = 0
    for name in SOURCES:
        fc = build(name, frame)
        txt = json.dumps(fc, ensure_ascii=False, separators=(",", ":"))
        total += len(txt.encode())
        (W / f"{name}.geojson").write_text(txt, encoding="utf-8")
        print(f"  {name}.geojson  면 {len(fc['features'])} · {len(txt.encode()) / 1024:.0f}KB")
    if total > SIZE_MAX:
        raise SystemExit(f"★ 바탕 면이 {total / 1e6:.1f}MB — 상한 {SIZE_MAX / 1e6:.1f}MB 를 넘었다")
    lu = build_landuse(frame)
    txt = json.dumps(lu, ensure_ascii=False, separators=(",", ":"))
    if len(txt.encode()) > LANDUSE_SIZE_MAX:
        raise SystemExit(f"★ 토지이용 면이 {len(txt.encode()) / 1024:.0f}KB — 상한 {LANDUSE_SIZE_MAX / 1024:.0f}KB 를 넘었다")
    (W / "landuse.geojson").write_text(txt, encoding="utf-8")
    print(f"  landuse.geojson  면 {len(lu['features'])} · {len(txt.encode()) / 1024:.0f}KB")
    dj = build_daeji(frame)
    txt = json.dumps(dj, ensure_ascii=False, separators=(",", ":"))
    if len(txt.encode()) > DAEJI_SIZE_MAX:
        raise SystemExit(f"★ 대지 면이 {len(txt.encode()) / 1024:.0f}KB — 상한 {DAEJI_SIZE_MAX / 1024:.0f}KB 를 넘었다")
    (W / "daeji.geojson").write_text(txt, encoding="utf-8")
    print(f"  daeji.geojson  면 {len(dj['features'])} · {len(txt.encode()) / 1024:.0f}KB")


if __name__ == "__main__":
    no_args(__doc__)          # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    main()
