# Fire-Lane

동명동 소방차 진입 판정 시스템 · 전남광주통합특별시 동구

**지도** https://woongtopia.github.io/fire-lane/

## 문서

| 문서 | 용도 |
|---|---|
| [`docs/MASTER.md`](docs/MASTER.md) | **여기부터.** 프로젝트 현재 상태 전체 |
| [`docs/GLOSSARY.md`](docs/GLOSSARY.md) | 용어. 지도에 나오는 말들 |
| [`docs/HANDOFF_UI.md`](docs/HANDOFF_UI.md) | UI 담당 인수인계 |
| [`docs/WORKFLOW.md`](docs/WORKFLOW.md) | 브랜치·푸시 규칙 |
| [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md) | 데이터 이력 |
| [`sources.yaml`](sources.yaml) | 데이터 정본 (기계가 읽는다) |

## 실행

```bash
uv sync
uv run python src/etl/ingest.py        # raw -> processed (18종)
uv run python src/etl/segments.py      # 노딩 -> 폭 -> 판정
uv run python src/etl/terrain.py       # 공개DEM -> z 표고 (표현용)
uv run python src/etl/publish_web.py   # -> web/data
uv run pytest tests/test_contract.py   # 계약 검증

cd web && uv run python -m http.server 8000
```

`index.html` 을 더블클릭하면 안 된다. `file://` 에서는 `fetch()` 가 CORS 로 막힌다.

---

# Fire-Lane

> 소방차 출동 경로 상에서 **불법 주정차로 통과 불가능해진 구간을 자동 판정**하고,
> 그 판정을 반영한 **우회 경로를 산출**하는 119상황실용 웹 대시보드.

인공지능사관학교 7기 3반 AI 보안반 · 파이널 프로젝트 (2026-05 ~ 12)
지역 스코프: 전남광주통합특별시 동구 동명동

```
상용 내비(TMAP/카카오)는 "교통량"(얼마나 느린가)을 모델링한다.
우리는 "통과 가능성"(지나갈 수 있는가)을 모델링한다.
```

승용차는 물리적으로 못 지나가는 골목이 거의 없다. **폭 2.5m 차량에만 존재하는 문제다.**

## 파이프라인

```
[프레임 획득]   mock CCTV 서버 (실배포 시 실제 CCTV API로 교체)
      ↓
[호모그래피]    픽셀 → 실제 미터
      ↓
[YOLO11-seg]   차량 탐지·세그멘테이션
      ↓
[유효 통행폭]   변환 좌표계 위에서 직접 측정
      ↓
[등급 판정]     6색 체계 (BLUE/GREEN/YELLOW/ORANGE/RED/GRAY)
      ↓
[경로탐색]      networkx 다익스트라 / A*
```

## 문서

| 문서 | 내용 |
|---|---|
| **[docs/PROJECT.md](docs/PROJECT.md)** | ★ 마스터 문서. 모든 결정의 단일 참조점 |
| [docs/DATA_INVENTORY.md](docs/DATA_INVENTORY.md) | 데이터 확보 현황 + 검증 로그 |
| [sources.yaml](sources.yaml) | 데이터 대장 (기계가 읽는 정본) |
| [src/etl/README.md](src/etl/README.md) | 새 데이터 추가 방법 |

**처음 보는 사람은 `docs/PROJECT.md` §0-3부터 읽어라.** 이전 문서를 왜 폐기했는지가 이 프로젝트의 작업 규칙을 설명한다.

---

# GIS 데이터 파이프라인

## 구조

```
fire-lane/
├── sources.yaml            ★ 데이터 대장. 여기 없으면 파이프라인에 못 들어온다
├── pyproject.toml          전체 스택 의존성
├── requirements-etl.txt    ETL 최소 의존성 (버전 고정)
├── data/
│   ├── raw/                원본 실물 포함 (327MB). 출처별 하위폴더. git 제외
│   └── processed/          동명동 표준 산출물 + _manifest.json
├── scripts/
│   └── normalize_ortho.py  정사영상 파일명 정규화
├── docs/
│   ├── PROJECT.md          ★ 마스터 문서
│   └── DATA_INVENTORY.md   확보 현황 + 검증 로그
└── src/etl/
    ├── README.md           ★ 새 데이터 추가 방법
    ├── ingest.py           raw → processed 전체 파이프라인
    ├── probe.py            좌표계 / 그래프 위상 진단기
    └── krgis/crs.py        한국 좌표계 판별·안전 변환
```

