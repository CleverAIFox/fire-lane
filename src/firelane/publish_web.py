#!/usr/bin/env python3
"""
publish_web.py — data/processed 산출물을 web/data 경량 사본으로 내보낸다.


IN    processed/*.geojson · processed/segments.schema.json ·
      processed/route_vehicle.csv · processed/corridor_5186.gpkg ·
      processed/building_5186.gpkg ·
      processed/navi_build.csv · processed/navi_jibun.csv · processed/civil_office.geojson ·
      processed/ngii1k_5186.gpkg · processed/road_rw_5186.gpkg · processed/ngii1k_walk_5186.gpkg
      processed/speedbump.csv · speed_cam.csv · child_zone_std_5186.gpkg · senior_zone_std_5186.gpkg ·
      processed/nfa_dispatch_119.csv · nfa_rescue.csv · nfa_fire_incident.csv · parking_enforce.csv
OUT   web/data/  — 아래 열일곱. ★ 중괄호 축약을 쓰지 않는다. 선언은
      기계가 대조하는 것이고(tests/test_declaration_reality.py) 축약하면
      그 대조가 이름을 못 찾는다.
        segments.geojson      buildings.geojson
        hydrants.geojson      stations.geojson     cctv.geojson
        poi.geojson
        dest.geojson
        segments.schema.json  vehicle_spec.json    route_vehicle.json
        navi_graph.json       _manifest.json       fleet.json
        road_area.geojson     sidewalk.geojson
        context.geojson       history.geojson
      ★ navi_graph.json 은 publish_navi.main() 을 여기서 불러 낸다(2026-09-16 · DECISIONS §170-5)
      ★ fleet.json 은 publish_fleet.main() 이(§212-3), road_area · sidewalk 는
        publish_basemap.main() 이 낸다(§213-4). context · history 는 publish_context.main() 이(§216-3)
      ★ web/data/view.json 은 terrain·ortho 가 넣어둔 타일 범위를 읽어
        보존하고 다시 쓴다 — writes 가 아니라 **mutates** 다
      ★ markers.geojson 은 **내지 않는다.** 286줄이 남은 것을 지운다 —
        종전에 이 줄이 산출물로 적혀 있었다(2026-09-03 정정)
PARAM 좌표 정밀도(PREC) · web/data 40MB 상한(CI · commit_policy · pipeline)

좌표를 6자리(약 11cm)로 반올림하고 표출에 안 쓰는 컬럼을 버린다.
web/data 는 생성물이다. 직접 수정하지 말 것.
"""
import hashlib
import json

import geopandas as gpd
import pandas as pd

from firelane import webmanifest
from firelane.paths import PROCESSED, ROOT

OUT = PROCESSED
P, W = ROOT/"data"/"processed", ROOT/"web"/"data"
EMD_CD = "12210108"
# ★ CCTV_RADIUS 는 삭제했다(2026-08-23). 여기서 0회 참조였고, 커버리지
#   원의 반경 정본은 web/config.js 의 markers[].cover.radius 다.
#   판정 임계(CCTV_RANGE 25.0)의 정본은 seg/params.py 다. 같은 숫자를
#   세 곳에 두면 반드시 한 곳만 고치고 잊는다.
PREC = dict(driver="GeoJSON", COORDINATE_PRECISION=6)
# ★ 건물 발행 예산(§181-2). 스코프 판 2.18MB · web/data 32MB / 상한 40MB 에서 잡았다.
# ★ 2026-09-22 (§218-3) — 6.0 **MiB** 였는데 커밋 정책(`tools/commit_policy.py` MAX_FILE_MB)은 5.0 **MB**
#   (10진)라 둘 사이(5.0MB~6.0MiB)에 떨어진 발행물이 파이프라인은 통과하고 커밋에서 막혔다.
#   단위를 정책에 맞추고 여유 0.1 을 둔다.
BLDG_MB = 4.9
BLDG_TOL = (0.3, 0.6, 1.0)          # m · EPSG:5186

