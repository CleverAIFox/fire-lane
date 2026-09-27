"""
shapefile.py — SHP 를 읽는 갈래.  (PLAN §1 #132 · DECISIONS §274)

IN    zip 안 SHP 한 장 · 도엽 여러 zip · NGI/SHP 혼재 묶음
OUT   GeoDataFrame (`shp_zip` · `shp_zip_multi`) 또는 완성된 계보 조각 (`ngii1k`)
밖   **어느 갈래인지는 안 고른다** — `read.reader()` 가 고른다. 여기 함수는
      불린 뒤에만 돈다. 그리고 **저장도 안 한다** — `ngii1k` 만 예외로
      `c.save` 를 받아 도엽별로 쓴다(레이어가 여럿이라 한 장으로 안 떨어진다).
"""
from __future__ import annotations

import zipfile

import geopandas as gpd
import pandas as pd
from shapely import make_valid

from firelane.hashing import sha256
from firelane.read._io import bbox_in, load_shp_in_zip
from firelane.read.ctx import Ctx


def read_shp_zip(c: Ctx):
    """kind "shp_zip" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    e = c.e
    src = c.src
    crs = c.crs
    tmp = c.tmp
    g = load_shp_in_zip(src, e["layer"], crs, e.get("encoding", "cp949"), tmp)
    return g


def read_shp_zip_multi(c: Ctx):
    """kind "shp_zip_multi" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    key = c.key
    e = c.e
    hits = c.hits
    crs = c.crs
    tmp = c.tmp
    rec = c.rec
    # ★ 2026-08-30. 종전에는 zip 하나당 shp 하나를 가정하고
    #   `tmp/z.stem/e["layer"]` 한 장만 읽었다. `jijeok` 은 zip 하나
    #   안에 shp 7장이 들어 있고 — 대장이 `parts` 로 그것을 이미
    #   적고 있었다 — 첫 장만 읽혔다. 그 장이 BBOX 밖이라 0건이
    #   나왔고 status 는 OK 였다. **970MB 를 읽고 초록불이 났다.**
    #
    #   선언이 있는데 읽는 곳이 없으면 그 선언은 주석이다.
    #   여기서는 **실물을 세고 대장과 대조한다** — 이름 규칙을
    #   코드에 박으면(`f"{stem}({n}).shp"`) 원본 명명이 바뀔 때
    #   또 조용히 0건이 된다. 실물이 근거이고 대장이 기대치다.
    # ★ 2026-09-16. **읽는 시점에** bbox 를 건다(DECISIONS §168).
    #   종전에는 조각 7장 × 100만 필지를 전부 메모리에 올린 뒤 아래
    #   `.cx` 로 24,183건을 잘랐다 — `jijeok` OOM 의 진짜 자리가 여기다.
    #   `tools/jijeok_probe.py --extract` 가 같은 zip 을 bbox 로 읽어
    #   이미 살아 있었다. `shp_zip`(load_shp_in_zip)도 처음부터 이렇게 읽는다.
    #   bbox 필터는 GDAL 빌드에 따라 외곽 사각형 기준이라(GEOS 없으면)
    #   결과가 넓거나 같다. 정확한 교차는 아래 `.cx` 가 그대로 자른다 —
    #   산출 행 집합은 같다. `.cx` 를 지우면 테스트 카나리아가 운다.
    _want = e["layer"]
    _base = _want.rsplit(".", 1)[0]
    _bb = bbox_in(crs)
    parts, _read = [], []
    for z in hits:
        with zipfile.ZipFile(z) as zf:
            zf.extractall(tmp / z.stem)
        found = sorted(x for x in (tmp / z.stem).rglob("*")
                       if x.suffix.lower() == ".shp"
                       and x.name.rsplit(".", 1)[0].startswith(_base))
        if not found:
            raise FileNotFoundError(
                f"{z.name} 안에 {_want} 계열 shp 가 없다")
        for p in found:
            parts.append(gpd.read_file(
                p, bbox=_bb, encoding=e.get("encoding", "utf-8")))
            _read.append(p.name)
    # ★ 2026-08-31. 종전에는 **zip 하나마다** `len(found) != len(parts)`
    #   를 봤다. `parts` 가 두 뜻으로 쓰이는 것을 못 본 것이다 —
    #
    #     jijeok      ['', '2'..'7']       zip 1개 **안의** shp 7장
    #     ngii_road   ['gj9708','gj9712']  zip 2개의 **도엽 토큰**
    #     ortho/dem   ['gj037'...]         같은 파일명 토큰(naming.part)
    #
    #   파일명 토큰이 다수이고 `naming.py` 가 `part` 를 그렇게 정의한다.
    #   zip 단위로 대조하면 도엽이 여럿인 소스는 **구조적으로 항상**
    #   실패한다(zip 2개 × 각 1장 → 1 != 2). 실제로 ngii_road ·
    #   ngii_road_center 가 그렇게 죽었고 소비자가 11곳이다.
    #
    #   대조는 유지하되 **합계로** 본다. 조용히 덜 읽는 것을 막는다는
    #   목적은 그대로고, 세는 단위만 zip → 전체로 옮긴다.
    _decl = e.get("parts")
    if _decl is not None and len(_read) != len(_decl):
        raise ValueError(
            f"{key}: 실물 shp 합계 {len(_read)}장 · 대장 parts "
            f"{len(_decl)}개. 어느 쪽이 맞는지 사람이 정해야 한다 — "
            f"수가 다르면 조용히 덜 읽는다 (zip {len(hits)}개: "
            f"{', '.join(z.name for z in hits)})")
    rec["parts_read"] = _read
    print(f"  · {key}: zip {len(hits)} · shp {len(_read)}장 "
          f"{sum(len(x) for x in parts):,}행")
    g = pd.concat(parts).pipe(gpd.GeoDataFrame, crs=parts[0].crs)
    g = g.set_crs(crs, allow_override=True)
    g = g.cx[_bb[0]:_bb[2], _bb[1]:_bb[3]].copy()
    # ★ buffer(0) 은 폴리곤 자기교차 정리용이다. LineString 에 걸면
    #   빈 폴리곤이 되어 전멸한다. ngii_road_center(선)가 0건이던 원인이다.
    g["geometry"] = g.geometry.apply(make_valid)
    if g.geom_type.isin(("Polygon", "MultiPolygon")).any():
        g["geometry"] = g.geometry.buffer(0)
    rec["source_sha256"] = ",".join(sha256(z)[:16] for z in hits)
    return g


