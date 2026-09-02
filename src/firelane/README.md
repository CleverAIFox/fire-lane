# src/firelane — 데이터 파이프라인

파일별 역할은 루트 `README.md` 의 **구조** 절이 든다. 이 문서는 **대장에
데이터를 추가하는 방법**이 본체다.

## 실행 — 진입점은 하나다

```bash
uv run fire-lane                  # 전량. ingest → … → publish → 계약 → 지문
uv run fire-lane --check          # 실행 없이 상태만
uv run fire-lane --from segments  # 그 단계부터
uv run fire-lane --only publish
```

★ **`uv run` 을 빼면 `command not found` 다.** 진입점은 `.venv/bin/fire-lane`
에 설치되고 그 폴더는 PATH 에 없다.

★ **단계를 직접 부르지 않는다.** `python -m firelane.ingest` 는 돌기는 하나
`pipeline` 이 세우는 `FIRE_LANE_STAGE` 가 없어 계보가 빠진다.
`guards.warn_direct_call()` 이 그때 경고한다 — 막지는 않는다. 디버깅에는
필요하고, 정상 경로를 막으면 사람이 우회를 습관으로 만든다(MASTER §18-13).

    ingest → segments → streetlight → terrain → ortho → publish

상세는 `MASTER §14-2`. 게이트와 계층은 `MASTER §18` 이 정본이다.

## 새 데이터를 추가할 때

**코드를 고치지 않는다. `sources.yaml` 에 항목을 추가한다.**

```yaml
  새키:
    what: 한 줄 설명
    kind: shp_zip | shp_zip_multi | shp_dir | csv_points | csv_points_in_zip
        | dbf_in_zip | json_points | csv_table | csv_table_multi
        | raw_only
    scope: jngj-donggu           # 공간 범위. 전국이면 kr
    updated: '2026-08-09'        # ★ 데이터 갱신일이지 다운로드일이 아니다
    stem: safety_cctv_jngj       # 파일명 어간. ext 와 합쳐 실물을 찾는다
    ext: [csv]
    feeds: [data/processed/cctv_5186.gpkg]   # 무엇을 먹이나
    feeds_note: '[]'
    layer: XXX.shp               # zip 안의 레이어 (shp 계열만)
    crs_native: EPSG:5179        # ★ probe.py crs 로 검증한 실제값
    encoding: cp949 | utf-8
    x_col: 경도                  # csv 계열만
    y_col: 위도
    schema: {컬럼명: 뜻}         # 편입 후 inventory.py 가 채운다
    contract: {rows: 5002}       # 같음. 건수·컬럼 계약
    feeds_why: 왜 이것을 먹이나   # feeds 가 비어 있으면 사유를 여기 적는다
    note: 믿으면 안 되는 것
```

★ **`url` · `license` · `retrieved` 를 적지 않는다.** URL 은 자주 깨지고
`provider + scope` 면 다시 찾는다. 메타 항목의 정본은 **`sources.yaml`
머리말**이며 거기 다섯이 전부다 — `provider` `updated` `acquired`
`scope` `crs`.

★ 이 예시는 2026-09-01 에 실물 41개와 맞췄다. 그전까지 `desc` `file`
`crs` `url` `license` `retrieved` 를 들고 있었는데 **실제로 그 여섯을 쓰는
항목이 0건**이었고, 그 예시를 보고 대장 초안을 쓰면 어긋났다.
`tests/test_doc_fsck.py::test_ledger_schema_doc_matches_reality` 가 지킨다.

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
사고가 있었고, 그때 받아주기로 한 것이다. **새 대장 항목에는 쓰지 않는다.**
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

★ **이 규칙은 `raw` 전용이다.** 계층마다 `sources.yaml` 의 `layers.<계층>.naming`
이 정본이고, `landing` · `interim` · `field` · `processed` 는 `null`(규칙 없음)
이다. `norm` 은 별도 규칙을 갖는다.

## 규칙

1. **`data/raw`는 불변.** 어떤 코드도 여기에 쓰지 않는다.
2. **좌표계는 정의(`set_crs`) 후 변환(`to_crs`).** 순서 바뀌면 전부 어긋난다.
3. **거리·면적·버퍼는 `*_5186.gpkg`로.** 4326에서 `buffer(3)`은 반경 330km 원이다.
4. **실행 기록은 `data/processed/_manifest.json`에 자동 축적된다.** 원본 SHA-256 포함.
