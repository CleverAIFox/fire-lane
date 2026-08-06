"""
동명동 GIS 마스터 데이터 전처리 파이프라인
원본(raw) -> 동명동 클리핑 -> 표준 좌표계(EPSG:4326) -> processed/ 저장

실행: uv run python src/etl/preprocess.py
"""

import json

import geopandas as gpd
import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 광주 동구 동명동 법정동코드 (LSMD 데이터 기준 확인됨)
DONGMYEONG_EMD_CD = "12210108"

# juso.go.kr 도로구간(TL_SPRD_MANAGE) 좌표계: .prj 파일 미제공, 좌표범위 역산으로 EPSG:5179(UTM-K, 전국 통합좌표계) 확인됨
JUSO_ROAD_CRS = "EPSG:5179"

# 3단 필터링 임계값 (마스터문서 4장). ⚠ 공식 규정 인용 아님, 팀 자체 추정 기준(문서화 필요)
# BLOCK: 소방차 폭(2.5m) 기준 절대 진입 불가
# PASS : 왕복 4차선급(차로폭 3~3.5m x 4개 차로 ≈ 12~14m) 추정치. 비용보다 안전 우선 -> 보수적으로 하한값 채택
TIER_BLOCK_MAX = 2.0
TIER_PASS_MIN = 12.0

# 경계 밖 확장 허용 마진(m). 순수 clip(정확한 경계선에서 절단)은 도로 중간을 뚝 끊어 부자연스럽고,
# 순수 intersects(경계에 걸치면 전체 포함)는 긴 간선도로가 수 km 밖까지 끌려와 지저분해짐
# -> 절충: 경계를 이 만큼 버퍼링한 뒤 그 확장된 경계로 클리핑(trim). "경계에 매몰되지 않되 무한정 늘어지지도 않게"
BOUNDARY_BUFFER_M = 10

# CCTV 커버리지 판정 반경(m). 25m — 호모그래피 정확도가 카메라 거리에 비례해 저하되는 광학적 한계 반영
# (40m -> 25m로 축소 조정: 카메라에서 멀수록 원근왜곡 오차가 커져 신뢰 가능한 유효거리가 아님)
CCTV_COVERAGE_RADIUS_M = 25


def load_dongmyeong_boundary() -> gpd.GeoDataFrame:
    """법정동 경계(LSMD_ADM_SECT_UMD)에서 동명동만 추출"""
    src = RAW_DIR / "lsmd_admin_boundary_umd.shp"
    gdf = gpd.read_file(src, encoding="cp949")
    dongmyeong = gdf[gdf["EMD_CD"] == DONGMYEONG_EMD_CD].copy()
    if dongmyeong.empty:
        raise ValueError(f"EMD_CD={DONGMYEONG_EMD_CD} 동명동 경계를 찾지 못함. 원본 데이터 확인 필요")
    return dongmyeong


