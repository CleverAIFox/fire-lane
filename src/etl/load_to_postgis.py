"""
road_segment_master.geojson -> PostGIS road_segment 테이블 적재
전제: docker compose up -d 로 postgis 컨테이너가 떠 있어야 함

실행: uv run python src/etl/load_to_postgis.py
"""

import geopandas as gpd
from pathlib import Path
from sqlalchemy import create_engine

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
DB_URL = "postgresql://postgres:parkingeye@localhost:5432/parkingeye"


def main():
    engine = create_engine(DB_URL)

    print("1. road_segment_master.geojson 로드...")
    gdf = gpd.read_file(PROCESSED_DIR / "road_segment_master.geojson")
    gdf.to_postgis("road_segment", engine, if_exists="replace", index=False)
    print(f"   -> road_segment 테이블 적재 완료 ({len(gdf)}행)")

    print("2. CCTV 테이블 적재...")
    cctv = gpd.read_file(PROCESSED_DIR / "cctv_points.geojson")
    cctv.to_postgis("cctv_point", engine, if_exists="replace", index=False)
    print(f"   -> cctv_point 테이블 적재 완료 ({len(cctv)}행)")

    print("3. 동명동 경계 테이블 적재...")
    boundary = gpd.read_file(PROCESSED_DIR / "dongmyeong_boundary.geojson")
    boundary.to_postgis("dongmyeong_boundary", engine, if_exists="replace", index=False)
    print(f"   -> dongmyeong_boundary 테이블 적재 완료")

    print("4. 공간 인덱스 생성...")
    with engine.connect() as conn:
        conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS idx_road_segment_geom ON road_segment USING GIST (geometry);'
        )
        conn.commit()
    print("   -> 완료")

    print("\n✅ PostGIS 적재 완료. psql로 확인: docker exec -it $(docker compose ps -q postgis) psql -U postgres -d parkingeye")


if __name__ == "__main__":
    main()