## 시작

```bash
pip install -r requirements-etl.txt
python src/etl/ingest.py
```

11개 레이어가 `data/processed/`에 재생성되면 정상이다.
`data/raw/`는 git 제외라 별도로 받아야 한다 — `data/raw/README.md` 참조.
항공정사영상만 용량 때문에 빠져 있다(Phase 3-A까지 불필요).
넣을 때는 `python scripts/normalize_ortho.py <원본폴더> --apply` — `data/raw/README.md` 참조.

## 의존성

| 파일 | 범위 |
|---|---|
| `requirements-etl.txt` | **GIS 파이프라인만.** 버전 고정. 데이터 담당자는 이것만 |
| `pyproject.toml` | 전체 스택 (FastAPI, PostGIS, YOLO 포함) |

```bash
pip install -r requirements-etl.txt      # ETL만
pip install -e ".[dev]"                  # 전체 + ruff/pytest
```

스택이 바뀌면 `pyproject.toml` 한 곳만 고친다. devcontainer 리빌드로 전원에게 전파된다.

## 실행

```bash
python src/etl/ingest.py                  # 전체
python src/etl/ingest.py --only ngii_road # 개별
python src/etl/ingest.py --check          # 원본 존재·체크섬만

python src/etl/probe.py crs  data/raw/xxx.shp        # 실제 좌표계 역추정
python src/etl/probe.py topo data/processed/road_link.geojson  # 위상 검사
```

## 산출물 규칙

| 파일 | 좌표계 | 용도 |
|---|---|---|
| `*_5186.gpkg` | EPSG:5186 | **거리·면적·버퍼 계산은 무조건 이쪽** |
| `*.geojson` | EPSG:4326 | 웹 표출 전용 |

4326에서 `buffer(3)` 하면 단위가 '도'라 반경 330km 원이 나온다.

## 좌표계 지문 (동명동 126.9245E / 35.1490N)

미상 데이터의 좌표 한 점만 보면 어느 좌표계인지 바로 나온다.

| 좌표계 | X | Y | 쓰는 곳 |
|---|---:|---:|---|
| EPSG:4326 | 126.9 | 35.1 | GPS, GeoJSON |
| EPSG:5179 | 947,580 | 1,683,903 | 도로명주소, 수치지도 |
| **EPSG:5186** | 193,120 | 283,628 | **프로젝트 표준**, 노드링크, 정사영상 |
| EPSG:5187 | 10,861 | 285,598 | 동부원점(강원·경북·경남·부산) |
| EPSG:5181 | 193,120 | 183,628 | 카카오 |
| EPSG:5174 | 193,047 | 183,321 | 구 지적 |

**판별**: 3자리(126/35)→4326 · 7자리+7자리→5179 · Y 60만대→5186/5187 ·
Y 50만대→5181/5174 · X 8자리→3857

## 어긋남 사고의 크기

| 사고 | 오차 |
|---|---|
| 5186 → 5187로 정의 | 184 km |
| 5186 → 5181로 정의 | 100 km |
| **5174 → 5181로 정의** | **316 m** ★ 위험 |
| **5174를 proj4 문자열로 직접 정의 (towgs84 누락)** | **390 m** ★ 최다 원인 |

축척을 줄이면 맞아 보인다. **Bessel 계열(5174~5178)은 proj4 문자열을 손으로 쓰지 말고
반드시 EPSG 코드로 정의할 것.**

## define vs transform

```python
gdf.set_crs("EPSG:5179", allow_override=True)  # 정의: "이 숫자는 5179다". 좌표값 안 바뀜
gdf.to_crs("EPSG:5186")                        # 변환: 좌표값을 실제로 계산
```

`.prj`가 없는데 `to_crs()`부터 부르면 다 틀어진다. `ingest.py`가 이 순서를 강제한다.

## 다음 순서

1. juso.go.kr 전자지도 승인 (행정구역경계 + 건물) — **대기 중**
2. 정식 경계로 재클립
3. 노딩 → 세그먼트 수 확정 → 전 문서의 "222" 교체
4. 폭 산출 (수치지도 주 / 실폭도로 폴백 / 교차로 5m 제외)

**1번 없이 3~4번을 시작하지 말 것.** bbox 기준 숫자를 문서에 박으면 승인 후 전부 다시 고친다.