def clip_road_network(boundary: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """표준노드링크(MOCT_LINK/NODE)를 동명동 경계로 클리핑"""
    link = gpd.read_file(RAW_DIR / "its_road_link.shp", encoding="cp949")
    node = gpd.read_file(RAW_DIR / "its_road_node.shp", encoding="cp949")

    # 좌표계 파라미터 사실상 동일(TM 중부원점) -> 강제 일치 후 클리핑
    link = link.set_crs(boundary.crs, allow_override=True)
    node = node.set_crs(boundary.crs, allow_override=True)

    link_clip = gpd.clip(link, boundary)
    node_clip = gpd.clip(node, boundary)
    return link_clip, node_clip


def load_juso_road_section(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """juso.go.kr 도로구간(TL_SPRD_MANAGE, ROAD_BT 포함)을 동명동 관련 구간으로 선별 + 3단 필터링
    ⚠ 순수 clip(경계선 정확히 절단)도, 순수 intersects(걸치면 전체포함)도 아닌 절충안:
    경계를 BOUNDARY_BUFFER_M만큼 살짝 넓힌 뒤 그 확장된 경계로 클리핑(trim).
    -> 도로 중간이 뚝 끊기지 않으면서도, 간선도로가 몇 km 밖까지 끌려오는 것도 방지.
    """
    src = RAW_DIR / "juso_road_section.shp"
    gdf = gpd.read_file(src, encoding="cp949")
    gdf = gdf.set_crs(JUSO_ROAD_CRS, allow_override=True).to_crs(5179)  # 버퍼는 미터단위 평면좌표계에서

    boundary_5179 = boundary.to_crs(5179)
    buffered = boundary_5179.copy()
    buffered["geometry"] = buffered.geometry.buffer(BOUNDARY_BUFFER_M)

    trimmed = gpd.clip(gdf, buffered).to_crs(4326)

    def classify_tier(width_m: float) -> str:
        if width_m < TIER_BLOCK_MAX:
            return "FIXED_BLOCK"
        elif width_m >= TIER_PASS_MIN:
            return "FIXED_PASS"
        return "CANDIDATE"

    trimmed = trimmed.copy()
    trimmed["tier"] = trimmed["ROAD_BT"].apply(classify_tier)
    return trimmed


def load_hydrants(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """전국소방용수시설표준데이터에서 동명동 소재 소화전만 추출"""
    src = RAW_DIR / "fire_hydrants.json"
    with open(src, encoding="utf-8") as f:
        raw = json.load(f)
    df = pd.DataFrame(raw["records"])
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["경도"], df["위도"]), crs=4326)
    clip = gpd.clip(gdf, boundary.to_crs(4326))  # 점 데이터는 clip해도 잘림 문제 없음
    return clip


def load_cctv_points(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """전국CCTV표준데이터에서 동명동 소재 CCTV만 추출 (위도/경도 컬럼 기반)
    도로명주소 텍스트에서 도로명을 추출해 road_name 매칭용으로 별도 저장
    (좌표 버퍼보다 신뢰도 높은 1차 매칭 기준 - 공식 주소 문자열 기반)
    """
    src = RAW_DIR / "cctv_locations.csv"
    df = pd.read_csv(src, encoding="cp949")
    # 주소 포맷: "{구} {도로명}[번지 등] {번호}" -> 두 번째 토큰이 도로명
    df["road_name_from_addr"] = df["소재지도로명주소"].str.split().str[1]
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["경도"], df["위도"]),
        crs=4326,
    )
    clip = gpd.clip(gdf, boundary.to_crs(4326))
    return clip


def compute_status(row) -> str:
    """road_segment 최종 상태(색상) 계산 - 6색 체계 (9장 GIS 마스터 아키텍처)
    BLUE(주도로,계산불필요) / GREEN·YELLOW·ORANGE(실시간 3단계) / RED(절대불가,계산불필요) / GRAY(사각지대)
    """
    if row["tier"] == "FIXED_BLOCK":
        return "RED"
    if row["tier"] == "FIXED_PASS":
        return "BLUE"
    # CANDIDATE
    if row["cctv_coverage"] == "BLIND":
        return "GRAY"
    # COVERED + CANDIDATE: 실시간 YOLO 판정 전이므로 잠정 YELLOW
    # ⚠확인필요 : mock CCTV 프레임 판정 파이프라인 연결 시 GREEN/YELLOW/ORANGE 3단계로 실시간 갱신되어야 함(current_status는 동적 계층)
    return "YELLOW"


