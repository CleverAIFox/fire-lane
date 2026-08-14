# data/raw — 원본 보관 규칙

> 이 파일이 데이터 관리의 정본이다. **별도 문서를 만들지 않는다**(PLAN §13-8).
> 2026-08-13 전면 개정. 이전 판은 파일명과 용량이 실제와 어긋나 있었다.

---

## 0. 그라운드 룰 4개

### R1. raw 는 불변이다

어떤 스크립트도 `data/raw` 에 쓰지 않는다. 읽기만 한다.
파생물(`_unz_*`, 임시 추출본)이 raw 안에 생기면 그건 버그다. `.work/` 로 뺀다.

> 2026-08-13 에 `ngii1k.py` 가 zip 을 raw 옆에 풀어 `_unz_*` 8폴더 1,570파일을
> 만들어 놓은 것이 발견됐다. raw 파일 수가 40배로 보였다.

### R2. 재생성 가능성이 gitignore 의 근거다

`.gitignore` 로 산출물을 빼는 이유는 단 하나 — **한 명령으로 다시 만들 수 있어서**다.
재생성이 안 되는 파일을 ignore 하면 그 파일은 사실상 소실된다.

> `data/processed/*.gpkg` 를 "30초면 재생성된다"는 근거로 제외했는데
> `ngii1k_5186.gpkg` 만 그 전제가 깨져 있었다(`ingest.py` 에 핸들러 없음).
> 결과: 다른 기기에서 폭 주 소스 없이 파이프라인이 돌아 `clear 392 → 346`.
> **ignore 목록에 뭘 넣기 전에 `pipeline.py` 로 그게 재생성되는지 먼저 확인한다.**

### R3. 등록되지 않은 데이터는 없는 데이터다

`sources.yaml` 에 항목이 없으면 파이프라인이 모른다. raw 폴더에 있어도 없는 것이다.
새 데이터를 받으면 **파일을 옮기기 전에 `sources.yaml` 부터 쓴다.**

### R4. `feeds` 를 못 채우면 raw 에 둘 이유가 없다

`sources.yaml` 의 모든 항목은 `feeds`(어느 산출물의 입력인가)를 갖는다.
채울 수 없으면 `kind: raw_only` + `feeds: 미투입 — <언제 쓸지>` 로 명시한다.

> 이 규칙이 없어서 `juso_road_geom` 291MB(전자지도로 대체된 구 소스)가
> raw 에 남아 raw 를 327MB 로 보이게 했고, "2.2GB 인프라 문제"로 오인하게 만들었다.
> **문제는 데이터를 모은 데서 안 나오고 안 치운 데서 나온다.**

---

## 1. 계층과 git 정책

| 계층 | 위치 | git | 근거 |
|---|---|---|---|
| **raw** | `$FIRE_LANE_RAW` (저장소 밖) | ❌ | `sources.yaml` 의 `url` + `sha256` 으로 재취득 |
| **processed (중간)** | `data/processed/*.gpkg` `*.tif` | ❌ | `pipeline.py` 한 명령으로 재생성 ← **R2 로 매번 확인** |
| **processed (계약)** | `segments.geojson` `segments.schema.json` `_manifest.json` | ✅ | UI 담당이 raw 없이 작업해야 한다 |
| **web/data** | 타일·GeoJSON | ✅ | 브라우저 입력. CI 가 60MB 상한 감시 |
| **코드** | `src/etl/*` `sources.yaml` | ✅ | |

**심링크 금지.** `data/raw` 를 심링크로 걸었더니 git 이 추적했고 exFAT 에서
`git reset --hard` 시 원본 2.5GB 가 소실됐다(2026-08-11). 환경변수로만 지정한다.

```bash
export FIRE_LANE_RAW="/mnt/f/.../FIRE_LANE/data/raw"     # 리눅스
setx FIRE_LANE_RAW "D:\...\FIRE_LANE\data\raw"           # 윈도우
```

미설정 시 `<repo>/data/raw`.

---

## 2. 백업과 기기 간 이동 — 구분한다

```
백업     외장 SSD. 축소 전 전량. 소실 대비. 읽을 일 없다
이동     ✗ SSD 를 쓰지 않는다
```

**SSD 를 이동 수단으로 쓰면 단일 장애점이 된다.** GPU 학습 중이라 SSD 를 못 빼서
하루가 날아간 사례가 있다(2026-08-13).

