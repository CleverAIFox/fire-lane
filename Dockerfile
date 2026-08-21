# Fire-Lane ETL 이미지
#
# ★ 2026-08-21 정정. 이전 CMD 는 `src.api.main:app` 을 가리켰으나
#   `src/api/` 가 존재하지 않는다. 빌드는 되고 실행하면
#   ModuleNotFoundError 로 죽었다. 지금 이 저장소가 실제로 돌리는 것은
#   ETL 파이프라인 하나뿐이므로 ETL 이미지로 정정한다.
#
# API 가 생기면 이 파일을 복사하지 말고 Dockerfile.api 를 따로 만들 것.
# GDAL + geopandas 는 1.5GB 가 넘는다. FastAPI 서빙에 그게 딸려가면
# ECS 콜드스타트가 무의미하게 길어진다. 이미지는 용도별로 나눈다.
#
#   etl     GDAL · geopandas · rasterio   ← 이 파일. 상시 실행 아님
#   api     fastapi · uvicorn · shapely   ← 슬림. ECS 에 올라갈 것
#   vision  opencv · ultralytics          ← 이가연 담당 붙을 때

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gdal-bin libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 의존성 레이어를 소스와 분리한다. 코드만 고쳤을 때 재설치하지 않는다.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src ./src
COPY tools ./tools
COPY sources.yaml ./
RUN uv sync --frozen

# 기본 동작은 상태 조회다. 실행 없이 무엇이 도는지만 보여준다.
CMD ["uv", "run", "python", "src/etl/pipeline.py", "--check"]
