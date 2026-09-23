# Fire-Lane

동명동 소방차 진입 판정 시스템 · 전남광주통합특별시 동구

```
착수      2026-08-03
기간      4개월
대상      동명동 + 119안전센터 접근 회랑
```

골목 1,281구간의 실제 통행 가능 폭을 산출해 소방차가 지나갈 수 있는지 판정하고,
**판정할 수 없는 이유까지** 지도에 표시한다.

**지도** https://cleveraifox.github.io/fire-lane/
**내비** https://cleveraifox.github.io/fire-lane/navi/
**관제** https://cleveraifox.github.io/fire-lane/navi/?view=ops — 사건 접수 · 출동 지령 · 판정 지도 · 출동 중 차 · 현장 공유 확인 (내비와 같은 브라우저 탭끼리 연결)

---

## 문서는 넷이다

문서 넷은 병렬 축이 아니라 **한 항목의 생애주기**다.

```
PLAN(미래)  →  도래  →  MASTER(현재)  →  회고  →  DECISIONS(과거)
```

| 문서 | 시제 | 담는 것 |
|---|---|---|
| [`docs/PLAN.md`](docs/PLAN.md) | 미래 | 남은 일 · 미결정 · 담당 공백 · 결함 대장 |
| [`docs/MASTER.md`](docs/MASTER.md) | 현재 | 판정 · 데이터 · 용어 · UI 계약 · 운영 |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 과거 | 왜 그렇게 됐나 (append-only) |
| `docs/proposal.docx` | — | 대외 제출용. 시제 규칙 밖 |

**한 항목은 한 문서에만 산다.** 두 곳에 있으면 한쪽만 고치는 날이 온다.
남은 일의 정본은 **수용 조건**으로 갈린다 — 판정을 움직이는 일은 `PLAN §1`,
안 움직이는 일(배선·정본화·문서 결함)은 `PLAN §13` 이다. 2026-09-18 감사에서
남은 일 42건이 **어느 쪽에도 없었고**, 그때까지 이 줄은 거짓이었다(DECISIONS §190-1).

**다섯 번째는 만들지 않는다.** 과거·현재·미래 세 시제가 다 찼다.
새 문서를 만들고 싶으면 그것은 셋 중 하나의 절이다.
`tests/test_reproducibility.py::test_no_fifth_doc` 이 저장소 전체를 보고 막는다.

`sources.yaml` 은 데이터 정본이다. 기계가 읽으므로 손으로 고칠 때 주의할 것.

강제자  `tests/test_reproducibility.py::test_doc_axis_tables_are_consistent` · `::test_no_fifth_doc`
        ★ 축 표의 정본은 MASTER 머리다. 이 표와 PLAN 머리는 사본이고 셋이 갈리면 운다.
          2026-09-18 까지 이 절은 검사 이름을 **산문으로만** 들었다 — `dms` 는 줄머리 칸만 센다.


### 일회성 도구는 저장소에 두지 않는다

    "내년에도 이걸 돌릴 일이 있나"
      있다  →  `tools/`            재현적이다. `verify.sh` 에 배선하고 README 에 적는다
      없다  →  저장소 밖에서 돈다   `~/oneoff/<저장소>/`. 커밋하지 않는다

한 번 돌고 끝난 스크립트는 남기지 않는다. 무엇을 왜 바꿨는지는
`DECISIONS` 가 정본이고, 스크립트를 같이 남기면 같은 기록이 두 벌이 된다.
어느 쪽이 정본인지 모르게 되는 것이 이 저장소가 232번 당한 형태다.

★ 2026-09-13 까지는 규약이 정반대였다. `tools/batches/` 에 34개가 쌓였고
그 규약에 강제자가 없어 디렉터리를 통째로 지워도 우는 곳이 없었다.
`tests/test_reproducibility.py::test_no_one_off_in_repo` 가 지금은 막는다.

### 문서에도 검사가 붙어 있다

