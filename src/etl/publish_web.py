#!/usr/bin/env python3
"""publish_web.py — data/processed 산출물을 web/data 경량 사본으로 내보낸다.

좌표를 6자리(약 11cm)로 반올림하고 표출에 안 쓰는 컬럼을 버린다.
web/data 는 생성물이다. 직접 수정하지 말 것.
"""
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW, PROCESSED, WEB  # noqa: E402
OUT = PROCESSED
P, W = ROOT/"data"/"processed", ROOT/"web"/"data"
EMD_CD = "12210108"
CCTV_RADIUS    = 25    # CCTV 유효 커버리지 반경(m). 보수적 추정
STATION_RADIUS = 300   # 안전센터 주변 반경(m). 출발점 일대 도로 맥락 확보
PREC = dict(driver="GeoJSON", COORDINATE_PRECISION=6)

def main():
    W.mkdir(parents=True, exist_ok=True)
    # z 는 terrain.py 산출물이다. DEM 이 없으면 안 생기므로 선택 컬럼으로 둔다.
    _seg = gpd.read_file(P/"segments.geojson")
    _cols = ["seg_id","width_min_m","width_max_m","verdict","width_verified",
             "midpoint_fallback","inherited","route_usage","length_m",
             "run_length_m","nfa_designated","cctv_dist_m","cv_feasible",
             "unknown_reason"]
    _cols += [c for c in ("z",) if c in _seg.columns]
    _seg[_cols + ["geometry"]].to_file(W/"segments.geojson", **PREC)

    emd = gpd.read_file(P/"boundary_emd.geojson")
    emd = emd[emd.EMD_CD == EMD_CD]
    emd.to_file(W/"boundary.geojson", **PREC)
    poly = emd.to_crs(5186).geometry.iloc[0]

    # ── 접근 회랑 ──────────────────────────────────────────────
    # 119안전센터는 동명동 밖이다(대인 서 1.0km / 지산 동 1.2km).
    # 출동 경로가 화면에 나와야 하므로 동 경계만 잠그면 안 된다.
    # 회랑 = 최단경로 중 동 밖 구간의 union. 전 광주가 아니라 얇은 리본이다.
    #   진입점 60개 중 실사용 23개, 그중 5개가 통행량의 80%를 담당한다.
    corr = None
    cp = P/"corridor_5186.gpkg"
    if cp.exists():
        corr = gpd.read_file(cp).to_crs(5186).union_all().buffer(70)

    # 안전센터 주변도 스코프에 넣는다. 회랑만으로는 리본이 너무 얇아
    # 출발점 일대의 도로 맥락이 안 보인다.
    sta_src = gpd.read_file(P/"fire_station.geojson").to_crs(5186)
    sta_buf = sta_src.geometry.union_all().buffer(STATION_RADIUS)

    scope = poly.buffer(60)
    if corr is not None:
        scope = scope.union(corr)
    scope = scope.union(sta_buf)
    gpd.GeoDataFrame(geometry=[scope], crs=5186).to_crs(4326).to_file(W/"scope.geojson", **PREC)

    # 3단 마스크
    #   tier1 동명동      = 원본 밝기
    #   tier2 접근 회랑   = 살짝 어둡게 (경로는 보이되 주역이 아니다)
    #   tier3 그 밖       = 덮는다
    from shapely.geometry import box
    world = box(-180, -85, 180, 85)
    emd4 = emd.to_crs(4326).geometry.iloc[0]
    scope4 = gpd.GeoSeries([scope], crs=5186).to_crs(4326).iloc[0]
    gpd.GeoDataFrame(geometry=[world.difference(scope4)], crs=4326).to_file(W/"mask.geojson", **PREC)
    gpd.GeoDataFrame(geometry=[scope4.difference(emd4)], crs=4326).to_file(W/"mask_soft.geojson", **PREC)

    # 뷰 설정: bbox 를 코드에 하드코딩하지 않고 데이터에서 뽑아 내보낸다.
    # terrain/ortho 가 기록한 타일 범위는 보존한다.
    _vj = W/"view.json"
    _prev = json.loads(_vj.read_text(encoding="utf-8")) if _vj.exists() else {}
    minx, miny, maxx, maxy = gpd.GeoSeries([scope4], crs=4326).total_bounds
    m = 0.002
    (W/"view.json").write_text(json.dumps({
        "center": [round((minx+maxx)/2, 6), round((miny+maxy)/2, 6)],
        "bounds": [[round(minx, 4), round(miny, 4)], [round(maxx, 4), round(maxy, 4)]],
        "maxBounds": [[round(minx-m, 4), round(miny-m, 4)], [round(maxx+m, 4), round(maxy+m, 4)]],
        "minZoom": 13.6, "maxZoom": 20,
        # terrain / ortho 타일의 실제 범위. 지도 소스의 bounds 로 쓴다.
        # 없으면 브라우저가 범위 밖 타일을 요청해 404 가 뜬다.
        # terrain.py / ortho.py 가 채운다. 여기서 새로 쓰면서 지우면 안 된다.
        "terrainBounds": _prev.get("terrainBounds"),
        "orthoBounds":   _prev.get("orthoBounds"),
        "emdBounds": [[round(*emd.to_crs(4326).total_bounds[:1], 4), round(emd.to_crs(4326).total_bounds[1], 4)],
                      [round(emd.to_crs(4326).total_bounds[2], 4), round(emd.to_crs(4326).total_bounds[3], 4)]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 건물은 스코프 전체를 덮는다. 동명동만 자르면 안전센터 주변이
    # 길만 남아 3D 가 안 선다. (2,518동 → 5,713동)
    b = gpd.read_file(P/"building_5186.gpkg")
    b = b[b.intersects(scope)].copy()
    b["flo"] = b.GRO_FLO_CO.fillna(1).astype(float).clip(lower=1)   # 0층 291동 → 1층
    b["h"] = (b.flo*3.3).round(1)
    cols = ["BUL_MAN_NO","BULD_NM","flo","h"] + (["z"] if "z" in b.columns else [])
    b[cols+["geometry"]].to_crs(4326).to_file(W/"buildings.geojson", **PREC)

    # ── 마커 3종 ────────────────────────────────────────────────
    # 전부 스코프로 자른다. 자르지 않으면 마스크가 덮은 어두운 영역 위에
    # 점이 떠서 "저게 뭐냐"는 오해를 부른다. (소화전 18개 중 스코프 밖이 7개였다)

    # 소화전. 관할 588개 중 공개 31개(5%), 그중 동명동 1개.
    # 이 희소성 자체가 발표 논거다.
    hyd = gpd.read_file(P/"hydrant_point.geojson")
    hcols = ["시설번호", "소재지도로명주소", "상세위치", "설치연도",
             "보호틀유무", "관할기관명"] + (["z"] if "z" in hyd.columns else [])
    hyd = hyd[hyd.within(scope4)][hcols + ["geometry"]]
    hyd.to_file(W/"hydrants.geojson", **PREC)

    # 소방서 / 119안전센터.
    # 출동은 안전센터에서 나간다. 동부소방서는 대인안전센터와 주소가 같아(제봉로 210)
    # 좌표가 겹치므로 유형을 나눠 따로 그린다.
    sta = gpd.read_file(P/"fire_station.geojson")
    sta = sta[sta.within(scope4)].copy()
    sta["kind"] = sta["유형"].astype(str).map(
        lambda v: "center" if "안전센터" in v else "station")
    scols = ["소방서 및 안전센터명", "주소", "전화번호", "kind"] + (["z"] if "z" in sta.columns else [])
    sta[scols + ["geometry"]].to_file(W/"stations.geojson", **PREC)

    # CCTV. 촬영방면·카메라대수·설치연도 보유.
    # 야간 답사 대체 근거이자 D-21 시간대 분석의 유일한 출구다.
    cctv = gpd.read_file(P/"cctv.geojson")
    cctv = cctv[cctv.within(scope4)].copy()
    for c, d in (("카메라대수", 1), ("설치연도", 0)):
        cctv[c] = pd.to_numeric(cctv[c], errors="coerce").fillna(d).astype(int)

    # 원본은 설치연도별로 행이 쪼개져 있다. 같은 지점이 여러 줄로 나온다.
    # (동명동 53행 → 고유 좌표 29지점, 카메라 90대)
    # 좌표로 묶어 지점 단위로 만든다. 대수는 합산, 연도는 최초/최신을 둘 다 남긴다.
    cctv["_k"] = list(zip(cctv.geometry.x.round(6), cctv.geometry.y.round(6)))
    agg = cctv.groupby("_k").agg(
        관리기관명=("관리기관명", "first"),
        소재지도로명주소=("소재지도로명주소", "first"),
        카메라대수=("카메라대수", "sum"),
        카메라화소=("카메라화소", "first"),
        촬영방면=("촬영방면", "first"),
        z=("z", "first") if "z" in cctv.columns else ("카메라대수", "size"),
        최초설치=("설치연도", "min"),
        최근설치=("설치연도", "max"),
        설치회차=("설치연도", "size"),
        geometry=("geometry", "first"),
    ).reset_index(drop=True)
    cg = gpd.GeoDataFrame(agg, crs=4326)
    cg.to_file(W/"cctv.geojson", **PREC)


    # ── 상가 POI ────────────────────────────────────────────
    # 소상공인시장진흥공단 상가(상권)정보. 이미 파이프라인에 있는데 지도에 안 올렸었다.
    # 네이버 지도처럼 상호가 보이면 어느 골목인지 즉시 감이 온다.
    # 업종 대분류로 묶어 색을 나눈다. 층정보가 있으면 1층만 남긴다(간판이 보이는 것).
    poi = gpd.read_file(P/"poi_store.geojson")
    poi = poi[poi.within(scope4)].copy()
    poi["cat"] = poi["상권업종대분류명"].fillna("기타")
    poi["층"] = pd.to_numeric(poi["층정보"], errors="coerce")
    poi = poi[(poi["층"].isna()) | (poi["층"] <= 1)]          # 지상 1층 = 골목에서 보이는 것
    poi[["상호명", "cat", "상권업종중분류명", "도로명주소", "geometry"]].rename(
        columns={"상호명": "name", "상권업종중분류명": "sub", "도로명주소": "addr"}
    ).to_file(W/"poi.geojson", **PREC)
    print(f"  상가 POI {len(poi)}개 (지상 1층 · {poi.cat.nunique()}개 업종)")

    # ── 시설 마커를 건물과 같은 방식으로 ──────────────────────
    # deck.gl 레이어는 map.setTerrain() 을 켜면 지형 아래로 묻힌다.
    # 건물처럼 fill-extrusion 으로 그리면 지형을 따라간다.
    # 그래서 포인트를 실제 시설 형상의 폴리곤으로 만들어 둔다.
    #
    # 비율은 실물을 따르되 크기는 과장한다. 소화전 실물 지름 0.2m 로는
    # 1km 시야에서 보이지 않는다.
    #   part: 아래에서 위로 쌓는 조각. base(바닥높이) / h(높이) / r(반지름)
    import math

    def solid(pt, parts, props):
        """포인트를 원기둥 조각들의 폴리곤으로 만든다."""
        out = []
        for i, (r, base, h, color) in enumerate(parts):
            # 반지름이 작을수록 각을 촘촘히. 소화전이 사각기둥으로 보이지 않게.
            seg_n = 24 if r < 1 else 16
            ring = [(pt.x + r*math.cos(t), pt.y + r*math.sin(t))
                    for t in [k*2*math.pi/seg_n for k in range(seg_n + 1)]]
            out.append({**props, "part": i, "base": base, "top": base + h,
                        "mcolor": color, "geometry": Polygon(ring)})
        return out

    from shapely.geometry import Polygon

    def slab(pt, parts, props):
        """포인트를 직사각형 박스 조각들로 만든다 (소방서 119 간판)."""
        out = []
        for i, (hw, hl, base, h, color) in enumerate(parts):
            ring = [(pt.x-hw, pt.y-hl), (pt.x+hw, pt.y-hl),
                    (pt.x+hw, pt.y+hl), (pt.x-hw, pt.y+hl), (pt.x-hw, pt.y-hl)]
            out.append({**props, "part": i, "base": base, "top": base + h,
                        "mcolor": color, "geometry": Polygon(ring)})
        return out

    # 소방서 = 붉은 직사각형 119 간판(기둥 + 넓은 판 + 흰 테). (half_w, half_l, base, h, color)
    STATION_BOX = [
        (1.6, 1.6, 0,    13,  "#b8241a"),   # 지지 기둥
        (7.0, 1.3, 13,   10,  "#e42a1e"),   # 붉은 119 간판(넓고 얇게)
        (7.4, 1.7, 12.2, 1.4, "#f2f2f2"),   # 간판 아래 흰 테
        (7.4, 1.7, 23,   1.4, "#f2f2f2"),   # 간판 위 흰 테
    ]
    # (반지름m, 바닥높이m, 높이m, 색)
    #
    # ★ 실물 치수를 따르되 최소한만 키운다.
    #   실물   소화전 지름 0.2m·높이 0.9m / CCTV 지주 4.5m / 건물 3~5층
    #   과장   소화전 x2 (지름 0.4m·높이 1.8m) — 골목 폭 3m 대비 자연스럽다
    #          CCTV 지주는 실물 그대로. 대수만큼만 높인다
    #          안전센터·소방서는 실제 건물 규모(4~6층)를 따른다
    #   이전에 소화전을 6m 로 세웠더니 2층 건물만 했다. 현실 반영이 우선이다.
    MARKER_PARTS = {
        "center":  [(6, 0, 15, "#ff4d3d"), (7, 15, 2, "#ff4d3d"), (1.2, 17, 6, "#ff968c")],
        "station": [(7, 0, 18, "#ffb020"), (8, 18, 2, "#ffb020"), (0.8, 20, 7, "#ffd68c")],
        "hydrant": [(1.4, 0,    0.8, "#286e96"),    # 받침(크게)
                    (0.9, 0.8,  5.2, "#4fc3f7"),    # 몸통(굵고 높게)
                    (1.5, 6.0,  0.7, "#286e96"),    # 플랜지
                    (0.7, 6.7,  1.8, "#8cdcff"),    # 상단 캡
                    (0.4, 8.5, 28,   "#78d4ff")],   # 위로 솟는 빛기둥(건물 위로)
        "cctv":    [(0.09, 0,   4.5, "#78788a"),    # 지주 4.5m (실물)
                    (0.28, 4.5, .45, "#b98cff"),    # 하우징
                    (0.13, 4.8, .30, "#e1cdff")],   # 렌즈
    }

    feats = []
    for _, r in sta.to_crs(5186).iterrows():
        base_props = {"name": r["소방서 및 안전센터명"],
                      "addr": r.get("주소", ""), "z": r.get("z", 0)}
        if r["kind"] == "center":
            feats += solid(r.geometry, MARKER_PARTS["center"],
                           {**base_props, "kind": "center", "sub": "출동 시작점"})
        else:  # 소방서 = 붉은 직사각형 119 간판
            feats += slab(r.geometry, STATION_BOX,
                          {**base_props, "kind": "station", "sub": "관할 본서"})
    for _, r in hyd.to_crs(5186).iterrows():
        feats += solid(r.geometry, MARKER_PARTS["hydrant"],
                       {"kind": "hydrant", "name": f"소화전 {r.get('시설번호','')}",
                        "sub": str(r.get("상세위치", "")), "addr": r.get("소재지도로명주소", ""),
                        "z": r.get("z", 0)})
    for _, r in cg.to_crs(5186).iterrows():
        n = int(r["카메라대수"])
        # 대수만큼 지주를 높인다. 실물 4.5m 에서 대당 0.5m.
        h = 4.5 + min(n, 8) * 0.5
        pts = [(0.09, 0, h, "#78788a"), (0.28, h, .45, "#b98cff"), (0.13, h + .3, .30, "#e1cdff")]
        feats += solid(r.geometry, pts,
                       {"kind": "cctv", "name": f"CCTV {n}대",
                        "sub": f"{r.get('카메라화소','')} · 설치 {r.get('최초설치','')}",
                        "addr": r.get("소재지도로명주소", ""), "z": r.get("z", 0)})

    gpd.GeoDataFrame(feats, crs=5186).to_crs(4326).to_file(W/"markers.geojson", **PREC)
    print(f"  시설 마커 {len(feats)}조각 "
          f"(안전센터·소방서 {len(sta)} · 소화전 {len(hyd)} · CCTV {len(cg)})")

    import shutil; shutil.copy(P/"segments.schema.json", W/"segments.schema.json")
    for f in sorted(W.iterdir()):
        print(f"  {f.name:26} {f.stat().st_size/1024:7.0f} KB")

if __name__ == "__main__":
    main()
