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

## 문서는 넷이다

문서 넷은 병렬 축이 아니라 **한 항목의 생애주기**다.

```
PLAN(미래)  →  도래  →  MASTER(현재)  →  회고  →  DECISIONS(과거)
```

| 문서 | 시제 | 담는 것 |
|---|---|---|
| [`docs/PLAN.md`](docs/PLAN.md) | 미래 | 남은 일 · 미결정 · 담당 공백 |
| [`docs/MASTER.md`](docs/MASTER.md) | 현재 | 판정 · 데이터 · 용어 · UI 계약 · 운영 |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 과거 | 왜 그렇게 됐나 (append-only) |
| `docs/proposal.docx` | — | 대외 제출용. 시제 규칙 밖 |

**한 항목은 한 문서에만 산다.** 두 곳에 있으면 한쪽만 고치는 날이 온다.
남은 일의 정본은 `PLAN §1` 하나다.

**다섯 번째는 만들지 않는다.** 과거·현재·미래 세 시제가 다 찼다.
새 문서를 만들고 싶으면 그것은 셋 중 하나의 절이다.
`tests/test_reproducibility.py::test_no_fifth_doc` 이 저장소 전체를 보고 막는다.

`sources.yaml` 은 데이터 정본이다. 기계가 읽으므로 손으로 고칠 때 주의할 것.

### 문서에도 검사가 붙어 있다

```bash
uv run python tools/docnum_check.py     # 문서 숫자 ↔ 산출물 · 필드표 대조
uv run python -m pytest tests/test_doc_style.py tests/test_reproducibility.py -q
```

문체·절 번호·어휘·생애주기·죽은 경로를 전부 코드가 본다.
**규약을 새로 적을 때는 강제자를 같이 만든다**(MASTER §17).

★ 강제자를 만들 때는 **그 강제자 자신의 목록 · 범위 · 형식 · 환경**을
실물과 대조한다(`DECISIONS §114-7`). 면제 목록에는 역방향을, 루트 기준
순회에는 형제 확인을, 형식 의존 검색에는 형식별 판독을 함께 붙이고,
참조하는 파일이 CI 에도 있는지 본다 — gitignore 대상이면 로컬에서만
통과하는 검사가 된다.

### `D-XX` 는 날짜가 아니다

**미결정 항목 번호(Decision)** 다. 2026-08-07 「미결정 사항 정리」에서 왔고
`MASTER §10-0` 에 대응표가 있다. 새 D 번호는 만들지 않는다.

### 숫자의 정본은 문서가 아니다

문서에 적힌 구간 수·판정 수는 **파이프라인 산출물의 사본**이다. 정본은
`data/processed/segments.geojson`, 기대값은 `data/golden/segments.fingerprint.json`
이다. 셋이 어긋나면 산출물이 옳다.

---

## 실행

```bash
uv sync
git config core.hooksPath .githooks   # 커밋 시점 방어. 클론 후 1회
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"   # 머신마다 다르다

uv run python -m firelane.normalize_raw "$FIRE_LANE_DATA/landing" --dry-run
uv run python -m firelane.contract
uv run fire-lane

uv run python tools/serve.py        # 캐시 없는 개발 서버
```

`uv pip install -e .` 은 쓰지 않는다. `[build-system]` 이 있으므로 `uv sync` 가
editable 로 알아서 깐다 — 검사 스크립트의 첫 단계가 그것이다.

받자마자 한 번, 그리고 큰 변경 뒤에는 이것 하나면 된다.

```bash
bash tools/verify.sh          # 전부. 실패해도 끝까지 돌고 표로 보여준다
bash tools/verify.sh --fast   # 파이프라인 전량 생략
```

푸시 전에는 이것 하나면 된다.

```bash
uv run python tools/ship.py              # 검사만
uv run python tools/ship.py --fix --push # 정리 + 검사 + push
```

```
verify.sh   코드가 도는가 — pytest · ruff · 파이프라인 · JS · 문서 숫자
ship.py     내보내도 되는가 — 위 + 문서 4축 + 위생 + git 상태
```