```bash
uv run python tools/docnum_check.py     # 문서 숫자 ↔ 산출물 · 필드표 대조
uv run python tools/lakecheck.py        # 레이크 선언 ↔ 실물 (L1~L6)
uv run python tools/deadcheck.py        # 검사가 죽었는지 검사 (프로브 5)
uv run python tools/gate_parity.py     # 로컬 관문 ↔ CI 차집합 (래칫 · 정본은 도구 안)
uv run python tools/dms.py delta         # 봉인 뒤 바뀐 절만 (소급 증분)
uv run python tools/dms.py rawdiff       # raw 가 봉인과 같은가 (전량 생략 근거)
uv run python tools/plan_renumber.py     # PLAN 번호·참조 정합 · 결번 대장 (★ --apply 는 폐지 — 번호는 영구 식별자다)
uv run python tools/dupcheck.py --min 40 # 같은 구조가 몇 벌인가 (사본군)
uv run python tools/sizecheck.py        # 파일 길이 양방향 래칫 (코드 600 · 시험 700 · EXCEPTIONS)
# ★ 위 도구가 세는 사본을 합친 자리 —
#   src/firelane/hashing.py    파일 sha256. 10곳이 한 벌이었다
#   src/firelane/console.py    col · human · 팔레트. 17곳
#   src/firelane/mercator.py   웹 메르카토르 역변환. 2곳
#   ledger.yaml_span · load_sources   대장 원문 파싱. 7곳
uv run python tools/vintage_check.py    # 파일명 날짜 ↔ 대장 updated (자료 기준일)
uv run python -m firelane.prep --check  # norm 이 지금의 raw 에서 나왔나 (재현성)
uv run python tools/widen.py            # 검사 범위를 넓히면 뭐가 걸리나
uv run python tools/codepatch.py        # 파이썬 소스 멱등 편집기 (배치용)

# 배치가 세운 상태가 유지되는가 — verify.sh 가 부른다
uv run python tools/install_navi.py --check    # web/navi/src 목록
uv run python tools/navi_env.py                # 내비 환경 = CI (잠금 → npm ci · 노드 판 · engines)
uv run python tools/pages_add_navi.py --check  # 배포에 내비 빌드
uv run python tools/navi_setup.py --check      # 루트 잔재 · 유령 면제
uv run python tools/ledger_fields.py --check   # 폐기 별칭 부활
uv run python tools/sweep.py            # 다운로드·레이크 스캔 → 근거 있는 것만 정리
uv run python -m pytest tests/test_doc_style.py tests/test_reproducibility.py -q
```

문체·절 번호·어휘·생애주기·죽은 경로를 전부 코드가 본다.
**규약을 새로 적을 때는 강제자를 같이 만든다**(MASTER §17).

★ 강제자를 만들 때는 **그 강제자 자신의 목록 · 범위 · 형식 · 환경**을
실물과 대조한다(`DECISIONS §114-7`). 면제 목록에는 역방향을, 루트 기준
순회에는 형제 확인을, 형식 의존 검색에는 형식별 판독을 함께 붙이고,
참조하는 파일이 CI 에도 있는지 본다 — gitignore 대상이면 로컬에서만
통과하는 검사가 된다.

강제자 없음 — 사유: README 는 도구 목록이고 test_declaration_sync.py::test_readme_lists_tools_the_automation_calls 가 verify.sh 와 대조한다. 절 자체를 강제하는 것은 아니다

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
# 전역 훅이 저장소 `.githooks` 에 위임한다. **로컬로 박으면** 전역이 죽고 자격증명 검사가 사라진다
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"   # 머신마다 다르다

uv run python -m firelane.normalize_raw "$FIRE_LANE_DATA/landing" --dry-run
uv run python -m firelane.contract
uv run fire-lane

uv run python tools/serve.py        # 배포와 같은 배치(입구 · navi 빌드 · data)
```

`uv pip install -e .` 은 쓰지 않는다. `[build-system]` 이 있으므로 `uv sync` 가
editable 로 알아서 깐다 — 검사 스크립트의 첫 단계가 그것이다.

받자마자 한 번, 그리고 큰 변경 뒤에는 이것 하나면 된다.

```bash
bash tools/verify.sh          # 51단계 전부. 실패해도 끝까지 돌고 표로 보여준다
bash tools/verify.sh --fast   # 급할 때. ★ `부분 실행` 에서 일부러 빨갛게 죽는다
```

★ `--fast` 로 찍은 로그로는 **봉인할 수 없다.** 건너뛴 것은 통과가 아니다.
근거 있는 생략은 두 겹이다. `dms.py rawdiff` 가 raw **와 파이프라인 코드**가 봉인과
같으면 전량을 안 돈다(44초). 돌 때는 ingest 가 소스마다 봉인지를 대조해 **찢어진
샤드만** 다시 만든다(DECISIONS §164 · §165). 모르면 안 건너뛴다.

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
bash tools/janitor.sh       # 기계·저장소·레이크 세 층을 한 표로
```