이동은 **축소본을 각 기기에 복제**하는 것으로 대신한다. 재취득 가능한 데이터는
복제해도 되는 데이터다. 유일본처럼 다루니까 SSD 가 인질이 된 것이다.

동일성은 파일을 옮겨서가 아니라 **해시로** 확인한다.

```bash
python src/etl/ingest.py --check      # _manifest.json 의 source_sha256 대조
```

### 전국판을 들고 다니지 않는다

```
its_nodelink_kr    258MB → 광주 축소 시 약 11MB
sbiz_store_kr      337MB → 광주 축소 시 약 9.6MB
합계               645MB → 약 70MB
```

축소 후 파이프라인을 재실행해 산출물이 동일한 것을 확인하고 나서 교체한다.
전국 원본은 `sources.yaml` 의 `url` 로 언제든 다시 받는다.

---

## 3. 새 데이터 등록 절차

```
1. sources.yaml 에 항목 추가 (kind · file · crs · feeds · license · url)
2. 파일명 규칙에 맞춰 이름 변경  →  기관_주제_지역_날짜.확장자
3. $FIRE_LANE_RAW/<기관>/ 에 배치
4. python src/etl/ingest.py --only <key>
5. _manifest.json 에 features 수가 찍히는지 확인
6. 이 README 인벤토리 표에 한 줄 추가
```

**폴더명 = 기관 약칭.** `juso` `ngii` `its` `sbiz` `safety` `gjcity` `nsdi` `misc`

파일명은 `기관_주제_지역_날짜` 다. glob 패턴을 파일명에 맞추지, 파일명을 glob 에
맞추지 않는다.

> `streetlight` 의 glob 이 `*가로등현황*.csv` 였는데 실제 파일은 규칙대로
> `gjcity_streetlight_dongu_20240415.csv` 였다. 영원히 안 맞는 상태로 방치됐다.
> 게다가 `kind: csv_point` 가 핸들러 이름(`csv_points`)과 달라 두 겹으로 막혀 있었다.

### `kind` 목록 (`ingest.py`)

```
shp_zip · shp_zip_multi · ngii_1k · csv_points · csv_points_in_zip
dbf_in_zip · json_points · csv_table · raw_only
```

`sources.yaml` 에 이 목록 밖의 `kind` 를 쓰면 `unknown kind` 로 FAIL 한다.
**새 형식이면 핸들러를 먼저 추가하고 항목을 쓴다.**

---

## 4. 재현 검증

파이프라인이 재현된다는 것은 **다른 기기에서 같은 raw 로 같은 숫자가 나온다**는 뜻이다.
말이 아니라 이걸로 확인한다.

```bash
python src/etl/pipeline.py --check     # 각 단계 산출물 존재
python src/etl/pipeline.py             # 전량 재실행
```

`pipeline.py` 의 `EXPECT` 와 다르면 멈춘다.

```
ingest    ngii1k 3593 · ngii_road 3740 · road_link 1508 · road_rw 1957
          node_link 1366 · streetlight 1786
segments  1087 · clear 443 · needs_cv 191 · blocked 57 · unknown 396
```

**2026-08-13 검증 완료.** raw 부터 전량 재실행해 위 숫자와 지오메트리 1,087개가
완전히 일치했다. 유일한 차이는 `z`(고도)로, DEM 미투입 시 생기지 않는 선택
컬럼이며 `publish_web.py` 가 이미 그렇게 처리한다.

> `segments.geojson` 의 `sha` 는 파일 바이트 해시라 `z` 컬럼 유무만으로도 바뀐다.
> **값 동일성 검증에 쓰지 마라.** 기준선은 위 `EXPECT` 표다.

---

## 5. 인벤토리

`feeds` = 이 데이터가 없으면 못 나오는 산출물. 못 채우면 R4 위반이다.

### 파이프라인 투입