`ship.py` 가 `verify.sh` 를 부른다. 셋(`docnum_check` · `tidy` · `golden`)은
양쪽에서 도는데, `ship.py` 쪽은 문서 4축·git 상태와 묶어 판정하므로 남긴다.
CI 가 지금 브랜치를 감시하는지도 확인하므로 검사 없이 머지되는 일이 없다.

머지하고 나면 로컬에 찌꺼기가 남는다. 그것도 한 명령이다.

```bash
uv run python tools/tidy.py          # 무엇이 지워질지만
uv run python tools/tidy.py --yes    # 실제로
```

죽은 upstream · 머지된 브랜치 · 백업 폴더 · 캐시를 본다.
**데이터 계층은 건드리지 않는다** — `data/raw` · `norm` · `field` · `web/data`
는 `NEVER` 로 막혀 있고 규칙에 실수로 넣어도 안 지워진다.

**마지막 하나는 사람이 봐야 한다.** WebGL 렌더링은 스크립트가 못 본다.
지도가 실제로 그려지는지, 판정 색·표지판·미니맵·검색이 눈으로 멀쩡한지는
`tools/serve.py` 로 직접 확인한다.

`index.html` 을 더블클릭하면 안 된다. `file://` 에서는 `fetch()` 가 CORS 로 막힌다.

### 파이프라인

```
ingest → segments → streetlight → terrain → ortho → publish → 계약 테스트 → 지문 대조
```

```bash
uv run fire-lane --check          # 실행 없이 상태만
uv run fire-lane --from segments  # 그 단계부터
uv run fire-lane --only publish
```

★ `uv run` 을 빼면 `command not found` 다. 진입점은 `.venv/bin/fire-lane` 에
설치되고 그 폴더는 PATH 에 없다. `uv sync` 가 editable 로 깔아주지만
**셸에 노출하지는 않는다** — 이것 때문에 파이프라인이 안 돌았고, 그 상태로
`golden.py check` 를 돌려 **통과했다.** 옛 산출물을 옛 지문과 비교한 것이라
아무것도 증명하지 않는다. 가장 위험한 종류의 초록불이다.

전량 재실행 약 285초. **`processed` 를 백업하지 않는 근거가 이 시간이다.**
raw + 코드 + 대장이 있으면 결정론적으로 재생성된다.

**단계를 하나씩 손으로 치지 않는다.** 순서가 중요하고 빠뜨리기 쉽다.

---

## 도구

```bash
uv run python tools/ship.py --fix --push   ★ 내보내기 전 단일 진입점
uv run python tools/tidy.py --yes          로컬 찌꺼기
uv run python tools/pull_data.py --yes     ★ Downloads → norm 한 명령 (아래 참조)
uv run python tools/acquire.py             landing → raw 획득 게이트
uv run python tools/scan_data.py           데이터 레이크 구조 점검
uv run python tools/baseline.py            판정 산출물 봉인 · 실행 간 전이 대조
uv run python tools/golden.py              리팩 전후 산출물 동일 증명
```

### 대조 도구 — 아무것도 안 바꾼다

```bash
uv run python tools/width_fn.py         폭을 함수 w(s) 로 — min 대 통과폭
uv run python tools/jijeok_probe.py     연속지적도(세 번째 계보)로 폭 대조
uv run python tools/jijeok_review.py    갈리는 구간을 정사영상 위에서 판정
uv run python tools/lanes_probe.py      표준노드링크 차로수로 폭 하한 대조
uv run python tools/route_probe.py      소방차 통행 비용으로 경로 — 거리만 대 차량
uv run python tools/clearance_probe.py  최대내접원 방식 (2026-08-22 기각)
uv run python tools/desk_check.py       정사영상 위에 구간·폭 렌더 (책상 대조)
uv run python tools/wmax_audit.py       width_max_m 결손이 판정에 미치는 규모
```

읽고 표를 내거나 페이지를 만들 뿐이라 `golden` 지문에 영향이 없다.
**측정하고 대조한 뒤에 판정을 바꾼다** — `n=7` 로 방법 하나를 기각했다가
근거를 다시 쓴 것이 그 교훈이다(DECISIONS).

---