죽은 upstream · 머지된 브랜치 · 백업 폴더 · 캐시를 본다.
**데이터 계층은 건드리지 않는다** — `data/raw` · `norm` · `field` · `web/data`
는 `NEVER` 로 막혀 있고 규칙에 실수로 넣어도 안 지워진다.

**마지막 하나는 사람이 봐야 한다.** WebGL 렌더링은 스크립트가 못 본다.
지도가 실제로 그려지는지, 판정 색·표지판·경로·관제 패널이 눈으로 멀쩡한지는
`tools/serve.py` 로 직접 확인한다(배포와 같은 배치 — 입구 · navi 빌드 · data).

강제자  `tools/verify.sh`

### 파이프라인

```
ingest → segments → scope → streetlight → terrain → ortho → publish → 계약 테스트 → 지문 대조
```

```bash
uv run fire-lane --check          # 실행 없이 상태만
uv run fire-lane --from segments  # 그 단계부터
uv run fire-lane --only publish
uv run fire-lane --split          # ingest 를 소스별 자식 프로세스로 (메모리 반납)
```

★ `--split` 은 기본값이 아니다. 8GB 기계에서 `Errno 12` 를 막지만 2분45초가
3분59초가 된다 — 자식마다 `geopandas` 를 다시 import 하는 값이라 코드로 못
줄인다. `verify.sh` 처럼 앞 단계가 이미 메모리를 먹은 맥락에서만 켠다
(`DECISIONS §160`).

★ `uv run` 을 빼면 `command not found` 다. 진입점은 `.venv/bin/fire-lane` 에
설치되고 그 폴더는 PATH 에 없다. `uv sync` 가 editable 로 깔아주지만
**셸에 노출하지는 않는다** — 이것 때문에 파이프라인이 안 돌았고, 그 상태로
`golden.py check` 를 돌려 **통과했다.** 옛 산출물을 옛 지문과 비교한 것이라
아무것도 증명하지 않는다. 가장 위험한 종류의 초록불이다.

전량 재실행 약 285초. **`processed` 를 백업하지 않는 근거가 이 시간이다.**
raw + 코드 + 대장이 있으면 결정론적으로 재생성된다.

**단계를 하나씩 손으로 치지 않는다.** 순서가 중요하고 빠뜨리기 쉽다.

