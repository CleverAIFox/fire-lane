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
    kind: shp_zip | shp_zip_multi | csv_points | csv_points_in_zip | dbf_in_zip | csv_table
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

`kind`가 여섯 종류로 모든 케이스를 덮는다. 새 형식이 나오면 그때만 `build()`에 분기를 추가한다.

## 파일 명명 규칙

`data/raw/`에 새 파일을 넣을 때는 반드시 이 형식이다.

```
{기관}_{데이터}_{범위}_{기준일}.{zip|csv}
예) juso_road_geom_jngj_20260701.zip
    safety_cctv_jngj_20260630.csv
```

한글·공백·괄호·대문자 금지, CSV는 UTF-8. 상세는 `data/raw/README.md`.

## 규칙

1. **`data/raw`는 불변.** 어떤 코드도 여기에 쓰지 않는다.
2. **좌표계는 정의(`set_crs`) 후 변환(`to_crs`).** 순서 바뀌면 전부 어긋난다.
3. **거리·면적·버퍼는 `*_5186.gpkg`로.** 4326에서 `buffer(3)`은 반경 330km 원이다.
4. **실행 기록은 `data/processed/_manifest.json`에 자동 축적된다.** 원본 SHA-256 포함.
