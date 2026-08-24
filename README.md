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
정본은 `data/processed/segments.geojson`, 기대값은 `src/firelane/pipeline.py` 의 `EXPECT` 다.
셋이 어긋나면 산출물이 옳다.

```bash
uv run python tools/docnum_check.py     # 문서·EXPECT 가 산출물과 같은지
```

---

## 실행

```bash
uv sync
git config core.hooksPath .githooks   # 커밋 시점 방어. 클론 후 1회
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"   # 머신마다 다르다

python -m firelane.normalize_raw "$FIRE_LANE_DATA/landing" --dry-run
python -m firelane.contract
uv run fire-lane

uv run python tools/serve.py        # 캐시 없는 개발 서버
```

받자마자 한 번, 그리고 큰 변경 뒤에는 이것 하나면 된다.

```bash
bash tools/verify.sh          # 8단계 전부. 실패해도 끝까지 돌고 표로 보여준다
bash tools/verify.sh --fast   # 파이프라인 전량(4분) 생략
```

`uv pip install -e .` 은 치지 마라. `[build-system]` 이 있으므로 `uv sync` 가
editable 로 알아서 깐다 — 스크립트 첫 단계가 그것이다.

푸시 전에는 이것 하나면 된다.

```bash
uv run python tools/ship.py              # 검사만
uv run python tools/ship.py --fix --push # 정리 + 검사 + push
```

`verify.sh`(코드가 도는가)에 더해 **문서 4축 · 위생 · git 상태**까지 본다.
CI 가 지금 브랜치를 감시하는지도 확인하므로 검사 없이 머지되는 일이 없다.

머지하고 나면 로컬에 찌꺼기가 남는다. 그것도 한 명령이다.

```bash
uv run python tools/tidy.py          # 무엇이 지워질지만
uv run python tools/tidy.py --yes    # 실제로
```

죽은 upstream · 머지된 브랜치 · 일회성 패처 · 격리 산출물 · 캐시를 본다.
**데이터 계층은 건드리지 않는다** — `data/raw` · `norm` · `field` · `web/data`
는 `NEVER` 로 막혀 있고 규칙에 실수로 넣어도 안 지워진다.

**마지막 하나는 사람이 봐야 한다.** WebGL 렌더링은 스크립트가 못 본다.
지도가 실제로 그려지는지, 판정 색·표지판·미니맵·검색이 눈으로 멀쩡한지는
`tools/serve.py` 로 직접 확인한다.

`index.html` 을 더블클릭하면 안 된다. `file://` 에서는 `fetch()` 가 CORS 로 막힌다.

### 파이프라인

```
ingest → segments → streetlight → terrain → ortho → publish → 계약 테스트 → 기대값 대조
```

```bash
uv run fire-lane --check          # 실행 없이 상태만
uv run fire-lane --from segments  # 그 단계부터
uv run fire-lane --only publish
```

★ `uv run` 을 빼면 `command not found` 다. 진입점은 `.venv/bin/fire-lane` 에
설치되고 그 폴더는 PATH 에 없다. `uv sync` 가 editable 로 깔아주지만
**셸에 노출하지는 않는다** — 2026-08-23 에 이것 때문에 파이프라인이 안 돌았고,
그 상태로 `golden.py check` 를 돌려 **통과했다.** 옛 산출물을 옛 지문과
비교한 것이라 아무것도 증명하지 않는다. 가장 위험한 종류의 초록불이다.



전량 재실행 약 285초. **`processed` 를 백업하지 않는 근거가 이 시간이다.**
raw + 코드 + 대장이 있으면 결정론적으로 재생성된다.

**단계를 하나씩 손으로 치지 마라.** 순서가 중요하고 빠뜨리기 쉽다.

---

## 도구

```bash
uv run python tools/ship.py --fix --push   ★ 내보내기 전 단일 진입점
uv run python tools/tidy.py --yes          로컬 찌꺼기
uv run python tools/acquire.py             landing → raw 획득 게이트
```

`ship.py` 가 `verify.sh`(코드가 도는가)에 더해 **문서 4축 · 위생 · git 상태**
까지 본다. CI 가 지금 브랜치를 감시하는지도 확인하므로 검사 없이 머지되는
일이 없다.

### 대조 도구 — 아무것도 안 바꾼다

```bash
uv run python tools/width_fn.py       폭을 함수 w(s) 로 — min vs 통과폭
uv run python tools/jijeok_probe.py   연속지적도(세 번째 계보)로 폭 대조
uv run python tools/jijeok_review.py  갈리는 구간을 정사영상 위에서 판정
uv run python tools/lanes_probe.py    표준노드링크 차로수로 폭 하한 대조
uv run python tools/route_probe.py    소방차 통행 비용으로 경로 — 거리만 vs 차량
uv run python tools/clearance_probe.py  최대내접원 방식 (2026-08-22 기각)
```