## 판정의 뼈대

```
TRUCK = 3.0     차량 전폭 2.5 + 미러·조향 여유 0.5
PARK  = 2.0     주차 1대 노면 점유
통행 불가   최대 폭(벽~벽) < 3.0
통행 가능   최소 폭 >= 3.0 + 2 x 2.0 = 7.0      양쪽 주차를 가정한다
```

근거는 소방청 「2025 화재현장 골든타임 확보 종합대책」이고, 기준 차량 제원은
소방청 「소방장비 기본규격」 소방펌프차 KFS-1-0073-2025-00 §3.3 이다.
임계값 정본은 `src/firelane/seg/params.py`, 차량 제원 정본은 `sources.yaml` 의
`vehicle_spec` 이다. 상세는 `MASTER §2-2` · `§3-13`.

★ **축거와 최소회전반경은 공식 규격에 없다.** 내륜차 계산에 그 둘이 필요하므로
지금 값은 추정이며 `wheelbase_verified: false` 가 그 표시다.

### 경로가 둘인 이유

```
route_usage        weight="length"       회랑 산정용. 폭을 모른다
route_vehicle.csv  vehicle.edge_cost()   폭 · 내륜차 · 회전반경 반영
```

`access_corridor()` 는 폭 산출보다 먼저 돌기 때문에 거리만 쓸 수 있다.
★ 그래서 **`route_usage` 는 통행 가능성을 뜻하지 않는다** — 0 초과인 579구간
중 통과 불가가 41, 폭 3.0m 미만이 168이다.

### 도달 가능성은 개별 판정과 다르다

```
차량 비용 통행 불가   416 / 1,101   폭 · 내륜차 · 회전반경까지 넣으면 못 지나간다
도달 가능            687 (62%)     안전센터에서 막힌 길 없이 갈 수 있다
도달 불가            414 (38%)
```

**막힌 구간 하나가 뒤쪽 골목 여러 개를 통째로 끊는다.** 폭 15m 대로라도
진입로가 막히면 소방차가 못 간다.

★ 416 은 지도의 빨강(`verdict` 159)과 **다른 값이다.** 산출 경로가 다르고
판정에도 반영되지 않는다. 셋의 구분은 `MASTER §3-9` 가 든다.

---

## 데이터 계층

```
landing      SSD/landing/     다운로드 원본. 규칙 없음. ★ 백업 제외
raw          SSD/raw/         제공기관 10폴더. 절대 수정 안 함
norm         파일명·인코딩·확장자만 통일. 값은 안 바꾼다. 텍스트 14종 이관 완료
interim      탐색·대조 산출물. 대장에 없고 지워도 된다
processed    저장소 안. 4개만 커밋하고 나머지는 재생성
field        실측 원자료. ★ 재생성 불가. raw 와 같은 등급
_quarantine  대장에 없는 파일. 삭제하지 않고 격리
web/data     표출용. 커밋한다. 40MB 상한
data/baseline  ★ 예외. 원본이 소실돼 재생성 불가가 된 산출물만 봉인
```

제공기관 폴더 — `juso` `its` `ngii` `vworld` `safety` `gjcity` `sbiz` `eais` `nsdi` `nfa`.
정본은 `sources.yaml` 의 `layers.raw.providers` 이고 `firelane.providers` 가 읽는다.
**같은 수치지형도라도 원천이 다르면 폴더가 다르다.**

계층 선언의 정본은 `sources.yaml` 의 `layers` 블록이고 경로 해석은
`src/firelane/paths.py` 다. 둘이 어긋나면 `datalog fsck` 가 잡는다.

### 게이트

```bash
uv run python -m firelane.contract        대장 선언 ↔ raw 실물. ingest 앞에 선다
uv run python -m firelane.datalog check   대장 정합성
uv run python -m firelane.datalog fsck    계층 선언 ↔ 실물
```

획득은 여덟 단계인데 **한때 명령이 넷이었다.** 그중 `--prune-landing` 은 `--verify`
없이도 돈다 — 편입이 성공했다는 확인 없이 원본을 지운다. 그것이 소실이다.