강제자  `tests/test_guards.py::test_docs_call_the_entrypoint_through_uv`

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
bash tools/merge_batch.sh [--release]       배치 PR 머지 → 파트 동기화 (적용 스크립트가 초록일 때만)
bash tools/fl.sh <feat/x> [--all|--undo|--resume]  ★ 배치 한 명령 — 적용 · verify · PR · 스쿼시 · 방송 · 정리
bash tools/branch_tidy.sh [--auto] [--close-bots]  열린 PR · 원격/로컬 가지 정리 · 봇 PR 닫기 (fl.sh 10단계가 부른다)
bash tools/inbox_fl.sh                      INBOX 에 `fl.sh` 로 두는 부트스트랩 — 패치 안 판을 골라 부른다
```

★ 배치는 INBOX 에서 이렇게 돈다: `bash "$FIRE_LANE_INBOX/fl.sh" feat/x --all`.
  INBOX 의 `fl.sh` 는 `tools/inbox_fl.sh` 사본이고, 진짜 도구는 **패치 안(없으면
  origin/part/infra)의 `tools/fl.sh`** 다(DECISIONS §214-1).
★ 배치 끝의 두 단계 — 10 가지 정리(`branch_tidy.sh --auto --close-bots` · 봇 PR 을 사유 댓글과 닫는다) ·
  11 위생(`tidy.py --yes` · `janitor.sh`). 사람이 기억해서 치던 것이다(DECISIONS §217-4).
★ 중간에 끊겼으면 `--resume`. 어디까지 됐는지는 GitHub PR 상태로 가린다 — feat PR 이
  열려 있으면 CI 대기부터, 머지됐으면 dev PR · 방송 · 정리부터(DECISIONS §215-3).

★ **도구는 세 갈래다** — 어디에 두느냐가 갈래를 정한다.

    ① 재현 · 자동     verify.sh · CI 가 부른다                         tools/ + 배선
    ② 재현 · 사람     사람이 판단하려고 부른다. 같은 입력이면 같은 출력    tools/ + README 한 줄 +
                                                                        (배선 또는 EXEMPT 에 사유)
    ③ 한 번 쓰고 버림  조사 · 이관 · 디버그 스크립트                     **저장소 밖**

  ③ 을 tools/ 에 넣지 않는다. 넣는 순간 ② 처럼 보이고, 아무도 안 고치는 채로 낡는다.
  ② 로 올릴 값어치가 생기면 README 줄과 배선(또는 사유)을 같이 단다.

강제자  `tests/test_tools_are_wired.py::test_every_tool_is_named_in_readme`

### 대조 도구 — 아무것도 안 바꾼다

```bash
uv run python tools/width_fn.py         폭을 함수 w(s) 로 — min 대 통과폭
uv run python tools/jijeok_probe.py     연속지적도(세 번째 계보)로 폭 대조
uv run python tools/jijeok_review.py    갈리는 구간을 정사영상 위에서 판정
uv run python tools/lanes_probe.py      표준노드링크 차로수로 폭 하한 대조
uv run python tools/route_probe.py      소방차 통행 비용으로 경로 — 거리만 대 차량
uv run python tools/clearance_probe.py  최대내접원 방식 (2026-08-22 기각)
uv run python tools/desk_check.py       정사영상 위에 구간·폭 렌더 (책상 대조)
uv run python tools/skeleton_compare.py NGII 1:1,000 뼈대 후보 대 현행 구간 — 위치 의심표 (R1)
uv run python tools/transition.py      옛 구간 → 새 구간 전이표 — 1:N · N:1 · 소멸 · 신설 (R2)
uv run python tools/wmax_audit.py       width_max_m 결손이 판정에 미치는 규모
uv run python tools/bridge_audit.py     끊기면 뒤가 통째로 막히는 구간 — 실측 우선순위
uv run python tools/its_linkmap.py      ITS 소통정보 링크 ↔ seg_uid 대조표
uv run python tools/matchcheck.py       Mapbox Map Matching 커버리지 (MAPBOX_TOKEN 필요)
uv run python tools/field_compare.py    실측 야장 ↔ 우리 폭 · 판정 — 위험 오판 · 보정 제안 (트랙 C 봉인)
```

읽고 표를 내거나 페이지를 만들 뿐이라 `golden` 지문에 영향이 없다.
**측정하고 대조한 뒤에 판정을 바꾼다** — `n=7` 로 방법 하나를 기각했다가
근거를 다시 쓴 것이 그 교훈이다(DECISIONS).

강제자  `tests/test_tools_are_wired.py::test_every_tool_is_named_in_readme`

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
차량 비용 통행 불가   474 / 1,281   폭 · 내륜차 · 회전반경까지 넣으면 못 지나간다
도달 가능            834 (65%)     안전센터에서 막힌 길 없이 갈 수 있다
도달 불가            447 (35%)
```

**막힌 구간 하나가 뒤쪽 골목 여러 개를 통째로 끊는다.** 폭 15m 대로라도
진입로가 막히면 소방차가 못 간다.

★ 474 는 지도의 빨강(`verdict` 191)과 **다른 값이다.** 산출 경로가 다르고
판정에도 반영되지 않는다. 셋의 구분은 `MASTER §3-9` 가 든다.

강제자 없음 — 사유: 도달 불가 조인은 tests/test_reach_overlay.py 가 보고 수 대조는 다음 코드 배치다(DECISIONS §167)

---

## 데이터 계층

정본은 **`MASTER §18`** 이다. 계층 선언은 `sources.yaml` 의 `layers` 블록,
경로 해석은 `src/firelane/paths.py`, 계층별 책임(획득 · 계약 · 생산 · 재현)은
`MASTER §5-3a` 가 든다. 여기에는 입구만 적는다.

강제자 없음 — 사유: 정본은 MASTER §18 이고 이 절은 참조만 둔다

### 게이트

```bash
uv run python tools/pull_data.py            관측만
uv run python tools/pull_data.py --yes       반입 · 편입 · norm
uv run python tools/pull_data.py --yes --all 위 + 파이프라인 + golden
```

★ 이 절이 계층 표 · 게이트 · 제공기관 폴더를 따로 들고 있었고, 제공기관을
**12폴더라 적고 이름은 열 개만** 나열하고 있었다(`mois` · `gjbg` 누락).
사본은 이렇게 낡는다(DECISIONS §162-4).

