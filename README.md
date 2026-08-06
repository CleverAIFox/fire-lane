# Fire-Lane

소방차 출동 시 불법 주정차로 인한 통행 불가 골목을 자동 판정하고 우회 경로를 탐색하는 서비스.
인공지능사관학교 7기 3반 AI보안반 파이널 프로젝트 (2026.08.03 ~ 2026.12.11)

## 프로젝트 전체 문서

**`docs/PROJECT.md`가 이 프로젝트의 단일 소스오브트루스임.** 결정사항, 폐기된 접근, 할 일 목록 전부 여기 있음.
새 팀원은 코드 보기 전에 이 문서부터 읽을 것.

## 개발 환경 세팅

```bash
# 1. Docker Desktop + WSL2가 이미 설치되어 있어야 함
# 2. VS Code에서 이 폴더 열고, 우측 하단 팝업에서 "Reopen in Container" 클릭
#    (또는 Ctrl+Shift+P -> "Dev Containers: Reopen in Container")
# 3. 컨테이너 빌드 완료되면 자동으로 의존성 설치됨 (uv sync)
```

컨테이너 없이 로컬에서 직접 돌리려면:
```bash
uv sync
uv run python src/etl/preprocess.py            # GIS 전처리 파이프라인 (동명동 클리핑, 3단 필터링)
docker compose up -d                            # PostGIS
uv run python src/etl/load_to_postgis.py        # DB 적재
uv run uvicorn src.api.main:app --reload        # API 서버
```

## 데이터

- `data/raw/` : 원본 GIS 데이터 (SHP/CSV). **git에 커밋되지 않음** (`.gitignore` 처리, 100MB 제한 초과). 각자 로컬에만 보관.
- `data/processed/` : 동명동으로 클리핑·정제된 결과물 (GeoJSON, 용량 작음). git에 포함됨.

| 파일 | 원본 출처 | 상태 |
|---|---|---|
| `dongmyeong_boundary.geojson` | 국토교통부 법정동(읍면동단위) 경계도면 | ✅ 완료 |
| `road_link_raw.geojson` / `road_node_raw.geojson` | ITS 국가교통정보센터 표준노드링크 | ✅ 완료 (그래프 뼈대용, 폭 정보 없음) |
| `cctv_points.geojson` | 공공데이터포털 전국CCTV표준데이터 | ✅ 완료 (동명동 53건) |
| `fire_hydrants.geojson` | 공공데이터포털 전국소방용수시설표준데이터 | ✅ 완료 (동명동 1건, `road_segment` 스키마 반영은 백로그) |
| **`road_segment_master.geojson`** | juso.go.kr 도로구간(`TL_SPRD_MANAGE`, ✅ 승인·다운로드·전처리 완료) + CCTV 매칭 | ✅ **완료 — GIS 마스터 데이터 MVP** |

### `road_segment_master.geojson` — 프로젝트 핵심 산출물

동명동 222개 도로구간에 대해 3단 필터링 + CCTV 커버리지 + 최종 상태(6색 체계)까지 계산 완료:

| tier | current_status | 개수 | 의미 |
|---|---|---|---|
| FIXED_PASS (≥12m) | 🔵 BLUE | 9 | 주 도로, 계산 자체 불필요 |
| CANDIDATE, COVERED | 🟡 YELLOW | 136 | 실시간 판정 대상(CCTV 있음, YOLO 미연동 상태라 잠정값) |
| CANDIDATE, BLIND | ⚪ GRAY | 57 | 사각지대 — CCTV 없어서 자동판정 불가 |
| FIXED_BLOCK (<2m) | 🔴 RED | 20 | 절대 진입불가 |

(GREEN·ORANGE는 YOLO 실시간 판정 연동 후 CANDIDATE 193개가 세분화되며 등장 예정)

⚠ BLUE 임계값(12m)은 공식 규정이 아니라 **팀 자체 추정**(차로폭 3~3.5m × 왕복 4차선). "비용 최소화보다 안전 우선"이라는 원칙으로 보수적으로 설정 — 222개 중 9개만 BLUE라는 건 동명동 대부분이 잠재적 위험구간이라는 뜻.
⚠ 경계 클리핑은 순수 절단이 아니라 10m 버퍼 후 trim 방식(도로 중간 끊김 방지, 4장 참고).

## DB & API 서버 (PostGIS 실연동)

```bash
docker compose up -d                          # PostGIS 컨테이너 기동
uv run python src/etl/load_to_postgis.py       # 마스터 데이터 DB 적재
uv run uvicorn src.api.main:app --reload       # API 서버 (실제 DB 쿼리)
```

```
http://localhost:8000/segments          # 전체 도로 세그먼트 (PostGIS 쿼리)
http://localhost:8000/segments/RED      # 상태별 필터링 (DB WHERE절 활용 예시)
http://localhost:8000/cctv              # CCTV 위치
http://localhost:8000/boundary          # 동명동 경계
http://localhost:8000/docs              # Swagger UI (FastAPI 자동생성)
```

⚠ 개발 샌드박스에 Docker가 없어 이 DB 연동은 로컬 환경에서 직접 테스트 필요. 문법 검증만 완료된 상태.

`outputs/dongmyeong_map.html` — Mapbox GL JS 버전 (3D 건물 포함, 토큰 직접 입력 필요)
`outputs/dongmyeong_map_naver.html` — Naver Maps 버전 (Client ID 직접 입력 필요)
⚠ 지도 엔진 최종 선택 미확정(팀 논의 예정) — 둘 다 동일 데이터로 구현되어 비교 가능

## 원본 데이터 로컬 세팅 (각자 1회)

`data/raw/`가 git에 없으므로, 아래 원본 파일들을 각자 다운받아 정해진 이름으로 넣어야 함:

```
data/raw/lsmd_admin_boundary_umd.{shp,dbf,shx,prj,cst,fix}   <- 법정동 경계
data/raw/its_road_link.{shp,dbf,shx,prj,cpg}                  <- 표준노드링크 LINK
data/raw/its_road_node.{shp,dbf,shx,prj,cpg}                  <- 표준노드링크 NODE
data/raw/juso_road_section.{shp,dbf,shx}                      <- juso.go.kr 도로구간(ROAD_BT, ✅ 승인완료), .prj 없음(EPSG:5179로 처리)
data/raw/cctv_locations.csv                                   <- CCTV 좌표
data/raw/fire_hydrants.json                                   <- 소화전 좌표 (전국소방용수시설표준데이터)
```

## 기술 스택

- GIS 전처리: geopandas, shapely, pyproj
- 경로탐색: networkx
- 백엔드: FastAPI
- DB: PostgreSQL + PostGIS
- CV: OpenCV, Ultralytics YOLO11-seg
- 프론트: React(Vite) + 지도 엔진(Mapbox GL JS ↔ Naver Maps, ⏳ 팀 결정 대기 — `outputs/` 안 두 버전 다 확인 가능)
