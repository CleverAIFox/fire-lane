# Fire-Lane

동명동 소방차 진입 판정 시스템 · 전남광주통합특별시 동구

```
착수      2026-08-03
기간      4개월
대상      동명동 + 119안전센터 접근 회랑
```

골목 1,101구간의 실제 통행 가능 폭을 산출해 소방차가 지나갈 수 있는지 판정하고,
**판정할 수 없는 이유까지** 지도에 표시한다.

**지도** https://woongtopia.github.io/fire-lane/

---

## 문서는 셋뿐이다

문서 셋은 병렬 축이 아니라 **한 항목의 생애주기**다.

```
PLAN(미래)  →  도래  →  MASTER(현재)  →  회고  →  DECISIONS(과거)
```

| 문서 | 시제 | 담는 것 |
|---|---|---|
| [`docs/PLAN.md`](docs/PLAN.md) | 미래 | 남은 일 · 미결정 · 담당 공백 |
| [`docs/MASTER.md`](docs/MASTER.md) | 현재 | 판정 결과 · 데이터 · 용어 · UI 인수인계 · 협업 |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 과거 | 왜 그렇게 됐나 (append-only) |
| `docs/기획서_Fire-Lane.docx` | — | 대외 제출용 |

**한 항목은 한 문서에만 산다.** 두 곳에 있으면 한쪽만 고치는 날이 온다.
남은 일의 정본은 `PLAN §1` 하나다.

> ### 셋에서 넷이 된 이유 (2026-08-18)
>
> 이 절은 원래 "문서는 셋뿐이다" 였고 `DECISIONS.md` 는 그 규칙을 어기고
> 생겼다. 어긴 것을 인정하고 규칙을 고친다.
>
> 08-17~18 에 `tools/` 로 일회성 패처 9개가 들어왔다. 코드로는 전부 죽었지만
> **docstring 이 사고 원인의 유일한 기록**이었다. MASTER 는 3,100줄이라
> 이력 226줄을 더 넣으면 아무도 안 읽는다. PLAN 이 MASTER 에서 갈라진 것과
> 같은 논리다 — **시제가 다르면 문서가 다르다.**
>
> **다섯 번째는 만들지 않는다.** 과거·현재·미래 세 시제가 다 찼다.
> `test_reproducibility.py::test_no_fifth_doc` 이 막는다.

`sources.yaml` 은 데이터 정본이다. 기계가 읽으므로 손으로 고칠 때 주의할 것.

**문서를 더 만들지 않는다.** 흩어지면 아무도 최신을 모른다.
완료된 일은 PLAN 에서 지우고 MASTER 에 결과를 쓴다.

### `D-XX` 는 날짜가 아니다

**미결정 항목 번호(Decision)** 다. 2026-08-07 「미결정 사항 정리」에서 왔다.
MASTER §10-0 에 대응표가 있다. 새 D 번호는 만들지 않는다.

### 숫자의 정본은 문서가 아니다

문서에 적힌 구간 수·판정 수는 **파이프라인 산출물의 사본**이다.
정본은 `data/processed/segments.geojson`, 기대값은 `src/etl/pipeline.py` 의 `EXPECT` 다.
셋이 어긋나면 산출물이 옳다.

```bash
uv run python tools/docnum_check.py     # 문서·EXPECT 가 산출물과 같은지
```

---

## 실행

```bash
uv sync
export FIRE_LANE_DATA="/mnt/ssd/인공_지능_사관학교/파이널_프로젝트_Fire_Lane/fire-lane-data"

uv run python src/etl/normalize_raw.py "$FIRE_LANE_DATA/landing" --dry-run
uv run python src/etl/contract.py
uv run python src/etl/pipeline.py

cd web && uv run python -m http.server 8000
```

`index.html` 을 더블클릭하면 안 된다. `file://` 에서는 `fetch()` 가 CORS 로 막힌다.

### 파이프라인