def read_ngii1k(c: Ctx):
    """kind ("ngii1k", "ngii_1k", "shp_dir") 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    key = c.key
    src = c.src
    hits = c.hits
    rec = c.rec
    save = c.save
    # NGI(텍스트) / SHP 혼재라 GDAL 로 못 읽는다. ngii1k.py 가 파싱한다.
    # 여기서 호출하는 이유: 손으로 따로 돌리면 파이프라인이 재현되지 않는다.
    # ★ 2026-08-17. 여기가 두 가지로 깨져 있었다.
    #   1) read_sheet 는 (geom, attrs) 튜플을 내는데 geom 으로 받아
    #      'tuple' object has no attribute 'geom_type' 로 매 실행 FAIL 했다.
    #      _manifest.json 에 FAIL 이 적힌 채 파이프라인은 OK 를 찍었다.
    #   2) 설령 통과해도 src 컬럼만 만들어 도로폭·일방통행을 통째로 버렸다.
    #      그래서 사람이 ngii1k.py 를 손으로 돌려야 했고, 폭 주 소스가
    #      파이프라인 밖에서 만들어지고 있었다("파이프라인은 한 명령이다"가
    #      폭에 대해서는 거짓이었다).
    #   프레임 조립을 ngii1k.build 하나로 합쳐 두 곳에서 만들지 않는다.
    from firelane.ngii1k import LAYERS, build, collect, read_sheet
    want = list(LAYERS)
    # ★ 2026-08-18. src = hits[0] 라 글롭이 여러 zip 을 찾아도 첫 개만 썼다.
    #   SHP 판(74도엽)만 들어가고 NGI 보완분(북부 12도엽)이 통째로 무시됐다.
    #   대장이 글롭이면 글롭 전체가 소스다.
    sheets = collect(hits if len(hits) > 1 else src)
    if not sheets:
        raise FileNotFoundError(f"도엽 없음: {src}")
    acc = {k: [] for k in want}
    per_sheet = {}
    for sh, (year, sk, path) in sorted(sheets.items()):
        got = read_sheet(sk, path, want)
        for k, v in got.items():
            acc[k] += v
        per_sheet[sh] = {"year": year, "kind": sk,
                         **{k: len(got[k]) for k in want}}
    # ★ 도엽별 0건은 오류가 아니다(2026-08-17 정정). ngii1k.main() 주석 참조.
    #   V-WORLD 74도엽은 동구 전역이라 빈 도엽이 정상적으로 섞인다.
    #   합계 0 만 오류로 본다. 도엽 목록은 대장에 남긴다.
    empty = [sh for sh, v in per_sheet.items() if v["A0010000"] == 0]
    rec["empty_sheets"] = empty
    if not acc["A0010000"]:
        raise ValueError("도로경계 총 0건 — 레이어 코드/압축 구조 확인")
    rec["sheets"] = per_sheet
    outs = []
    made = []
    for lay in want:
        gg = build(lay, acc[lay])       # 타입 필터로 전멸하면 여기서 세운다
        if gg is None:
            continue
        k2 = LAYERS[lay][0]
        info = save(gg, k2)
        outs += [f"{k2}.geojson", f"{k2}_5186.gpkg"]
        made.append(k2)
        if k2 == key:
            rec |= info
    # 폭 주 소스와 속성 소스는 반드시 나와야 한다.
    for must in ("ngii1k", "ngii1k_center"):
        if must not in made:
            raise ValueError(f"{must} 산출 0건 — GEOM_OF / 레이어 코드 확인")
    rec |= {"status": "OK", "outputs": outs, "layers": made}
    return rec