def main():
    print("1. 동명동 법정동 경계 추출...")
    boundary = load_dongmyeong_boundary()
    boundary_wgs84 = boundary.to_crs(4326)
    boundary_wgs84.to_file(PROCESSED_DIR / "dongmyeong_boundary.geojson", driver="GeoJSON")
    print(f"   -> dongmyeong_boundary.geojson ({len(boundary)}개 폴리곤)")

    print("2. 표준노드링크 클리핑 (그래프 뼈대용, 폭 정보 없음)...")
    link, node = clip_road_network(boundary)
    link.to_crs(4326).to_file(PROCESSED_DIR / "road_link_raw.geojson", driver="GeoJSON")
    node.to_crs(4326).to_file(PROCESSED_DIR / "road_node_raw.geojson", driver="GeoJSON")
    print(f"   -> road_link_raw.geojson ({len(link)}개 LINK)")
    print(f"   -> road_node_raw.geojson ({len(node)}개 NODE)")

    print("3. juso.go.kr 도로구간(ROAD_BT) 클리핑 + 3단 필터링...")
    road_segment = load_juso_road_section(boundary)
    tier_counts = road_segment["tier"].value_counts().to_dict()
    print(f"   -> {len(road_segment)}개 구간, tier 분포: {tier_counts}")

    print("4. CCTV 위치 추출 및 CANDIDATE 구간 버퍼조인...")
    cctv = load_cctv_points(boundary)
    cctv.to_file(PROCESSED_DIR / "cctv_points.geojson", driver="GeoJSON")
    print(f"   -> cctv_points.geojson ({len(cctv)}건)")

    # 미터 단위 버퍼 연산을 위해 UTM-K(EPSG:5179)로 임시 변환
    road_5179 = road_segment.to_crs(5179)
    cctv_5179 = cctv.to_crs(5179)
    cctv_union = cctv_5179.geometry.union_all() if len(cctv_5179) else None
    cctv_road_names = set(cctv["road_name_from_addr"].dropna().unique())

    def check_coverage(row_geom, row_name) -> str:
        """1차: 주소 텍스트 정확 매칭(신뢰도 높음) / 2차(보조): 좌표 버퍼(신뢰도 낮음, 폴백용)"""
        if row_name in cctv_road_names:
            return "COVERED"
        if cctv_union is not None and row_geom.distance(cctv_union) <= CCTV_COVERAGE_RADIUS_M:
            return "COVERED"
        return "BLIND"

    road_segment["cctv_coverage"] = None
    candidate_mask = road_segment["tier"] == "CANDIDATE"
    road_segment.loc[candidate_mask, "cctv_coverage"] = [
        check_coverage(geom, name)
        for geom, name in zip(
            road_5179.loc[candidate_mask, "geometry"],
            road_segment.loc[candidate_mask, "RN"],
        )
    ]

    covered_count = (road_segment["cctv_coverage"] == "COVERED").sum()
    blind_count = (road_segment["cctv_coverage"] == "BLIND").sum()
    print(f"   -> CANDIDATE {candidate_mask.sum()}개 중 COVERED {covered_count}개 / BLIND {blind_count}개")
    print(f"      (주소 텍스트 매칭 우선 적용, 미매칭분만 좌표버퍼 {CCTV_COVERAGE_RADIUS_M}m 폴백)")

    print("4-1. 소화전(소방용수시설) 위치 추출...")
    hydrants = load_hydrants(boundary)
    hydrants.to_file(PROCESSED_DIR / "fire_hydrants.geojson", driver="GeoJSON")
    print(f"   -> fire_hydrants.geojson ({len(hydrants)}건)")
    print("   ⚠ road_segment 스키마에는 아직 미반영 (백로그, 9장 참고) - 좌표 확보만 완료")

    print("5. 최종 상태(current_status) 계산 및 마스터 테이블 저장...")
    road_segment["current_status"] = road_segment.apply(compute_status, axis=1)
    status_counts = road_segment["current_status"].value_counts().to_dict()
    print(f"   -> 상태 분포: {status_counts}")

    # segment_id 자체 부여 (juso RDS_MAN_NO 있으면 그거 기반, 없으면 순번)
    road_segment["segment_id"] = [
        f"seg_{rds}" if pd.notna(rds) else f"seg_auto_{i}"
        for i, rds in enumerate(road_segment.get("RDS_MAN_NO", []))
    ]

    keep_cols = [
        "segment_id", "RDS_MAN_NO", "RN", "ROAD_BT", "ROAD_LT",
        "tier", "cctv_coverage", "current_status", "geometry",
    ]
    road_segment_master = road_segment[keep_cols].rename(columns={
        "RDS_MAN_NO": "rds_man_no", "RN": "road_name",
        "ROAD_BT": "road_bt", "ROAD_LT": "road_lt",
    })
    out_path = PROCESSED_DIR / "road_segment_master.geojson"
    road_segment_master.to_file(out_path, driver="GeoJSON")
    print(f"   -> road_segment_master.geojson 저장 완료 ({len(road_segment_master)}개 구간)")

    print("\n✅ GIS MVP 파이프라인 완료")


if __name__ == "__main__":
    main()