```
ingest → segments → streetlight → terrain → ortho → publish → 계약 테스트 → 기대값 대조
```

```bash
uv run python src/etl/pipeline.py --check          # 실행 없이 상태만
uv run python src/etl/pipeline.py --from segments  # 그 단계부터
uv run python src/etl/pipeline.py --only publish
```

전량 재실행 약 285초. **`processed` 를 백업하지 않는 근거가 이 시간이다.**
raw + 코드 + 대장이 있으면 결정론적으로 재생성된다.

**단계를 하나씩 손으로 치지 마라.** 순서가 중요하고 빠뜨리기 쉽다.

---

## 데이터 계층

```
landing      SSD/landing/     다운로드 원본. 규칙 없음. ★ 백업 제외
raw          SSD/raw/         30개 · 2.59GB · 제공기관 8폴더. 절대 수정 안 함
norm         파일명·인코딩·확장자만 통일. 값은 안 바꾼다
field        실측 원자료. ★ 재생성 불가. raw 와 같은 등급
_quarantine  대장에 없는 파일. 삭제하지 않고 격리
processed    저장소 안. 백업도 커밋도 하지 않는다
data/baseline  ★ 예외. 원본이 소실돼 재생성 불가가 된 산출물만 봉인
```

제공기관 폴더 — `juso` `its` `ngii` `vworld` `safety` `gjcity` `sbiz` `eais`.
**같은 수치지형도라도 원천이 다르면 폴더가 다르다.**

### 게이트

```
uv run python src/etl/contract.py       대장 선언 ↔ raw 실물 대조. ingest 앞에 선다
uv run python tools/scan_data.py        계층·명명·중복·격리 대상
uv run python src/etl/datalog.py check  대장 정합성
```

`contract.py` 가 보는 것 — 인코딩 · 컬럼 소실 · 건수 · zip 안 레이어 ·
**스코프 안 유효 건수(`scope_min`)**. 마지막 항목이 핵심이다.
2026-08-15 소스 교체 때 소화전이 파싱은 되고 스코프에서 전멸해
`OK 0건` 으로 통과한 적이 있다. 조용한 0건이 제일 나쁘다.

---

## 구조

```
sources.yaml              데이터 정본. contract 블록 포함
src/etl/
  paths.py                경로 정본. FIRE_LANE_DATA 환경변수
  normalize_raw.py        landing → raw 명명규칙 배치
  contract.py             ★ 대장 ↔ 실물 계약 게이트
  pipeline.py             단일 진입점. EXPECT 기대값
  ingest.py               raw → processed
  ngii1k.py               V-WORLD 1:1,000 74도엽 → 레이어별 gpkg
  guards.py               ★ 방어 정본. 계보 · 낡은 산출물 격리 · 공간 커버리지
  segments.py             조립부 429줄. 계산은 seg/ 가 한다
  seg/
    params.py             임계값 정본. web/config.js 는 표시용 사본
    graph.py              노딩 · 최대성분 · 접근 회랑
    width.py              폭 산출 (WidthEngine) — ngii1k 1014 · silpok 84
    geom.py               verdict · _seal · _join · _dirv (폐포 없는 순수 함수)
    roadname.py           도로명 되붙이기 (RoadNameIndex)
    report.py             소방서 대조 · 진단 · 산출물 기록
  streetlight.py          가로등 지점 단위 집계
  terrain.py · ortho.py   DEM · 정사영상 타일
  publish_web.py          → web/data
  datalog.py              대장 정합성 · 계보 · 영향분석 · 백업 검증
tools/
  baseline.py             판정 산출물 봉인 · 실행 간 전이 대조
  golden.py               ★ 리팩 전후 산출물 동일 증명. baseline 과 반대 용도
  scan_data.py            데이터 레이크 구조 점검
  docnum_check.py         문서 ↔ 산출물 숫자 대조
     ※ 날짜 붙은 일회성 스크립트는 두지 않는다(§18-5 R8). CI 가 막는다.
tests/
  test_contract.py        GIS ↔ UI 경계 19종
  test_guards.py          계보 2층 · 격리 · 커버리지
  test_seg_*.py           verdict · RoadNameIndex · WidthEngine 단위
  test_static.py          정의되지 않은 이름 (실패 경로의 NameError)
  test_reproducibility.py §18-5 규약 강제 · 문서 ↔ 코드 동기화
web/
  index.html              뼈대                      공동
  style.css               색·간격·타이포             @marscoolcat
  config.js               색상표·임계값·마커·카메라   공동
  app.js                  로직·레이어               @AIMasterFox
  data/                   생성물. 손으로 고치지 말 것
```