```bash
uv run python tools/pull_data.py            관측만
uv run python tools/pull_data.py --yes       이관 → 편입 → 검증 → 사본삭제
                                             → 격리 → 판정 → norm 이관 → 정합
uv run python tools/pull_data.py --yes --all 위 + 파이프라인 + golden
```

★ **삭제는 검증에 매달려 있다.** `③ verify` 가 0 이 아니면 `④` 는 실행되지
않고 landing 원본이 그대로 남는다. 순서를 주석이 아니라 자료구조로 들고 있고
`tests/test_intake_rules.py` 의 `test_prune_needs_verify` 외 다섯이 그것을 강제한다 —
게이트를 뚫는 · None 을 0 으로 읽는 · 통과 경로를 막는 세 방향 전부 본다.

단계별로 손으로 치고 싶으면 `intake.py` · `acquire.py` 를 직접 쓴다.
pull_data 는 그 둘을 부를 뿐 판정을 다시 쓰지 않는다.

`contract.py` 가 보는 것 — 인코딩 · 컬럼 소실 · 건수 · zip 안 레이어 ·
**스코프 안 유효 건수(`scope_min`)**. 마지막 항목이 핵심이다. 소스 교체 때
소화전이 파싱은 되고 스코프에서 전멸해 `OK 0건` 으로 통과한 적이 있다.
조용한 0건이 제일 나쁘다.

**`raw` 를 저장소에 두지 않는다.** 심링크도 쓰지 않는다 — 심링크를 git 이
추적했다가 원본 수 GB 가 두 번 소실된 적이 있다.

---

## 구조

