# Fire-Lane ETL 이미지
#
# ★ 2026-08-21 정정. 이전 CMD 는 `src.api.main:app` 을 가리켰으나
#   `src/api/` 가 존재하지 않는다. 빌드는 되고 실행하면
#   ModuleNotFoundError 로 죽었다. 지금 이 저장소가 실제로 돌리는 것은
#   ETL 파이프라인 하나뿐이므로 ETL 이미지로 정정한다.
#
# API 가 생기면 이 파일을 복사하지 말고 Dockerfile.api 를 따로 만들 것.
# GDAL + geopandas 는 1.5GB 가 넘는다. FastAPI 서빙에 그게 딸려가면
# 기동이 무의미하게 길어진다. 이미지는 용도별로 나눈다.
#
#   etl     GDAL · geopandas · rasterio   ← 이 파일. 상시 실행 아님
#   api     fastapi · uvicorn · shapely   ← 슬림. 상시 서비스가 될 것
#   vision  opencv · ultralytics          ← 이가연 담당 붙을 때
#
# ★ 2026-09-03 정정. 종전에 "ECS 콜드스타트" · "ECS 에 올라갈 것" 으로
#   적혀 있었다. 2026-09-02 에 배포를 **EC2 한 대 + Docker Compose** 로
#   정했고(MASTER §12-8 · DECISIONS §93), 이 머리말만 안 따라왔다.
#
# ★ **ECS 는 기각이 아니라 유보다**(§93-4). 아래 넷 중 둘 이상이 참이면
#   다시 본다 — 상시 서비스가 둘 이상 · 무중단 배포 요구 · 인스턴스 한 대
#   사양 초과 · 인프라 전담 인원. 그러니 이 파일은 그때도 안 고친다.
#
# ★ **이미지 분할은 오케스트레이터와 무관하다.** ECS 도 Compose 도 같은
#   OCI 이미지를 굴리고, 바뀌는 것은 task definition 이냐 compose 파일이냐
#   뿐이다. 지금 셋으로 쪼개 두는 것이 곧 ECS 준비다 — 한 덩어리로
#   만들어두면 그때 쪼개는 것이 진짜 이중 작업이 된다.

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
CMD ["uv", "run", "fire-lane", "--check"]