**`raw` 를 저장소에 두지 않는다.** 심링크도 쓰지 않는다.
심링크를 git 이 추적했다가 원본 2GB 가 두 번 소실된 적이 있다(2026-08-11, 08-12).

---

## 지금 상태 — 2026-08-17

```
세그먼트     1,101   (동명동 416 + 119안전센터 접근 회랑)
판정        통행 가능 400 · 판정 보류 209 · 통행 불가 63 · 영상판정 불가 429
기준        소방청 2025 골든타임 대책 + 2026-08-06 현장 답사 (통과 하한 3.0m)
데이터      raw 30종 · 2.59GB
```

`영상판정 불가` 429 는 전부 `no_cctv` 다. 폭 산출 불가는 0 이다.

**폭 값은 아직 미검증이다**(`width_verified: false`, 전건). 레이저 실측 후 바뀐다.
값은 바뀌어도 필드와 `verdict` 어휘는 안 바뀐다. 계약 테스트가 그것을 보장한다.

### 2026-08-17 원본 전량 재취득

```
수치지형도   국토정보플랫폼 NGI 20도엽 (2020·2022)
           → V-WORLD SHP 74도엽 (2026-03)   vintage 6년 · 도엽 3.7배 · 도로명 채워짐
평면교차점   신규. A0080000 2,025개
           → XSEC_EXCL 5.0(근거 없는 반경)을 실제 형상으로 대체
연속수치지도  B030 국가기본공간정보 → B020 연속수치지도
           도로경계면 밀도가 줄어 폭 채택에서 ngii 가 117 → 1 로 빠지고
           silpok 폴백이 84 → 203 으로 늘었다. 버그가 아니라 제품 교체의 결과다
```

구 판정(1,102 / 386·210·62·444)은 원본이 소실돼 **재생성 불가**다. <!--stale-ok--> <!--stale-ok-->
`data/baseline/20260814-ngii-ngi20/` 에 봉인돼 있다.

```bash
uv run python tools/baseline.py diff 20260814-ngii-ngi20
```

`seg_uid` 유지율 99.1% · 판정이 바뀐 구간 27 / 1,101 · 총연장 48,580m 동일.

취득 주의 — **행정구역 단위 다운로드는 스코프를 보장하지 않는다.**
V-WORLD 동구 SHP 판(74도엽)이 1:50,000 경계에 걸친 도엽 12장을 흘려
스코프의 69%가 도로경계 폴리곤 밖이었다. 북·남·서구 상품도 그 띠를
비껴간다. 같은 상품의 NGI 포맷판(143도엽)으로 메웠다.
취득 후 반드시 스코프 bbox 와 교차 검증할 것.

### 구간 수는 고정값이 아니다

```
641   동명동만 노딩 (8/11)
1,266 접근 회랑 포함 (8/11)
1,087 노드접합 · 산출단위 병합 (8/13) <!--stale-ok--> <!--stale-ok-->
1,102 교차부 실제 폴리곤 반영 (8/14) <!--stale-ok--> <!--stale-ok-->
1,101 수치지형도 교체 + 북부 12도엽 보완 (8/18)   ← 현재 판정 단위
```

노딩 규칙이 바뀌면 `seg_id` 가 전부 밀린다. 외부 참조에는 `seg_uid` 를 쓴다.