```
sources.yaml              데이터 정본. layers · datasets · outputs · retired
src/contracts/            ★ 파트 간 유일한 접점. 세 파트가 이것만 import 한다
  vision.py               영상판정 인터페이스 (MASTER §19 의 실행 가능한 사본)
src/firelane/
  paths.py                경로 정본. FIRE_LANE_DATA 환경변수
  layers.py               계층 선언과 경로를 이름으로 묶는다
  normalize_raw.py        landing → raw 명명규칙 배치
  contract.py             ★ 대장 ↔ 실물 계약 게이트
  pipeline.py             단일 진입점. Step 선언(reads/writes/mutates)
  lineage.py              ★ 계보. 단계별 입출력 지문 대조
  ingest.py               raw → processed
  ngii1k.py               수치지형도 도엽 → 레이어별 gpkg
  ngi.py                  NGI/NDA 리더
  guards.py               방어 정본. 낡은 산출물 격리 · 공간 커버리지
  segments.py             조립부. 계산은 seg/ 가 한다
  seg/
    params.py             임계값 정본. web/config.js 는 표시용 사본
    graph.py              노딩 · 최대성분 · 접근 회랑
    width.py              폭 산출 (WidthEngine)
    geom.py               verdict · _seal · _join · _dirv (폐포 없는 순수 함수)
    roadname.py           도로명 되붙이기 (RoadNameIndex)
    basisno.py            기초구간 → seg_label
    vehicle.py            차량 제원 · 엣지 비용
    report.py             소방서 대조 · 진단 · 산출물 기록
  streetlight.py          가로등 지점 단위 집계
  terrain.py              공개DEM → Terrain-RGB 타일
  ortho.py                항공정사영상 → 배경 타일
  publish_web.py          → web/data
  webmanifest.py          web/data 계보. publish 가 직접 쓴다
  datalog.py              대장 정합성 · 계보 · 영향분석 · 백업 검증
  inventory.py            원본 레이어·속성 인벤토리 → sources.yaml
  sample_design.py        실측 표본 설계. 시드 고정
  segkey.py               seg_uid + 관측점 방위각
  probe.py                좌표계 역추정 · 그래프 위상 진단
  quiet_gdal.py           GDAL 잡음 억제
  krgis/crs.py            한국 좌표계 판별 · 안전 변환
tools/
  ship.py                 ★ 내보내기 전 단일 진입점
  verify.sh               코드가 도는가 — 일괄 검증
  tidy.py                 머지 후 로컬 찌꺼기
  acquire.py              landing → raw 획득 게이트 · sha 대조
  baseline.py             판정 산출물 봉인 · 실행 간 전이 대조
  golden.py               ★ 리팩 전후 산출물 동일 증명. baseline 과 반대 용도
  scan_data.py            데이터 레이크 구조 점검. §7 이 레이크 **밖**도 본다
  docnum_check.py         문서 ↔ 산출물 숫자 · 필드표 대조
  commit_policy.py        산출물 · 일회성 스크립트 · 비밀값 차단
  encoding_check.py       인코딩 · 개행
  web_manifest.py         web/data 계보 검사
  owned_paths.py          ★ CODEOWNERS 를 소유권·검사강도의 정본으로 읽는다
  pr_body_check.py        PR 본문이 템플릿을 실제로 채웠는가
  docx_check.py           기획서 ↔ 산출물 숫자·폐기 용어 대조
  docx_fix.py             기획서 낡은 숫자·용어 자동 교정 (--write)
  doctor.py               ★ 전 계층 진단 한 명령 — 정체·무결성·백업·할 일
  intake.py               Downloads → landing 게이트 · 대장 미매칭 차단
  pull_data.py            ★ 반입 입구. 여덟 단계. 삭제는 검증에 매달려 있다
  triage.py               받은 더미를 분류한다
  doc_fsck.py             문서끼리 어긋난 데가 있는가 (여덟)
  corner_probe.py         코너 꺾임각·반경 — 회전 가능성 대조
  migrate_names.py        raw 개명 백필 — 실물·sha대장·대장을 원자적으로
  refcheck.py             선언이 가리키는 것이 실재하는가 · --gc
  treecheck.py            ★ 전수 스캔 — 항목이 아니라 트리에서 출발한다
  ledger_stem.py          대장 stem 이관 · 무손실 증명
  ledger_fields.py        대장 별칭 필드 통합
  ledger_schema.py        실물에서 스키마 추출 · --check 드리프트
  render_workflow.py      MASTER §12 → web/workflow.html 자동 생성 (CI 가 배포 때 부른다)
  stage_pages.py          ★ 배포 준비 한 곳 — docs/proposal.docx → web/
  render_figures.py       ★ 정본 → docs/figures/*.svg · --check 로 낡음 대조
  release_brief.py        ★ 이 PR 이 무엇을 흡수하나 — 판정·계보·대장·계약
  ruleset_check.py        GitHub 룰셋 ↔ 문서 방침 대조 (사람이 주기적으로)
  ledger_feeds.py         feeds 산문 → 소비자 리스트
  serve.py                캐시 없는 개발 서버
  wmax_audit.py           width_max_m 결손이 판정에 미치는 규모
  desk_check.py           정사영상 위에 구간·폭 렌더
  docpatch.py             문서 절 단위 멱등 교체 · 표 행 추가
  js_graph_check.mjs      ES 모듈 의존 그래프 · 순환 참조
  web_boot_check.mjs      UI 부팅 경로 점검
     ※ 날짜 붙은 일회성 스크립트는 두지 않는다(MASTER §18-5 R8). CI 가 막는다.
tests/
  test_contract.py        GIS ↔ UI 경계
  test_guards.py          계보 2층 · 격리 · 커버리지 · 저장소 위생
  test_seg_geom.py        verdict 단위
  test_seg_width.py       WidthEngine 단위
  test_seg_roadname.py    RoadNameIndex 단위
  test_static.py          정의되지 않은 이름 (실패 경로의 NameError)
  test_intake_rules.py    명명·스코프·인코딩 규칙 — raw 없이 도는 강제자
  test_reproducibility.py 재현성 규약 강제 · 문서 ↔ 코드 동기화
  test_doc_style.py       문서 문체 · 절 번호 · 어휘
  test_declaration_sync.py ★ 역방향 — 실물이 선언돼 있는가
  test_ownership.py       ★ 미소유 경로가 없는가. CODEOWNERS 전수 검사
  test_docref.py          절 참조 무결성 · 하위 절 번호 유일·연속
  test_workflow_html_sync.py   web/workflow.html ↔ 브랜치·팀·워크플로 대조
  test_contract_vision.py GIS ↔ CV 경계 (MASTER §19)
  test_ledger_outputs.py  대장 outputs ↔ 실제 산출물
  test_place_idempotent.py 지점 집계 멱등성
web/
  index.html              뼈대                      공동
  style.css               색·간격·타이포             @marscoolcat
  config.js               색상표·임계값·마커·카메라   공동
  js/                     로직·레이어 29개 모듈      공백 (PLAN #79)
  data/                   생성물. 손으로 고치지 않는다
```