읽고 표를 내거나 페이지를 만들 뿐이라 `golden` 지문에 영향이 없다.
**측정하고 대조한 뒤에 판정을 바꾼다** — `n=7` 로 방법 하나를 기각했다가
근거를 다시 쓴 것이 그 교훈이다(DECISIONS).

## 차량 제원

판정과 경로 비용의 기준 차량이다. `sources.yaml` 의 `vehicle_spec` 이 정본이고
**기본값을 두지 않는다** — 없으면 `seg/vehicle.py` 가 죽는다.

출처는 소방청 「소방장비 기본규격」 소방펌프차 **KFS-1-0073-2025-00 §3.3**
(2025-12-24 고시)이다. 원문 표기는 "이하"다.

```
구분   전장(m)    전폭(m)    전고(m)   물탱크(ℓ)
대형   8.5 이하   2.5 이하   3.4 이하   4,500 이상
중형   8.0 이하   2.5 이하   3.2 이하   2,800 이상   ← 현재 기준
소형   6.8 이하   2.2 이하   2.8 이하   1,200 이상
경형   5.2 이하   1.9 이하   2.8 이하     500 이상
```

★ **축거와 최소회전반경은 공식 규격에 없다.** KFS-1-0073 ·
KFS-1-0030(소형사다리차) · 2025년 MAS 차종별 제작규격 셋을 전수 확인했다.
내륜차 계산에 그 둘이 필요하므로 지금 값은 추정이며
`wheelbase_verified: false` 가 그 표시다. D-30 소방서 인터뷰에서 확정한다.

### 내륜차

회전 시 뒷바퀴가 앞바퀴보다 안쪽으로 도는 폭 차이다.

```
Δ = R − √(R² − L²)        R = 회전반경 · L = 축거

     R      내륜차    필요폭
   직선      0.00     3.00
     20      0.40     3.40
      8      1.07     4.07
      6      1.53     4.53   회전 불가
```

1차 근사 `L²/(2R)` 를 쓰지 않는다. R=8·L=4 에서 근사 1.000 대 정확 1.072 로
7cm 차이가 나고, 그것이 3.0m 임계 근처에서 판정을 가른다.

## 경로

119안전센터 2곳에서 모든 노드까지 **단일 출발 Dijkstra** 를 돌린다.
목적지가 다수이므로 A* 의 이점이 없다 — 휴리스틱으로 탐색을 줄이는 이득은
목적지가 하나일 때 나오고, 다수이면 목적지마다 다시 돌아야 한다.

★ 네비게이션 앱은 출발 1 → 도착 1 이므로 그쪽은 A* 가 맞다.
같은 `vehicle.edge_cost` 를 쓰므로 코드가 갈리지 않는다.

### 두 가지 경로가 있다

```
route_usage        weight="length"       회랑 산정용. 폭을 모른다
route_vehicle.csv  vehicle.edge_cost()   폭 · 내륜차 · 회전반경 반영
```

`access_corridor()` 는 **폭 산출보다 먼저** 돈다(`segments.py` 194줄 대
435줄). 그래서 거리만 쓸 수 있고, 그 결과가 `route_usage` 다.

★ 2026-08-24 실측 — `route_usage > 0` 인 579구간 중 `blocked` 가 41,
폭 3.0m 미만이 168이다. **이 값은 통행 가능성을 뜻하지 않는다.**
스키마도 "최단경로 사용횟수" 라고만 적는다.

폭이 나온 뒤 한 번 더 돌아 `route_vehicle.csv` 를 낸다. 순서를 바꾸지 않는
이유는 회랑 산정(표출 스코프)이 폭에 의존하게 되면 계보가 꼬이기 때문이다.

### 도달 가능성이 개별 판정과 다르다

```
통행 불가       416 / 1,101   구간 자체가 못 지나간다
도달 가능       687 (62%)     안전센터에서 막힌 길 없이 갈 수 있다
도달 불가       414 (38%)
```

**막힌 구간 하나가 뒤쪽 골목 여러 개를 통째로 끊는다.** `blocked 159` 는
구간의 성질이지 도달 가능성이 아니다. 폭 15m 대로라도 진입로가 막히면
소방차가 못 간다.

★ 막힌 엣지를 **그래프에서 뺀 뒤** Dijkstra 를 돌린다. 큰 비용을 주고
남겨두면 다른 길이 없을 때 그 엣지를 쓴다 — "막힌 길로라도 도달" 은
답이 아니다.