강제자 없음 — 사유: 입구 명령이다. 게이트 강제자는 MASTER §18-11 이 든다

---

## 구조

```
sources.yaml              데이터 정본. layers · datasets · outputs · retired
src/contracts/            ★ 파트 간 유일한 접점. 세 파트가 이것만 import 한다
  vision.py               영상판정 인터페이스 (MASTER §19 의 실행 가능한 사본)
src/firelane/
  paths.py                경로 정본. FIRE_LANE_DATA 환경변수
  layers.py               계층 선언과 경로를 이름으로 묶는다
  ledger.py               대장 항목 스키마의 정본. 산문을 필드로 읽는다
  kinds.py                `kind` 분류의 정본. 여섯 곳에 흩어져 있던 것을 모았다
  scope.py                공간 범위의 통제 어휘. 선언이 정본이다
  naming.py               raw 파일명 문법의 정본. 파서가 곧 규칙이다
  providers.py            raw 1단 폴더(제공기관)의 정본
  encoding.py             인코딩 판별과 정규화. 디코드 성공은 정답이 아니다
  lake.py                 레이크 해석기. 대장 + 디스크 → 파일마다 한 줄
  normalize_raw.py        landing → raw 명명규칙 배치
  prep.py                 raw → norm. 형식만 통일한다. 값은 안 바꾼다
  contract.py             ★ 대장 ↔ 실물 계약 게이트
  pipeline.py             단일 진입점. Step 선언(reads/writes/mutates)
  lineage.py              ★ 계보. 단계별 입출력 지문 대조
  ingest.py               raw → processed
  shardseal.py            ingest 샤드(소스 하나)의 봉인지. 넷이 같을 때만 재사용
  ngii1k.py               수치지형도 도엽 → 레이어별 gpkg
  ngi.py                  NGI/NDA 리더
  guards.py               방어 정본. 낡은 산출물 격리 · 공간 커버리지
  segments.py             조립부. 계산은 seg/ 가 한다
  skeleton.py             ★ 판정 뼈대 후보(NGII 1:1,000 중심선 하이브리드). 순수 함수 (R1 · DECISIONS §184)
  transition.py           ★ 옛 구간 → 새 구간 전이표. 1:N · N:1 · 소멸 · 신설 (R2 · §187)
  seg/
    params.py             판정 임계값 정본. 표출 상수는 display_scope.py 가 든다(DECISIONS §220)
    graph.py              노딩 · 최대성분 · 접근 회랑
    width.py              폭 산출 (WidthEngine)
    geom.py               verdict · _seal · _join · _dirv (폐포 없는 순수 함수)
    roadname.py           도로명 되붙이기 (RoadNameIndex)
    basisno.py            기초구간 → seg_label
    vehicle.py            차량 제원 · 엣지 비용
    report.py             소방서 대조 · 진단 · 산출물 기록
    scope.py              판정 범위 (judgment_scope) — 표출 범위는 판정 지문 밖이다
    centerline_correction.py  사람이 승인한 중심선 위치 보정. 지문이 안 맞으면 실패한다
  display_scope.py        ★ 표출 범위 단계 (display_scope · DISPLAY_BUFFER/CLOSE) — 판정 지문 밖 · scope_5186.gpkg
  streetlight.py          가로등 지점 단위 집계
  terrain.py              공개DEM → Terrain-RGB 타일
  ortho.py                항공정사영상 → 배경 타일
  publish_web.py          → web/data
  publish_navi.py         내비가 먹을 그래프 하나 (navi_graph.json)
  publish_fleet.py        관내 보유 차종 · 제원 → 내비
  publish_basemap.py      내비 바탕 면 — 도로면(수치지형도 + 실폭도로) · 보도. 판정과 무관
  publish_context.py      경로 주변 사정(과속방지턱 · 카메라 · 보호구역) · 119 출동 이력(실제 도착 시간). 판정과 무관
  destinations.py         내비 목적지 검색 색인. 상가 · 주소/건물 · 관공서
  vehiclecard.py          소방자동차 관리카드 판독
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
  plan_renumber.py        PLAN §1 표 번호를 1..N 으로 · 결번 해소
  commit_policy.py        산출물 · 일회성 스크립트 · 비밀값 차단
  encoding_check.py       인코딩 · 개행
  env_check.py            환경변수 선언(.env.example) ↔ 실물 · 단일 독자
  web_manifest.py         web/data 계보 검사
  scopecheck.py           ★ 발행 스코프가 출동 대상지(동명동) 밖으로
                          얼마나 벗어났는가. 래칫 — 지금 값에서 내린다
  freshcheck.py           ★ 커밋된 생성물이 **왜** 낡았는지를 자리로 말한다
                          (시각 · 코드/설정/원본 봉인 · 파생 · 산출값)
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
  render_figures.py       ★ 정본 → docs/figures/*.svg · --check 로 낡음 · 라벨 넘침 · 막대 덮음 대조
  docx_figs.py            ★ 그 그림을 기획서 안에 넣는다 — --sync 가 교체 · --check 는 변환기 없이 대조
  release_brief.py        ★ 이 PR 이 무엇을 흡수하나 — 판정·계보·대장·계약
  ruleset_check.py        GitHub 룰셋 ↔ 문서 방침 대조 (사람이 주기적으로)
  ledger_feeds.py         feeds 산문 → 소비자 리스트
  serve.py                배포와 같은 배치로 띄운다 (입구 · navi 빌드 · data)
  wmax_audit.py           width_max_m 결손이 판정에 미치는 규모
  desk_check.py           정사영상 위에 구간·폭 렌더
  skeleton_compare.py     NGII 뼈대 후보 대 현행 구간 대조 (R1)
  transition.py           옛 구간 → 새 구간 전이표 (R2 · R3 전후)
  docpatch.py             문서 절 단위 멱등 교체 · 표 행 추가
     ※ 날짜 붙은 일회성 스크립트는 두지 않는다(MASTER §18-5 R8). CI 가 막는다.
tests/
  test_contract.py        파이프라인 ↔ 화면 경계 (web/data 계약)
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
  index.html              관제(navi/?view=ops)로 넘기는 입구
  navi/                   내비 · 관제 앱 (React + MapLibre · vite 8 · vitest)
  config.js               파이프라인 설정 — 판정색 · 지형 과장 · 편성
  data/                   생성물. 손으로 고치지 않는다 — 백엔드와 화면 사이의 계약
```

