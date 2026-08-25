# src/firelane — 데이터 파이프라인

## 파일

| 파일 | 역할 |
|---|---|
| `ingest.py` | `data/raw` → `data/processed` 전체 변환. 유일한 진입점 |
| `probe.py` | 좌표계 역추정 / 그래프 위상 진단 |
| `krgis/crs.py` | 한국 좌표계 판별·안전 변환 유틸 |

## 실행

```bash
python -m firelane.ingest                  # 전체
python -m firelane.ingest --only ngii_road # 개별
python -m firelane.ingest --check          # 원본 존재·체크섬만
```

## 새 데이터를 추가할 때

**코드를 고치지 마라. `sources.yaml`에 항목을 추가한다.**

```yaml
  새키:
    desc: 한 줄 설명
    kind: shp_zip | shp_zip_multi | shp_dir | csv_points | csv_points_in_zip
        | dbf_in_zip | json_points | csv_table | csv_table_multi
        | raw_only
    file: 폴더/파일명.zip        # data/raw 기준 상대경로. 와일드카드 가능
    layer: XXX.shp               # zip 안의 레이어 (shp 계열만)
    crs: EPSG:5179               # ★ probe.py crs 로 검증한 실제값
    encoding: cp949 | utf-8
    x_col: 경도                  # csv 계열만
    y_col: 위도
    url: ...
    license: ...
    retrieved: 2026-08-09
```

### `kind` — 정본은 `ingest.py` 의 `build()` 다

| kind | 무엇 |
|---|---|
| `shp_zip` | zip 안 SHP 한 장 |
| `shp_zip_multi` | 도엽 여러 zip 을 병합 |
| `shp_dir` | 중첩 zip → 도엽 묶음. `ngii1k.py` 가 파싱한다 |
| `csv_points` | 위경도 컬럼이 있는 CSV |
| `csv_points_in_zip` | zip 안 대용량 CSV. 청크로 읽는다 |
| `dbf_in_zip` | 지오메트리 없는 DBF (회전제한) |
| `json_points` | 표준데이터 JSON. CSV 로 오다 바뀌는 경우 |
| `csv_table` | 좌표 없는 표. 그대로 복사 |
| `csv_table_multi` | 좌표 없는 표 여러 판. 이어붙인다. 컬럼이 다르면 FAIL · `_src` 에 원본 파일명 |
| `raw_only` | 읽지 않는다. 존재만 기록(SKIP) |

**새 형식이면 핸들러를 먼저 추가하고 대장을 쓴다.** 목록 밖의 `kind` 는
`unknown kind` 로 FAIL 한다.

★ 별칭이 넷 살아 있다 — `ngii1k` · `ngii_1k` 는 `shp_dir` 의 옛 이름이고
`csv_point` 는 `csv_points` 의 오타판이다. 2026-08-13 에 `kind: csv_point`
가 핸들러 이름(`csv_points`)과 달라 `streetlight` 가 두 겹으로 막혀 있던
사고가 있었고, 그때 받아주기로 한 것이다. **새 대장 항목에는 쓰지 마라.**
`tests/test_guards.py::test_ingest_kinds_are_documented` 가 이 표를 지킨다.

## 파일 명명 규칙

`data/raw/`에 새 파일을 넣을 때는 반드시 이 형식이다.

```
{기관}_{데이터}_{범위}_{기준일}.{zip|csv}
예) juso_road_geom_jngj_20260701.zip
    safety_cctv_jngj_20260630.csv
```

한글·공백·괄호·대문자 금지, CSV는 UTF-8.
제공기관 폴더와 계층 규칙은 `docs/MASTER.md` §18-1 · §18-2 가 정본이다.

## 규칙

1. **`data/raw`는 불변.** 어떤 코드도 여기에 쓰지 않는다.
2. **좌표계는 정의(`set_crs`) 후 변환(`to_crs`).** 순서 바뀌면 전부 어긋난다.
3. **거리·면적·버퍼는 `*_5186.gpkg`로.** 4326에서 `buffer(3)`은 반경 330km 원이다.
4. **실행 기록은 `data/processed/_manifest.json`에 자동 축적된다.** 원본 SHA-256 포함.