★ `reachable` 은 **양 끝 노드가 모두 도달 가능할 때만** 1 이다.
한쪽만 닿으면 그 구간에 들어갈 수 없다.

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
python -m firelane.contract       대장 선언 ↔ raw 실물 대조. ingest 앞에 선다
uv run python tools/scan_data.py        계층·명명·중복·격리 대상
python -m firelane.datalog check  대장 정합성
```

`contract.py` 가 보는 것 — 인코딩 · 컬럼 소실 · 건수 · zip 안 레이어 ·
**스코프 안 유효 건수(`scope_min`)**. 마지막 항목이 핵심이다.
2026-08-15 소스 교체 때 소화전이 파싱은 되고 스코프에서 전멸해
`OK 0건` 으로 통과한 적이 있다. 조용한 0건이 제일 나쁘다.

---

## 구조

```
sources.yaml              데이터 정본. contract 블록 포함
src/firelane/
  paths.py                경로 정본. FIRE_LANE_DATA 환경변수
  normalize_raw.py        landing → raw 명명규칙 배치
  contract.py             ★ 대장 ↔ 실물 계약 게이트
  pipeline.py             단일 진입점. Step 선언(reads/writes/mutates)
  lineage.py              ★ 계보. 단계별 입출력 지문 대조
  ingest.py               raw → processed
  ngii1k.py               V-WORLD 1:1,000 74도엽 → 레이어별 gpkg
  guards.py               방어 정본. 낡은 산출물 격리 · 공간 커버리지
  segments.py             조립부. 계산은 seg/ 가 한다
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
  docnum_check.py         문서 ↔ 산출물 숫자 대조 (있어야 할 값 · 없어야 할 값)
  wmax_audit.py           width_max_m 결손이 판정에 미치는 규모
  desk_check.py           정사영상 위에 구간·폭 렌더 (책상 대조)
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
  js/                     로직·레이어 (27개 모듈)   @AIMasterFox
    main.js               부트스트랩. 순서만
    data.js               ★ 데이터 접근 단일 지점
    layers/ icons/ ui/
  data/                   생성물. 손으로 고치지 않는다
```

**`raw` 를 저장소에 두지 않는다.** 심링크도 쓰지 않는다.
심링크를 git 이 추적했다가 원본 2GB 가 두 번 소실된 적이 있다(2026-08-11, 08-12).

---

## 지금 상태 — 2026-08-23

```
세그먼트     1,101   (동명동 416 + 119안전센터 접근 회랑)
판정        통행 가능 397 · 판정 보류 191 · 통행 불가 159 · 영상판정 불가 354
도달 가능    687 (62%)   119안전센터에서 막힌 길 없이 갈 수 있는 구간
기준        소방청 2025 골든타임 대책 + 2026-08-06 현장 답사 (통과 하한 3.0m)
데이터      대장 31종 · raw 32파일 · 2.61GB
전량 실행    165초 · sha d0325299403c2766
```

★ 판정 네 숫자는 2026-08-18 이후 **바뀌지 않았다.** 그 사이 버그 28건을
고치고 도구 6종을 붙였으나 산출물은 동일하다 — `golden` 지문이 그것을
매 실행 확인한다.

`영상판정 불가` 354 는 전부 CCTV 사각이다. 폭 산출 불가는 0 이다.
사유는 `no_cctv_band` · `no_cctv_thin` · `no_cctv_narrow` ·
`no_cctv_single` 넷으로 갈라 적는다(DECISIONS).

★ `통행 불가` 159 는 확정 개수가 아니라 **하한**이다. `width_max_m` 결손
  496건 중 도로대장 명목폭이 3.0m 이상이거나 없는 64건은 아직 판정되지
  않는다. 발표 자료에서 159 를 확정으로 쓰지 않는다.

**폭 값은 아직 미검증이다**(`width_verified: false`, 전건). 레이저 실측 후 바뀐다.
값은 바뀌어도 필드와 `verdict` 어휘는 안 바뀐다. 계약 테스트가 그것을 보장한다.

### 원본 재취득 (2026-08-17)

```
수치지형도   국토정보플랫폼 NGI 20도엽 (2020·2022)
           → V-WORLD SHP 74도엽 (2026-03)   vintage 6년 · 도엽 3.7배 · 도로명 채워짐
평면교차점   신규. A0080000 2,025개
           → XSEC_EXCL 5.0(근거 없는 반경)을 실제 형상으로 대체
연속수치지도  B030 국가기본공간정보 → B020 연속수치지도
           도로경계면 밀도가 줄어 폭 채택에서 ngii 가 117 → 1 로 빠지고
           silpok 폴백이 84 → 203 으로 늘었다. 버그가 아니라 제품 교체의 결과다
```

구 판정(1,102 / 386·210·62·444)은 원본이 소실돼 **재생성 불가**다. <!--stale-ok-->
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
1,087 노드접합 · 산출단위 병합 (8/13) <!--stale-ok-->
1,102 교차부 실제 폴리곤 반영 (8/14) <!--stale-ok-->
1,101 수치지형도 교체 + 북부 12도엽 보완 (8/18)   ← 현재 판정 단위
```

노딩 규칙이 바뀌면 `seg_id` 가 전부 밀린다. 외부 참조에는 `seg_uid` 를 쓴다.