def main():
    W.mkdir(parents=True, exist_ok=True)
    # z 는 terrain.py 산출물이다. DEM 이 없으면 안 생기므로 선택 컬럼으로 둔다.
    _seg = gpd.read_file(P/"segments.geojson")
    # seg_no — 도로명 안에서의 구간 순번. 화면 표기 전용이다.
    # seg_uid 는 사람이 읽을 정보가 없고(DM-193399-284228-9UPP), seg_id 는
    # 실행 간 유지되지 않아 외부 참조 금지다(MASTER §11). 팝업 머리글에
    # seg_id 를 쓰고 있었던 것은 그 금지를 화면이 어긴 것이다.
    # ★ 순번은 노딩 규칙이 바뀌면 밀린다. 표기용이지 키가 아니다.
    _rep = _seg.geometry.representative_point()
    _seg = _seg.assign(_ox=_rep.x, _oy=_rep.y)
    _seg["seg_no"] = (_seg.sort_values(["road_name", "_oy", "_ox"])
                          .groupby("road_name").cumcount() + 1)

    _cols = ["seg_uid","seg_id","seg_no","width_min_m","width_max_m","verdict","width_verified",
             "midpoint_fallback","inherited","route_usage","length_m",
             "run_length_m","nfa_designated","cctv_dist_m","cv_feasible","width_src","width_disagree_m","width_cov","n_sample","n_try","road_name","seg_label","road_side","road_bt_m","in_emd","light_count",
             "unknown_reason"]
    _cols += [c for c in ("z",) if c in _seg.columns]
    _seg[_cols + ["geometry"]].to_file(W/"segments.geojson", **PREC)

    emd = gpd.read_file(P/"boundary_emd.geojson")
    emd = emd[emd.EMD_CD == EMD_CD]
    # ★ 2026-09-22 (DECISIONS §218-1) — boundary · mask · mask_soft · streetlights · lightpoles 를
    #   **더 내지 않는다.** 읽던 것은 옛 지도(web/js)뿐이었고 그 지도를 걷어냈다. 관제는 동 경계 ·
    #   덮개를 안 그리고, 가로등은 판정(`light_count`)에만 쓴다. 남은 파일은 지운다 — 안 지우면
    #   아무도 안 읽는 276KB 가 계속 배포된다(`test_web_data_has_no_unintended_orphan` 이 본다).
    for _gone in ("boundary.geojson", "mask.geojson", "mask_soft.geojson",
                  "streetlights.geojson", "lightpoles.geojson"):
        (W / _gone).unlink(missing_ok=True)

    # ★ 2026-09-04. 계산을 `segments._write_scope()` 로 옮겼다.
    #   `ortho` 가 이 결과를 읽는데 STEPS 순서가 … → ortho → publish 라
    #   뒤 단계 산출을 앞 단계가 읽고 있었다.
    #
    #   ★ web/data/scope.geojson 은 **더 이상 내지 않는다.** 처음부터
    #     화면이 읽지 않았다 — web/js 참조가 어느 커밋에도 없고, 최초
    #     커밋 185876d 의 view.json 이 이미 bounds·maxBounds·emdBounds 를
    #     들고 있다. 화면 범위는 view.json 이, 마스킹은 mask·mask_soft 가
    #     맡는다. 이것은 ortho 전용 중간 산출물이었고, 그것을 web/data 에
    #     둔 것이 후진 의존의 원인이었다.
    scope = gpd.read_file(P/"scope_5186.gpkg").to_crs(5186).geometry.iloc[0]
    (W/"scope.geojson").unlink(missing_ok=True)

    # 표출 범위(시설 · 상가를 자르는 틀)와 동명동 경계 — 4326
    from shapely.geometry import box
    emd4 = emd.to_crs(4326).geometry.iloc[0]
    scope4 = gpd.GeoSeries([scope], crs=5186).to_crs(4326).iloc[0]

    # ── 캐시 무효화 스탬프 ──────────────────────────────────────
    # ★ 2026-08-22. 툴팁을 고치고 몇 번을 새로고침해도 옛 화면이 떴다.
    #   개발 중에는 성가신 정도지만 배포에서는 다르다 — 관제사가 옛
    #   segments.geojson 을 보면 **판정 색이 틀린 지도**를 본다.
    #   이 프로젝트가 막으려는 바로 그 종류의 사고다.
    #
    # ★ 타임스탬프를 쓰지 않는다. 같은 입력에 같은 산출물이 나와야 하는
    #   저장소다(golden 지문). 매 실행 값이 달라지면 index.html 이 계속
    #   더러워지고 "재실행했더니 diff 가 떴다" 가 일상이 된다.
    #   **판정 데이터의 내용 해시**를 쓴다. 데이터가 그대로면 스탬프도 그대로다.
    _BUILD = hashlib.sha256(
        (W/"segments.geojson").read_bytes()).hexdigest()[:8]

    # 뷰 설정: bbox 를 코드에 하드코딩하지 않고 데이터에서 뽑아 내보낸다.
    # terrain/ortho 가 기록한 타일 범위는 보존한다.
    _vj = W/"view.json"
    _prev = json.loads(_vj.read_text(encoding="utf-8")) if _vj.exists() else {}
    minx, miny, maxx, maxy = gpd.GeoSeries([scope4], crs=4326).total_bounds
    m = 0.002
    # ★ 2026-09-17 (DECISIONS §181-2). 지도가 움직일 수 있는 범위. 건물 · 목적지를 여기로 자른다 —
    #   판정 스코프로 자르면 광주지방법원처럼 지도 안에 있는 건물이 안 그려지고 검색에도 없다.
    move4 = box(round(minx-m, 4), round(miny-m, 4), round(maxx+m, 4), round(maxy+m, 4))
    move = gpd.GeoSeries([move4], crs=4326).to_crs(5186).iloc[0]
    (W/"view.json").write_text(json.dumps({
        "center": [round((minx+maxx)/2, 6), round((miny+maxy)/2, 6)],
        "bounds": [[round(minx, 4), round(miny, 4)], [round(maxx, 4), round(maxy, 4)]],
        "maxBounds": [[round(minx-m, 4), round(miny-m, 4)], [round(maxx+m, 4), round(maxy+m, 4)]],
        "minZoom": 13.6, "maxZoom": 20,
        # terrain / ortho 타일의 실제 범위. 지도 소스의 bounds 로 쓴다.
        # 없으면 브라우저가 범위 밖 타일을 요청해 404 가 뜬다.
        # terrain.py / ortho.py 가 채운다. 여기서 새로 쓰면서 지우면 안 된다.
        # ★ 캐시 무효화 스탬프. data.js 가 이 값을 읽어 데이터 URL 에 붙인다.
        #   segments.geojson 은 매 실행 바뀌므로 옛 것을 보면 판정이 틀린다.
        "build": _BUILD,
        "terrainBounds": _prev.get("terrainBounds"),
        "orthoBounds":   _prev.get("orthoBounds"),
        "emdBounds": [[round(*emd.to_crs(4326).total_bounds[:1], 4), round(emd.to_crs(4326).total_bounds[1], 4)],
                      [round(emd.to_crs(4326).total_bounds[2], 4), round(emd.to_crs(4326).total_bounds[3], 4)]],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 건물은 스코프 전체를 덮는다. 동명동만 자르면 안전센터 주변이
    # 길만 남아 3D 가 안 선다. (2,518동 → 5,713동)
    # ★ 2026-09-17 (§181-2). 스코프가 아니라 **지도 이동 범위**(view.maxBounds)로 자른다.
    b = gpd.read_file(P/"building_5186.gpkg")
    b = b[b.intersects(move)].copy()
    b["flo"] = b.GRO_FLO_CO.fillna(1).astype(float).clip(lower=1)   # 0층 291동 → 1층
    b["h"] = (b.flo*3.3).round(1)
    # ★ 2026-09-22 (DECISIONS §217-3) 사용자 보고 「건물과 길이 겹친다」. 도로명주소 건물 면과
    #   수치지형도 도로 면이 서로 다른 측량이라 12,736동 중 370동이 발자국의 5% 넘게 도로 위에
    #   있었다(154동은 20% 넘게). 화면에서는 건물이 차도를 먹었다. **표시용으로** 건물에서 도로 면을
    #   뺀다. 발자국 절반 넘게 도로 위인 건물은 자르지 않는다 — 복개 구조물이거나 한쪽 자료가
    #   틀린 것이라, 자르면 건물이 사라진다. 판정 입력(`building_5186.gpkg`)은 그대로다.
    from firelane import publish_basemap as _bm
    _road = _bm.union("road_area", move)
    # ★ 2026-09-22 (§218) — 발행된 도로면은 `SIMPLIFY_M` 만큼 단순화돼 경계가 그만큼 움직인다.
    #   원본 도로면 · 1% 문턱으로 빼면 화면에서 1~5% 겹침이 161동 남았다(`test_building_road_overlap`).
    #   그 여유만큼 넓힌 도로면으로 재고 빼며, 문턱은 0.2% 로 낮춘다(스치는 것도 깎는다).
    #   「절반 넘게 도로 위라 안 자름」 판단은 **원본** 도로면으로 한다 — 넓힌 면으로 하면 그 몫이
    #   부풀어 안 잘리는 건물이 83 → 113동으로 늘었다.
    _road_cut = _road.buffer(_bm.SIMPLIFY_M)
    _area = b.geometry.area.where(b.geometry.area > 0, 1)
    _ov = b.geometry.intersection(_road).area / _area
    _cut = (b.geometry.intersection(_road_cut).area / _area > 0.002) & (_ov <= 0.5)
    # 빼기가 도로면의 꼭짓점을 건물에 옮겨 붙인다(파일이 5% 불었다) — 깎인 건물만 0.2m 로 편다.
    #   발행 도로면 단순화(0.4m)보다 작아 겹침을 되살리지 않는다(`test_building_road_overlap`).
    b.loc[_cut, "geometry"] = (b.loc[_cut, "geometry"].difference(_road_cut).buffer(0)
                               .simplify(0.2, preserve_topology=True))
    # 잘라서 부스러기(2㎡ 미만)만 남은 것만 버린다 — 원래 작은 건물은 건드리지 않는다
    b = b[~(_cut & (b.geometry.is_empty | (b.geometry.area < 2.0)))].copy()
    print(f"  건물 · 도로 겹침 {int(_cut.sum())}동 잘라냄 · 절반 넘게 도로 위 {int((_ov > 0.5).sum())}동은 그대로")
    cols = ["BUL_MAN_NO","BULD_NM","flo","h"] + (["z"] if "z" in b.columns else [])
    b = b[cols+["geometry"]]
    b.to_crs(4326).to_file(W/"buildings.geojson", **PREC)
    # ★ 예산을 넘을 때만 단순화한다(§181-2). 늘 깎으면 스코프 안 건물 모양까지 바뀐다.
    #   공차는 고정 단계라 같은 입력에 같은 산출물이다.
    for tol in BLDG_TOL:
        if (W/"buildings.geojson").stat().st_size <= BLDG_MB * 1_000_000:
            break
        b.assign(geometry=b.geometry.simplify(tol, preserve_topology=True)) \
         .to_crs(4326).to_file(W/"buildings.geojson", **PREC)
        print(f"  건물 단순화 {tol}m")
    _mb = (W/"buildings.geojson").stat().st_size / 1_000_000
    if _mb > BLDG_MB:
        raise SystemExit(f"buildings.geojson {_mb:.1f}MB — 예산 {BLDG_MB}MB 를 단순화로도 못 맞췄다")
    print(f"  건물 {len(b):,}동 (지도 이동 범위) · {_mb:.2f}MB")

    # ── 마커 3종 ────────────────────────────────────────────────
    # 전부 스코프로 자른다. 자르지 않으면 마스크가 덮은 어두운 영역 위에
    # 점이 떠서 "저게 뭐냐"는 오해를 부른다. (소화전 18개 중 스코프 밖이 7개였다)

    # 소화전. ★ 2026-08-31 실측 — processed 524 · 스코프 안 153 · 동명동 41.
    # 종전 주석의 "공개 31개 · 동명동 1개" 는 소스 교체 전 값이고 9개월 낡았다.
    # 희소성 논거를 그 숫자로 쓰면 안 된다(MASTER §3-12 도 같이 고쳤다).
    hyd = gpd.read_file(P/"hydrant_point.geojson")
    # ★ 컬럼을 하드코딩하지 않는다. 2026-08-15 소스 교체 때 여기가
    #   KeyError 로 파이프라인 전체를 세웠다. 있는 것만 싣는다.
    #   결손은 폐기가 아니다 — 0건이어도 빈 레이어로 발행하고 지도는 뜬다.
    #   다만 조용히 넘어가지도 않는다. 없으면 이름을 찍는다.
    # ★ 2026-08-31. 종전 `want` 는 **한글 컬럼명**이었고 실물은 영문
    #   카멜케이스다. 9종 전부 못 찾아 `속성 0종` 으로 발행됐고 지도
    #   팝업이 비어 있었다. "있는 것만 싣는다" 가 **아무것도 안 싣는
    #   것**을 조용히 통과시킨 것이다 — 경고는 매 실행 찍혔지만
    #   0종을 실패로 보는 곳이 없었다.
    #
    #   표시명 ← 원본명 으로 못박는다. 관제 시설 카드가 이 표시명을 쓴다(MASTER §11-4).
    want = {"시설번호": "fcltyNo", "시설유형코드": "fcltySeCode",
            "소재지도로명주소": "rdnmadr", "소재지지번주소": "lnmadr",
            "상세위치": "descLc", "설치연도": "installationYear",
            "보호틀유무": "prtcYn", "관할기관명": "institutionNm",
            "안전센터명": "safeCnterNm"}
    have = {k: v for k, v in want.items() if v in hyd.columns}
    miss = [k for k, v in want.items() if v not in hyd.columns]
    if miss:
        print(f"  ! 소화전 속성 없음 {miss} — 있는 것만 싣는다")
    # ★ 0종은 결손이 아니라 매핑이 통째로 틀어진 것이다. 조용히 넘기지 않는다.
    if not have and len(hyd):
        raise KeyError(
            f"소화전 속성 매핑이 전부 빗나갔다. 실물 컬럼: {list(hyd.columns)[:12]}\n"
            "  publish_web.want 를 실물에 맞춰라. 0종 발행은 팝업을 비운다.")
    hyd = hyd.rename(columns={v: k for k, v in have.items()})
    have = list(have)
    hcols = have + (["z"] if "z" in hyd.columns else [])
    hyd = hyd[hyd.within(scope4)][hcols + ["geometry"]] if len(hyd) else hyd
    print(f"  소화전 {len(hyd)}개 · 속성 {len(have)}종")
    if len(hyd):
        hyd.to_file(W/"hydrants.geojson", **PREC)
    else:
        # 빈 GeoDataFrame 은 드라이버가 거부한다. 빈 FeatureCollection 을 직접 쓴다.
        (W/"hydrants.geojson").write_text(
            '{"type":"FeatureCollection","features":[]}', encoding="utf-8")
        print("    ★ 스코프 안 소화전 0개. 빈 레이어로 발행했다.")

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
    # ★ 같은 GeoSeries 의 x, y 라 길이가 같아야 한다.
    cctv["_k"] = list(zip(cctv.geometry.x.round(6),
                          cctv.geometry.y.round(6), strict=True))
    _agg = dict(
        관리기관명=("관리기관명", "first"),
        소재지도로명주소=("소재지도로명주소", "first"),
        카메라대수=("카메라대수", "sum"),
        카메라화소=("카메라화소", "first"),
        촬영방면=("촬영방면", "first"),
        최초설치=("설치연도", "min"),
        최근설치=("설치연도", "max"),
        설치회차=("설치연도", "size"),
        geometry=("geometry", "first"),
    )
    # z 는 terrain.py 산출물이다. DEM 이 없으면 컬럼 자체를 만들지 않는다.
    # 이전 fallback 이 ("카메라대수","size") 였어서 DEM 없이 돌리면
    # 표고 자리에 그룹 행 수(1,2,3...)가 들어갔다. 표고 없음은 결측이지 카운트가 아니다.
    # app.js 는 coalesce(z, 0) 이라 컬럼이 없어도 안전하다.
    if "z" in cctv.columns:
        _agg["z"] = ("z", "first")

    agg = cctv.groupby("_k").agg(**_agg).reset_index(drop=True)
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

    # ── 목적지 색인 ─────────────────────────────────────────
    # ★ 2026-09-17 (DECISIONS §181 · PLAN 「목적지 검색 — 주소 · 건물명 · 관공서」).
    #   poi.geojson 은 지도 라벨이다(스코프 · 1층). 검색은 dest.geojson 을 읽는다 —
    #   상가 + 주소/건물(내비게이션용DB) + 관공서/학교(민원행정기관).
    # ★ 2026-09-17 (DECISIONS §183-1 · 사용자). 목적지는 **동명동 경계 안만**이다. 화재 발생 후보지 스코프가
    #   동명동이다. N1.1 은 지도 이동 범위로 잘라 동구청 · 동부소방서가 목적지로 떴다. 지도(건물 · 라벨)는
    #   지금처럼 안전센터 · 회랑까지 넓게 둔다 — 넓은 것은 표출이고 목적지는 판정 스코프다.
    # ★ 입력이 없으면 죽는다. 빠진 채 발행하면 검색에서 법원이 또 조용히 사라진다.
    from firelane import destinations as _dest
    for _need in (P/"navi_build.csv", P/"navi_jibun.csv", P/"civil_office.geojson"):
        if not _need.exists():
            raise FileNotFoundError(f"{_need.name} 없음 — ingest 를 먼저(목적지 색인 원천)")
    _store = poi[["상호명", "cat", "상권업종중분류명", "도로명주소", "geometry"]].rename(
        columns={"상호명": "name", "상권업종중분류명": "sub", "도로명주소": "addr"})
    _rd = dict(dtype=str, keep_default_na=False, encoding="utf-8-sig")
    dest, _st = _dest.build_index(
        _store, pd.read_csv(P/"navi_build.csv", **_rd), pd.read_csv(P/"navi_jibun.csv", **_rd),
        gpd.read_file(P/"civil_office.geojson"), emd4)
    dest.to_file(W/"dest.geojson", **PREC)
    _nv = _st["navi"]
    print(f"  목적지 {_st['total']:,} — 상가 {_st['store']:,} · 주소/건물 {_st['build']:,} · 관공서/학교 {_st['civil']:,}")
    print(f"    내비DB {_nv['rows']:,}행 — 출입구 {_nv['entrance']:,} · 중심점 {_nv['center']:,} · "
          f"좌표 없음(뺌) {_nv['no_coord']:,} · 같은 주소(뺌) {_nv['same_addr']:,}")

    # ── 시설 마커 ──────────────────────────────────────────────
    # 형상·색·크기는 표현이다. web/config.js 의 markers[] 가 정본이고
    # app.js 가 런타임에 폴리곤으로 만든다. 위치는 위에서 이미 발행했다
    # (cctv.geojson / hydrants.geojson / stations.geojson).
    # 여기서 형상을 굽지 않는다. 구우면 UI 가 값을 못 바꾼다.
    (W/"markers.geojson").unlink(missing_ok=True)

    # ── 스키마는 그대로 복사하지 않는다 ────────────────────────
    # ★ 2026-08-23. 종전에는 shutil.copy 였다. processed 스키마는 processed
    #   산출물(31필드)을 서술하는데 web 은 27필드다. 그래서 web 스키마가
    #   `merged_n` · `cov_*` · `merge_why` 5개를 **웹 필드처럼** 서술하고,
    #   정작 web 에만 있는 `seg_no` 는 빠져 있었다.
    #   UI 담당이 이 표를 보고 `merged_n` 으로 분기하면 undefined 가 나온다 —
    #   2026-08-18 에 MASTER §11 필드표로 똑같이 겪은 일이다.
    #
    # `test_schema_matches_data` 는 `>=`(부분집합)만 봐서 못 잡았다.
    # MASTER §18-5 R7 은 "컬럼 집합 == 스키마 키 집합" 검사를 넣겠다고
    # 적어놓고 안 넣었다. `pipeline.verify()` 가 이제 그것을 본다.
    _sch = json.loads((P/"segments.schema.json").read_text(encoding="utf-8"))
    _pub = set(_cols) | {"seg_no"} | ({"z"} if "z" in _seg.columns else set())
    _dropped = sorted(k for k in _sch["fields"] if k not in _pub)
    _sch["fields"] = {k: v for k, v in _sch["fields"].items() if k in _pub}
    _sch["fields"]["seg_no"] = ("int 도로명 안에서의 구간 순번. ★ 표기 전용이고 "
                                "publish 가 만든다. 노딩이 바뀌면 밀린다 — "
                                "외부 참조는 seg_uid, 화면 표기는 seg_label")
    _sch["scope"] = "web — 표출용 사본. processed 전용 컬럼은 뺐다"
    _sch["dropped_from_processed"] = _dropped
    (W/"segments.schema.json").write_text(
        json.dumps(_sch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ── 차량 제원 대장 → 화면 ──────────────────────────────────
    # ★ 2026-09-01. 화면이 최소회전반경 7.30m 을 확정값처럼 띄우는데
    #   대장의 `turn_radius_verified` 는 false 이고 `can_turn()` 은 그
    #   플래그를 보고 **아무것도 막지 않는다**(DECISIONS 81). 판정은
    #   "못 믿는 값" 으로 아는데 화면만 몰랐다(DECISIONS 86-5).
    # ★ 값을 config.js 에 손으로 옮겨 적지 않는다. 대장이 정본인데 사본을
    #   만들면 갈린다 — 실제로 갈려 있었다(DECISIONS 87 ③).
    #   `web/config.js` 의 CONFIG.fleet 이 제원 숫자를 안 적는 것과 같은 규칙.
    from firelane import ledger as _ld
    _spec = (_ld.load() if hasattr(_ld, "load") else
             __import__("yaml").safe_load(
                 (ROOT/"sources.yaml").read_text(encoding="utf-8"))
             ).get("vehicle_spec", {})
    # ★ 미검증 값은 아예 안 보낸다. 게이트는 아래 `_keep` 화이트리스트다 —
    #   대장의 `absent` 를 코드가 읽지는 않는다. 종전 주석이 그렇게 적어
    #   없는 의존을 주장하고 있었다(2026-09-02 정정). 대장이 `absent` 로 든
    #   축거·회전반경을 그대로 실으면 대장과 발행물이 어긋난다 —
    #   `doc_fsck ③` 이 그것을 잡았다(2026-09-01). 화면은 그 숫자를 쓰지
    #   않고 **플래그만** 쓰므로 보낼 이유도 없다. 안 보내면 실수로 쓸
    #   위험까지 같이 사라진다.
    _keep = ("kind", "width_m", "length_m", "height_m", "clearance_m",
             "gradeability_pct",
             "verified", "wheelbase_verified", "turn_radius_verified")
    (W/"vehicle_spec.json").write_text(json.dumps(
        {k: _spec[k] for k in _keep if k in _spec}
        | {"_note": ("성격 선언이다. *_verified 가 false 면 그 값으로 "
                     "화면이 말하지 않는다 — DECISIONS 81 · 86-5")},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  차량 제원 대장 발행 · 회전반경 검증 "
          f"{'O' if _spec.get('turn_radius_verified') else 'X'}")
    _missing = sorted(_pub - set(_sch["fields"]))
    print(f"  스키마 {len(_sch['fields'])}필드 · processed 전용 {len(_dropped)} 제외"
          + (f"  ★ 서술 없는 필드 {_missing}" if _missing else ""))

    # ── index.html 에 스탬프 주입 ───────────────────────────────
    # ★ ES 모듈 그래프는 진입점에 쿼리를 붙여도 그 안의 import 까지
    #   전파되지 않는다. 그래서 데이터 URL 은 js/data.js 가 view.json 의
    #   build 를 읽어 따로 붙이고, JS/CSS 파일 자체는 여기서 붙인다.
    # ★ 내용 해시라 데이터가 그대로면 이 파일도 안 바뀐다. 재실행 diff 없음.
    # ── web/data 계보 ──────────────────────────────────────────
    # ★ 2026-08-22. 종전에는 tools/web_manifest.py 를 사람이 따로 기억해서
    #   돌려야 했고, 아무도 안 돌렸다. CI 가 main 에서만 도는 바람에 2주
    #   동안 몰랐고 gis 로 켜자마자 바로 잡혔다.
    #   생산자가 자기 산출물의 계보를 쓴다 — ingest 가 processed/
    #   _manifest.json 을 쓰는 것과 같다. 순서를 기억할 필요가 없어진다.
    # ★ index.html 스탬프보다 **뒤**여야 한다. 스탬프가 web/ 을 바꾸므로
    #   먼저 뜨면 지문이 즉시 낡는다.
    # ★ 2026-08-24. index.html 을 더 이상 고치지 않는다.
    #
    #   (당시 이 파일은 CODEOWNERS 상 UI 담당 소유였다 — 지금 정본은 CODEOWNERS.)
    #   여기서 스탬프를 주입하면 **판정이 바뀔 때마다** 그 파일이
    #   바뀌고, GIS 가 파이프라인만 돌려도 UI 리뷰가 걸린다.
    #   스탬프가 내용 해시라 잡음이 아니라 **의미 있는 작업을 한 그
    #   순간에만** 걸린다. 더 나쁘다.
    #
    #   index.html 주석이 이미 정답을 적어놨다 —
    #     "저장소에 커밋된 상태에서는 문자 그대로 BUILD 이고,
    #      그래도 동작한다(쿼리는 파일 조회에 영향 없음)"
    #   저장소는 BUILD 로 두고 **배포 시점에** 찍는다(.github/workflows/
    #   pages.yml). 값은 view.json 의 build 를 그대로 쓴다 — 여기서 이미
    #   썼고 data.js 가 읽는 그 값이다.
    #
    #   ★ 경계는 경로로 갈린다. 생성물은 web/data/ 안에서 끝나야 하고
    #     사람 파일을 코드가 고치면 안 된다.
    #     tests/test_web_ownership.py 가 이 구조를 지킨다.
    # ★ 2026-09-01. 판정 반영 경로를 앱이 읽을 수 있게 낸다(MASTER §20-5).
    #   `route_usage` 는 거리만 본 1차이고 이것이 폭·내륜차·판정을 반영한
    #   2차다. 조인 키는 `seg_uid` — `seg_id` 는 실행 간 유지되지 않는다.
    _rv = P / "route_vehicle.csv"
    if _rv.exists():
        _d = pd.read_csv(_rv)
        _out = {r.seg_uid: {"use": int(r.route_vehicle),
                            "cost": round(float(r.cost), 1),
                            "passable": int(r.passable),
                            "reachable": int(r.reachable)}
                for r in _d.itertuples()}
        (W / "route_vehicle.json").write_text(
            json.dumps(_out, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8")
        print(f"  route_vehicle.json {len(_out):,}구간")
    else:
        print("  ! route_vehicle.csv 없음 — 2차 경로를 안 낸다")

    print(f"  스탬프 {_BUILD} → view.json (index.html 은 배포 시 주입)")

    # ★ 2026-09-16. 내비 그래프를 여기서 같이 낸다(DECISIONS §170-5). 종전에는 `publish_navi` 를
    #   부르는 곳이 없었다 — 파이프라인에도 verify 에도 없고 손 명령으로만 적혀 있었다. 판정이
    #   1,101 → 1,281 로 바뀐 전량 뒤에도 navi_graph.json 이 엣지 1,101 그대로였고, 내비는 옛
    #   구간으로 경로를 짰다. 매니페스트보다 **먼저** 불러야 계보에 새 그래프가 잡힌다.
    from firelane import publish_navi as _navi
    _navi.main()
    # ★ 2026-09-22 (DECISIONS §212). `fleet.json` 도 같은 모양이었다 — `publish_fleet` 를 부르는
    #   곳이 없어 손으로만 돌았다. 회전반경 숫자가 그 파일로 화면까지 가므로 여기서 같이 낸다.
    from firelane import publish_fleet as _fleet
    _fleet.main()
    # ★ 2026-09-22 (DECISIONS §213-4). 내비 바탕의 도로면 · 보도. 판정과 무관한 색칠용이다.
    from firelane import publish_basemap as _base
    _base.main()
    # ★ 2026-09-22 (DECISIONS §216-3). 받아 두고 안 쓰던 데이터 — 경로 주변 사정 · 출동 이력.
    from firelane import publish_context as _ctx
    _ctx.main()

    _wm = webmanifest.write()
    print(f"  web/data 계보 → {_wm['total_mb']}MB · 타일 {_wm['tiles_digest']}")
    for f in sorted(W.iterdir()):
        print(f"  {f.name:26} {f.stat().st_size/1024:7.0f} KB")

if __name__ == "__main__":
    from firelane.guards import warn_direct_call

    warn_direct_call(__name__)
    main()