| 기관 | 파일 | 크기 | feeds |
|---|---|---:|---|
| juso | `juso_elctrnmap_jngj_20260711.zip` | 6.9MB | `road_link` `road_rw` `boundary_emd` `building` `building_entrance` |
| ngii | `ngii_1k/` 도엽 20장 | 19MB | **`ngii1k` ★ 폭 주 소스 (925/1085 구간)** |
| ngii | `ngii_basemap_gj0{37,38,47,48}.zip` | 15MB | `ngii_road` (폭 2순위) |
| ngii | `ngii_dem_gj35616_20251117.zip` | 0.3MB | `terrain` → `z` |
| its | `its_nodelink_kr_20260810.zip` | 258MB → 축소 필요 | `node_link` `node_point` `turn_restriction` (A*) |
| sbiz | `sbiz_store_kr_20260630.zip` | 337MB → 축소 필요 | `poi_store` (GRAY 사전확률 §8-4) |
| safety | `safety_cctv_jngj_20260630.csv` | 754KB | `cctv` → `cv_feasible` 판정 |
| safety | `safety_parking_enforce_dongu_20240108.csv` | 4.9MB | `enforcement` (빈도만. 시간대 오염 §3-9) |
| safety | `safety_firestation_kr_20240901.csv` | 166KB | `fire_station` (119안전센터 출발점) |
| safety | `safety_hydrant_point_kr_20260811.csv` | 14MB | `hydrant_point` (공개 31개, 5%) |
| safety | `safety_hydrant_summary_jngj_20251231.csv` | 259B | `hydrant_summary` |
| safety | `safety_fire_access_gj_dong_20250731.csv` | 2KB | `fire_access` — **폭의 유일한 외부 대조 수단** |
| gjcity | `gjcity_parking_dongu_20260811.csv` | 84KB | `parking` |
| streetlight | `gjcity_streetlight_dongu_20240415.csv` | 248KB | `streetlight` → `light_count` |

### raw_only — 파이프라인 미투입

| 파일 | feeds | 비고 |
|---|---|---|
| `juso_spotaddr_geom_jngj_20260801.zip` | 미투입 — STEP 4 관측점 랜드마크 | 동명동 26건. 폭·그래프·영상 기여 0 |
| `juso_spotaddr_ref_jngj_20260801.zip` | 미투입 — 동일 | 좌표 m급. 호모그래피 대응점 불가 |
| `ngii_ortho_gj0*.tif` (4장 1.3GB) | 미투입 — Phase 3-A 폭 전수검증 | 지오태그 없음. 복원 규칙 MASTER §10 |
| `nsdi_building_change_kr_20260806.zip` | 미투입 | 일변동분. 전체분 아님 |

### 치울 것

| 파일 | 사유 |
|---|---|
| `juso_road_geom_jngj_20260701.zip` (291MB) | 전자지도로 대체됨(2026-08-12). `misc/` 로 내린다 |
| `ngii_1k/*.xlsx` 20개 (8.8MB) | 도엽 속성 목록. 파서가 안 읽는다 |
| `ngii_1k/_unz_*` | R1 위반. 파생물이다 |

`.nda` 12개는 남긴다. 지금은 안 읽지만 도로경계 유형 필터에 쓸 여지가 있다.

---

## 6. 알려진 주의사항

| 대상 | 내용 |
|---|---|
| `juso` zip | 내부 `.dbf` 가 CP949. `.prj` 없음 → **EPSG:5179 로 강제 정의** |
| `juso` zip | 내부 한글 파일명이 CP437 로 깨짐. CP949 로 되돌려 매칭 |
| 사물주소 | `.prj` 없음(5179). 0건 유형 파일이 `"No Data"` 한 줄이라 파서가 죽는다 |
| `ngii_1k` | 2022년~ SHP / ~2020년 NGI 텍스트 혼재. GDAL 드라이버 없음 |
| `ngii_1k` | 같은 도엽이 여러 해로 오면 최신 채택. **연도는 `_YYYYMMDD` 에서 뽑는다** |
| `ngii_1k` | 다운로드 zip 을 추출본 옆에 두면 zip 이 우선 선택돼 **0건이 조용히 나온다** |
| `ngii` basemap | `.cpg` UTF-8, EPSG:5179 |
| 공공 CSV | 같은 데이터셋도 시점에 따라 인코딩이 바뀐다. `read_csv_any` 가 순차 시도 |
| 정사영상 | GeoTIFF 아님. `.tfw`·도곽좌표 없음. **EPSG:5186** (수치지도 5179와 다름) |

---

## 7. 라이선스

`juso` 전자지도와 사물주소는 **도로명주소법 시행령 제46조 심사 승인** 데이터다.
승인 당사자의 사용과 제3자 재배포는 다르다.

- 퍼블릭 버킷·공개 저장소에 올리지 않는다
- 클라우드로 옮길 경우 프라이빗 + 팀 내부 접근으로 한정한다
- 이관 전에 이용 조건을 확인한다

`ngii` 수치지형도·정사영상은 국토정보플랫폼 이용 조건을 따른다.
