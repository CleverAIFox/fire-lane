"""
GIS 마스터 데이터 서빙 API (마스터문서 9장 아키텍처)
FE(앱/대시보드)든 내부 시각화든 이 API 하나만 보고 GeoJSON을 받는 구조.
PostGIS를 실제로 쿼리함 (정적 파일 서빙 아님 - road_segment/cctv_point 테이블 필요, load_to_postgis.py로 적재)

실행: docker compose up -d && uv run python src/etl/load_to_postgis.py && uv run uvicorn src.api.main:app --reload
확인: http://localhost:8000/segments , http://localhost:8000/docs (Swagger 자동 생성)
"""

import json

import geopandas as gpd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

DB_URL = "postgresql://postgres:parkingeye@localhost:5432/parkingeye"
engine = create_engine(DB_URL)

app = FastAPI(title="parking-eye GIS API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠확인필요 : 프로덕션 배포 시 프론트 도메인으로 제한 필요
    allow_methods=["GET"],
)


@app.get("/")
def root():
    return {"service": "parking-eye GIS API", "endpoints": ["/segments", "/segments/{status}", "/cctv", "/boundary"]}


@app.get("/segments")
def get_segments():
    """
    도로 세그먼트 마스터 데이터 (PostGIS road_segment 테이블 실쿼리)
    current_status: BLUE(주도로,계산불필요) / GREEN·YELLOW·ORANGE(실시간 3단계, CCTV 판정 대상)
                     / RED(절대불가,계산불필요) / GRAY(사각지대, CCTV 없음)
    """
    gdf = gpd.read_postgis("SELECT * FROM road_segment", engine, geom_col="geometry")
    return JSONResponse(json.loads(gdf.to_json()))


@app.get("/segments/{status}")
def get_segments_by_status(status: str):
    """상태별 필터링 조회 (예: /segments/RED) - DB 쿼리 활용 예시"""
    query = text("SELECT * FROM road_segment WHERE current_status = :status")
    gdf = gpd.read_postgis(query, engine, geom_col="geometry", params={"status": status.upper()})
    return JSONResponse(json.loads(gdf.to_json()))


@app.get("/cctv")
def get_cctv():
    """동명동 CCTV 위치 (PostGIS cctv_point 테이블)"""
    gdf = gpd.read_postgis("SELECT * FROM cctv_point", engine, geom_col="geometry")
    return JSONResponse(json.loads(gdf.to_json()))


@app.get("/boundary")
def get_boundary():
    """동명동 법정동 경계 (PostGIS dongmyeong_boundary 테이블)"""
    gdf = gpd.read_postgis("SELECT * FROM dongmyeong_boundary", engine, geom_col="geometry")
    return JSONResponse(json.loads(gdf.to_json()))

