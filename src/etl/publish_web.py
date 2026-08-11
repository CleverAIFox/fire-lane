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
P, W = ROOT/"data"/"processed", ROOT/"web"/"data"
EMD_CD = "12210108"
CCTV_RADIUS    = 25    # CCTV 유효 커버리지 반경(m). 보수적 추정
STATION_RADIUS = 300   # 안전센터 주변 반경(m). 출발점 일대 도로 맥락 확보
PREC = dict(driver="GeoJSON", COORDINATE_PRECISION=6)

def main():
    W.mkdir(parents=True, exist_ok=True)
    gpd.read_file(P/"segments.geojson")[
        ["seg_id","width_min_m","width_max_m","verdict","width_verified",
         "midpoint_fallback","inherited","route_usage","length_m",
         "run_length_m","nfa_designated","cctv_dist_m","cv_feasible",
         "unknown_reason","geometry"]
    ].to_file(W/"segments.geojson", **PREC)

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
    minx, miny, maxx, maxy = gpd.GeoSeries([scope4], crs=4326).total_bounds
    m = 0.002
    (W/"view.json").write_text(json.dumps({
        "center": [round((minx+maxx)/2, 6), round((miny+maxy)/2, 6)],
        "bounds": [[round(minx, 4), round(miny, 4)], [round(maxx, 4), round(maxy, 4)]],
        "maxBounds": [[round(minx-m, 4), round(miny-m, 4)], [round(maxx+m, 4), round(maxy+m, 4)]],
        "minZoom": 13.6, "maxZoom": 20,
        "emdBounds": [[round(*emd.to_crs(4326).total_bounds[:1], 4), round(emd.to_crs(4326).total_bounds[1], 4)],
                      [round(emd.to_crs(4326).total_bounds[2], 4), round(emd.to_crs(4326).total_bounds[3], 4)]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 건물은 스코프 전체를 덮는다. 동명동만 자르면 안전센터 주변이
    # 길만 남아 3D 가 안 선다. (2,518동 → 5,713동)
    b = gpd.read_file(P/"building_5186.gpkg")
    b = b[b.intersects(scope)].copy()
    b["flo"] = b.GRO_FLO_CO.fillna(1).astype(float).clip(lower=1)   # 0층 291동 → 1층
    b["h"] = (b.flo*3.3).round(1)
    b[["BUL_MAN_NO","BULD_NM","flo","h","geometry"]].to_crs(4326).to_file(W/"buildings.geojson", **PREC)

    # ── 마커 3종 ────────────────────────────────────────────────
    # 전부 스코프로 자른다. 자르지 않으면 마스크가 덮은 어두운 영역 위에
    # 점이 떠서 "저게 뭐냐"는 오해를 부른다. (소화전 18개 중 스코프 밖이 7개였다)

    # 소화전. 관할 588개 중 공개 31개(5%), 그중 동명동 1개.
    # 이 희소성 자체가 발표 논거다.
    hyd = gpd.read_file(P/"hydrant_point.geojson")
    hyd = hyd[hyd.within(scope4)][["시설번호", "소재지도로명주소", "상세위치",
                                   "설치연도", "보호틀유무", "관할기관명", "geometry"]]
    hyd.to_file(W/"hydrants.geojson", **PREC)

    # 소방서 / 119안전센터.
    # 출동은 안전센터에서 나간다. 동부소방서는 대인안전센터와 주소가 같아(제봉로 210)
    # 좌표가 겹치므로 유형을 나눠 따로 그린다.
    sta = gpd.read_file(P/"fire_station.geojson")
    sta = sta[sta.within(scope4)].copy()
    sta["kind"] = sta["유형"].astype(str).map(
        lambda v: "center" if "안전센터" in v else "station")
    sta[["소방서 및 안전센터명", "주소", "전화번호", "kind", "geometry"]].to_file(
        W/"stations.geojson", **PREC)

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
        최초설치=("설치연도", "min"),
        최근설치=("설치연도", "max"),
        설치회차=("설치연도", "size"),
        geometry=("geometry", "first"),
    ).reset_index(drop=True)
    cg = gpd.GeoDataFrame(agg, crs=4326)
    cg.to_file(W/"cctv.geojson", **PREC)


    import shutil; shutil.copy(P/"segments.schema.json", W/"segments.schema.json")
    for f in sorted(W.iterdir()):
        print(f"  {f.name:26} {f.stat().st_size/1024:7.0f} KB")

if __name__ == "__main__":
    main()