---

## 지금 상태

```
세그먼트     1,101   (동명동 416 + 119안전센터 접근 회랑)
판정        통행 가능 397 · 판정 보류 191 · 통행 불가 159 · 영상판정 불가 354
도달 가능    687 (62%)   119안전센터에서 막힌 길 없이 갈 수 있는 구간
총연장       48,579.7m
기준        소방청 2025 골든타임 대책 + 2026-08-06 현장 답사 (통과 하한 3.0m)
대장        `datasets` 54종 · `retired` 10종
web/data    지형 22타일 · 정사영상 1,423타일 포함 (크기는 web_manifest 가 낸다)
```

`영상판정 불가` 354 는 전부 CCTV 사각이다. 폭 산출 불가는 0 이다.
사유는 `no_cctv_band` 152 · `no_cctv_thin` 128 · `no_cctv_narrow` 62 ·
`no_cctv_single` 12 넷으로 갈라 적는다.

★ `통행 불가` 159 는 확정 개수가 아니라 **하한**이다. `width_max_m` 결손
496건 중 도로대장 명목폭이 3.0m 이상이거나 없는 64건은 아직 판정되지 않는다.
발표 자료에서 159 를 확정으로 쓰지 않는다.

**폭 값은 아직 미검증이다**(`width_verified: false`, 전건). 레이저 실측 후 바뀐다.
값은 바뀌어도 필드와 `verdict` 어휘는 안 바뀐다. 계약 테스트가 그것을 보장한다.

### 구간 수는 고정값이 아니다

```
641   동명동만 노딩
1,266 접근 회랑 포함
1,101 노드접합 · 산출단위 병합 + 수치지형도 교체   ← 현재 판정 단위
```

노딩 규칙이 바뀌면 `seg_id` 가 전부 밀린다. 외부 참조에는 `seg_uid` 를 쓴다.
중간 단계의 구간 수와 그 사유는 `DECISIONS.md` 가 든다.

## 나는 어느 파트인가

★ 이 파일은 루트라 **누구든 처음 본다.** 지금은 GIS 파이프라인 서술이 많은데
그것은 `src/firelane/README.md` 가 정본이다(PLAN 이 그 정리를 든다).

| 나는 | 브랜치 | 볼 곳 | 문서 |
|---|---|---|---|
| GIS · Web | `part/gis` | `src/firelane/` `data/` `web/` `docs/` | `src/firelane/README.md` |
| Vision · CV | `part/cv` | `src/cv/` | (해당 파트가 쓴다) |
| Infra · API | `part/infra` | `src/api/` `infra/` `Dockerfile.*` | (해당 파트가 쓴다) |

**데이터 레이크는 GIS 담당만 필요하다.** CV·Infra 는 git 으로 추적되는
`web/data/`(40MB 상한)만으로 작업할 수 있다.

배포된 화면 넷이다. **서로 링크하지 않는다** — 각각 다른 사람이 다른
이유로 열고, 화면마다 이동 메뉴를 두면 같은 목록이 네 곳에 산다.
가는 길은 여기 하나다(DECISIONS §99).

```
지도        woongtopia.github.io/fire-lane/
협업 방침    woongtopia.github.io/fire-lane/workflow.html   MASTER §12 생성물
플레이북     woongtopia.github.io/fire-lane/playbook.html   상황별 안내서
기획서       woongtopia.github.io/fire-lane/proposal.html   docs/proposal.docx 를 그대로 그린다
```

## 문서는 어디에

머리의 [문서는 넷이다](#문서는-넷이다) 표가 정본이다.
어긋나면 `uv run python tools/doc_fsck.py` 가 운다.