강제자 없음 — 사유: 구조 블록의 실재는 test_readme_structure_lists_real_files 가 본다

---

## 지금 상태

```
세그먼트     1,281   (동명동 416 + 119안전센터 접근 회랑 70m + 안전센터 반경 300m)
판정        통행 가능 465 · 판정 보류 226 · 통행 불가 191 · 영상판정 불가 399
도달 가능    834 (65%)   119안전센터에서 막힌 길 없이 갈 수 있는 구간
도달 불가    447         지도에 점선으로 겹친다 — 판정이 clear 여도 닿지 못한다
총연장       58,308.7m
기준        소방청 2025 골든타임 대책 + 2026-08-06 현장 답사 (통과 하한 3.0m)
대장        `datasets` 72종 · `retired` 4종
web/data    지형 22타일 · 정사영상 1,423타일 포함 (크기는 web_manifest 가 낸다)
내비        web/navi/ — GPS 위치 추정(경로 투영 · 순간이동 재동기화) · A* · 턴바이턴 · 대체 접근 지점
            edge_cost 는 파이썬과 전량 대조 · 단위 시험 web/navi/test (npm run test · vitest)
            vite 8(rolldown) · 지형(Terrain-RGB) 지면 휨 · 모든 레이어를 style-spec 검증기로 본다
관제        web/navi/?view=ops — 유일한 지도 화면. 옛 GIS 지도(web/js)는 2026-09-22 걷어냈다(DECISIONS §218-1)
KPI         폭 미인지 내비가 통행불가를 지나는 목적지 299/707 (42%)
```

`영상판정 불가` 399 는 전부 CCTV 사각이다. 폭 산출 불가는 0 이다.

**시간을 줄이는 앱이 아니라 못 가는 길로 보내지 않는 앱이다.** 폭을 모르는
내비의 최단경로는 세 번 중 한 번 이상 소방차가 못 지나가는 구간을 지난다.
우리 경로는 그것을 피하면서 실거리가 더 길지 않다 — 중앙값 1.00배.
숫자는 `uv run python tools/kpi.py` 가 계산 조건과 함께 낸다.
사유는 `no_cctv_band` 183 · `no_cctv_thin` 142 · `no_cctv_narrow` 61 ·
`no_cctv_single` 13 넷으로 갈라 적는다.

★ `통행 불가` 191 은 확정 개수가 아니라 **하한**이다. `width_max_m` 결손
675건 중 노면 3.0m 미만인데 도로대장 명목폭이 3.0m 이상이거나 없는 92건은 막을 근거가 하나뿐이라 막지 않는다.
발표 자료에서 191 을 확정으로 쓰지 않는다.

★ **측량과 대조한 정확도**(2026-09-16 · DECISIONS §170-4) — NGII 1:1,000 측량 중심선에 엄격 매칭된
1,041구간(81%)에서 **통행 가능인데 측량폭 3m 미만 0 · 통행 불가인데 측량폭 6m 이상 0**,
노면 최솟폭 대 측량폭 절대편차 중앙 0.31m 다. 매칭 안 된 240구간(대부분 수치지도가 도로로
안 그린 최협소 골목)은 측량으로 검증되지 않는다 — 정본은 현장 실측이다.

**폭 값은 아직 미검증이다**(`width_verified: false`, 전건). 레이저 실측 후 바뀐다.
값은 바뀌어도 필드와 `verdict` 어휘는 안 바뀐다. 계약 테스트가 그것을 보장한다.

강제자 없음 — 사유: 수치는 docnum_check 가 segments · 판정 수를 대조하고 도달 가능 수는 다음 코드 배치다

### 구간 수는 고정값이 아니다

```
641   동명동만 노딩
1,266 접근 회랑 포함
1,101 노드접합 · 산출단위 병합 + 수치지형도 교체   <!--stale-ok-->
1,281 판정 범위에 119안전센터 반경 300m 추가 · 필문대로289번길 중심선 보정   ← 현재 판정 단위
```

노딩 규칙이 바뀌면 `seg_id` 가 전부 밀린다. 외부 참조에는 `seg_uid` 를 쓴다.
중간 단계의 구간 수와 그 사유는 `DECISIONS.md` 가 든다.

## 나는 어느 파트인가

★ 이 파일은 루트라 **누구든 처음 본다.** 지금은 GIS 파이프라인 서술이 많은데
그것은 `src/firelane/README.md` 가 정본이다(PLAN 이 그 정리를 든다).

| 나는 | 브랜치 | 볼 곳 | 문서 |
|---|---|---|---|
| GIS · Web | `part/gis` | `src/firelane/` `data/` `web/` `docs/` | `src/firelane/README.md` |
| Vision · CV | `part/cv` | 아직 코드 없음 — 입력은 `web/data/segments.geojson` 의 `needs_cv` 226구간 · `cctv.geojson` | DECISIONS §213-5(4색 정의) |
| Infra · API | `part/infra` | 아직 서버 없음 — 배포는 `.github/workflows/_deploy.yml` · 배치는 `tools/fl.sh` | README `## 도구` |

**데이터 레이크는 GIS 담당만 필요하다.** CV·Infra 는 git 으로 추적되는
`web/data/`(40MB 상한)만으로 작업할 수 있다.

배포된 화면 다섯이다. **서로 링크하지 않는다** — 각각 다른 사람이 다른 이유로 열고, 화면마다 이동 메뉴를 두면 같은 목록이 네 곳에 산다.
가는 길은 여기 하나다(DECISIONS §99). 플레이북(`web/playbook.html`)은 협업 방침을 그리는
**틀**이라 따로 배포하지 않는다(§216-5).

```
지도        cleveraifox.github.io/fire-lane/
협업 방침    cleveraifox.github.io/fire-lane/workflow.html   MASTER §12 생성물
기획서       cleveraifox.github.io/fire-lane/proposal.html   docs/proposal.docx 를 그대로 그린다
내비        cleveraifox.github.io/fire-lane/navi/          출동 경로 안내. web/data 를 그대로 읽는다
관제        cleveraifox.github.io/fire-lane/navi/?view=ops 사건 접수 · 출동 지령 · 실시간 공유 확인
```

강제자  `tests/test_n1.py::test_no_doc_sends_people_to_old_pages_domain` — 옛 조직 주소(이관 전 배포)로 보내지 않는다(DECISIONS §181-6)

## 문서는 어디에

머리의 [문서는 넷이다](#문서는-넷이다) 표가 정본이다.
어긋나면 `uv run python tools/doc_fsck.py` 가 운다.
