# Fire-Lane

동명동 소방차 진입 판정 시스템 · 전남광주통합특별시 동구

```
착수      2026-08-03
기간      4개월
대상      동명동 + 119안전센터 접근 회랑 + 안전센터 반경 300m
```

골목 1,281구간의 실제 통행 가능 폭을 산출해 소방차가 지나갈 수 있는지 판정하고,
**판정할 수 없는 이유까지** 지도에 표시한다.

**관제** https://cleveraifox.github.io/fire-lane/ — 사건 접수 · 출동 지령 · **판정 지도** · 출동 중 차 · 현장 공유 확인
**내비** https://cleveraifox.github.io/fire-lane/navi/ — 출동 경로 안내 (관제와 같은 브라우저 탭끼리 연결)

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
| `docs/proposal.md` | — | 대외 제출용 **내용 정본**. 시제 규칙 밖. 화면 `web/proposal.html` 은 생성물이다 |

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

강제자  `tests/test_tools_are_wired.py`(`tools/` 의 것이 **제 머리말 첫 줄에 제 이름·설명을 대고** 어딘가에서 불리는가 — 판정은 `tools/toolindex.py` 가 한다. 둘 다 아니면 저장소 밖으로 나가야 한다 · DECISIONS §352)

    "내년에도 이걸 돌릴 일이 있나"
      있다  →  `tools/`            재현적이다. `verify.sh` 에 배선하고 **머리말 첫 줄**에 적는다
      없다  →  저장소 밖에서 돈다   `~/oneoff/<저장소>/`. 커밋하지 않는다

한 번 돌고 끝난 스크립트는 남기지 않는다. 무엇을 왜 바꿨는지는
`DECISIONS` 가 정본이고, 스크립트를 같이 남기면 같은 기록이 두 벌이 된다.
어느 쪽이 정본인지 모르게 되는 것이 이 저장소가 232번 당한 형태다.

★ 2026-09-13 까지는 규약이 정반대였다. `tools/batches/` 에 34개가 쌓였고
그 규약에 강제자가 없어 디렉터리를 통째로 지워도 우는 곳이 없었다.
`tests/test_reproducibility.py::test_no_one_off_in_repo` 가 지금은 막는다.

### 문서에도 검사가 붙어 있다

문체·절 번호·어휘·생애주기·죽은 경로를 전부 코드가 본다. **어느 도구가 무엇을
보는지는 그 도구가 제 머리에 적는다** — `uv run python tools/toolindex.py` 가
전수 색인을 낸다. 종전에 여기 **61줄 · 도구 마흔넷**짜리 목록이 있었다. 설명이 두 벌이면
갈린다(DECISIONS §352).
**규약을 새로 적을 때는 강제자를 같이 만든다**(MASTER §17).

★ 강제자를 만들 때는 **그 강제자 자신의 목록 · 범위 · 형식 · 환경**을
실물과 대조한다(`DECISIONS §114-7`). 면제 목록에는 역방향을, 루트 기준
순회에는 형제 확인을, 형식 의존 검색에는 형식별 판독을 함께 붙이고,
참조하는 파일이 CI 에도 있는지 본다 — gitignore 대상이면 로컬에서만
통과하는 검사가 된다.

강제자 없음 — 사유: 이 절은 「검사가 붙어 있다」는 사실만 적고 목록은 안 든다. 목록의 정본은 도구 자신이며 tools/toolindex.py 가 그것을 판정한다(DECISIONS §352). 절 자체를 강제하는 것은 아니다

### `D-XX` 는 날짜가 아니다

강제자 없음 — 사유: 새 D 번호를 안 만든다는 약속이라 기계가 셀 것이 없다. 대응표가 실재하는지는 `tools/refcheck.py` 가 본다

**미결정 항목 번호(Decision)** 다. 2026-08-07 「미결정 사항 정리」에서 왔고
`MASTER §10-0` 에 대응표가 있다. 새 D 번호는 만들지 않는다.

### 숫자의 정본은 문서가 아니다

강제자  `tools/docnum_check.py`(문서 ↔ golden) · `tools/golden.py`(golden ↔ 산출물) · `tests/test_nfa_table.py`(MASTER §4 소방서 대조 표 ↔ 봉인 사본)

문서에 적힌 구간 수·판정 수는 **파이프라인 산출물의 사본**이다. 정본은
`data/processed/segments.geojson`, 기대값은 `data/golden/segments.fingerprint.json`
이다. 셋이 어긋나면 산출물이 옳다.

★ 2026-10-01 (DECISIONS §346). 이 원칙에 **짝이 없던 자리가 하나 있었다** —
소방서 대조 표(MASTER §4)는 그 절이 스스로 「대조 도구가 없다」고 적어 둔 채
사흘 낡았다(8.31 → 실측 8.78m). 정본은 커밋된 봉인 사본이고, 이제 짝이 있다.

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
bash tools/verify.sh                  # 전 단계. 실패해도 끝까지 돌고 표로 보여준다
bash tools/verify.sh --since=origin/dev   # ★ 바뀐 것이 닿는 단계만. 되먹임용
bash tools/verify.sh --scope-list     # 단계마다 어느 경로에 반응하는가 (아무것도 안 돈다)
bash tools/verify.sh --only=pytest    # 이름이 맞는 단계만
bash tools/verify.sh --fast           # 급할 때. 파이프라인 전량을 뺀다
```

★ **`--since` 가 「매번 전부 다 도는가」에 대한 답이다.** 단계마다 `scope` 선언이
붙어 있고(`verify.sh --scope-list` 가 실측을 낸다 — 선언 없는 단계는 **항상 돈다**,
그것이 안전한 기본값이다),
`--since` 는 그 범위에 닿은 변경이 없는 단계를 건너뛴다. 문서만 고친 배치면
`파이프라인 전량`(20분) · 레이크 셋이 빠져 35분이 10분이 된다.

★ 그런데 **`--only` · `--fast` · `--since` 셋 다 마지막에 「부분 실행」 단계에서
일부러 빨갛게 죽는다.** 부분 실행은 **빠른 되먹임 도구지 수용이 아니다** — 여기서
안 울면 `dms.py seal` 이 반쪽 실행을 전수로 착각하고 봉인한다. 머지 관문은 언제나
인자 없는 전수다.

★ `--fast` 로 찍은 로그로는 **봉인할 수 없다.** 건너뛴 것은 통과가 아니다.
근거 있는 생략은 두 겹이다. `dms.py rawdiff` 가 raw **와 파이프라인 코드**가 봉인과
같으면 전량을 안 돈다(1분 밑). 돌 때는 ingest 가 소스마다 봉인지를 대조해 **찢어진
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
ingest → segments → nfa_compare → scope → terrain → ortho → publish → 계약 테스트 → 지문 대조
```

```bash
uv run fire-lane --check          # 실행 없이 상태만
uv run fire-lane --from segments  # 그 단계부터
uv run fire-lane --only publish
uv run fire-lane --split          # ingest 를 소스별 자식 프로세스로 (메모리 반납)
```

★ `--split` 은 기본값이 아니다. 8GB 기계에서 `Errno 12` 를 막지만 전량이
**1.4배**가 된다 — 늘어난 몫은 자식마다 `geopandas` 를 다시 import 하는
값이라 코드로 못 줄인다. `verify.sh` 처럼 앞 단계가 이미 메모리를 먹은 맥락에서만 켠다
(`DECISIONS §160`).

★ `uv run` 을 빼면 `command not found` 다. 진입점은 `.venv/bin/fire-lane` 에
설치되고 그 폴더는 PATH 에 없다. `uv sync` 가 editable 로 깔아주지만
**셸에 노출하지는 않는다** — 이것 때문에 파이프라인이 안 돌았고, 그 상태로
`golden.py check` 를 돌려 **통과했다.** 옛 산출물을 옛 지문과 비교한 것이라
아무것도 증명하지 않는다. 가장 위험한 종류의 초록불이다.

전량 재실행은 **수 분**이고, 그것이 `processed` 를 백업하지 않는 근거다.
raw + 코드 + 대장이 있으면 결정론적으로 재생성된다. 걸린 시간은
`uv run fire-lane` 이 끝에 `총 …s` 를 스스로 적는다 — **문서는 그 수를 안 든다**
(기계마다 다르다 · `DECISIONS §326`).

**단계를 하나씩 손으로 치지 않는다.** 순서가 중요하고 빠뜨리기 쉽다.

강제자  `tests/test_guards.py::test_docs_call_the_entrypoint_through_uv`

---

## 루트에서 내린 것

★ 2026-10-10 (DECISIONS §450 · PLAN #34 닫힘). 이 파일은 **clone 한 사람이 처음
보는 자리**다. 그래서 넷만 둔다 — **무엇을 만드나 · 5분 시작 · 어느 파트인가 ·
문서는 어디에.** 나머지 다섯은 `docs/MASTER.md` §24 로 내렸다.

| 내린 것 | 어디로 | 무엇이 들어 있나 |
| --- | --- | --- |
| 도구 | [`MASTER §24-1`](docs/MASTER.md) | 배치 · 검사 · 수리 문을 어떻게 돌리나 |
| 판정의 뼈대 | [`MASTER §24-2`](docs/MASTER.md) | 폭 → 판정 4종까지의 줄거리 |
| 데이터 계층 | [`MASTER §24-3`](docs/MASTER.md) | raw · norm · processed · web |
| 구조 | [`MASTER §24-4`~`24-6`](docs/MASTER.md) | 디렉터리와 그 안의 일 |
| 지금 상태 | [`MASTER §24-7`](docs/MASTER.md) | 서 있는 것 · 안 서 있는 것 |

강제자  `tools/readmecheck.py`(리드미가 적은 목록 ↔ 실물) ·
        `tools/docnum_check.py`(이 파일의 숫자 ↔ 산출물)

## 어느 파트인가

★ 이 파일은 루트라 **누구든 처음 본다.** 지금은 GIS 파이프라인 서술이 많은데
그것은 `src/firelane/README.md` 가 정본이다(PLAN 이 그 정리를 든다).

| 파트 | 브랜치 | 볼 곳 | 문서 |
|---|---|---|---|
| GIS · Web | `part/gis` | `src/firelane/` `data/` `web/` `docs/` | `src/firelane/README.md` |
| Vision · CV | `part/cv` | 아직 코드 없음 — 입력은 `web/data/segments.geojson` 의 `needs_cv` 218구간 · `cctv.geojson` | MASTER §10-2(판정 4종 · 색값은 `web/config.js`) |
| Infra · API | `part/infra` | 아직 서버 없음 — 배포는 `.github/workflows/deploy.yml` · 배치는 `tools/fl.sh` | README `## 도구` |

**데이터 레이크는 GIS 담당만 필요하다.** CV·Infra 는 git 으로 추적되는
`web/data/`(40MB 상한)만으로 작업할 수 있다.

배포된 화면 넷이다. **서로 링크하지 않는다** — 각각 다른 사람이 다른 이유로 열고, 화면마다 이동 메뉴를 두면 같은 목록이 네 곳에 산다.
가는 길은 여기 하나다(DECISIONS §99). 플레이북(`web/playbook.html`)은 협업 방침을 그리는
**틀**이라 따로 배포하지 않는다(§216-5).

```
관제        cleveraifox.github.io/fire-lane/               사건 접수 · 출동 지령 · 판정 지도 · 실시간 공유 확인
내비        cleveraifox.github.io/fire-lane/navi/          출동 경로 안내. web/data 를 그대로 읽는다
협업 방침    cleveraifox.github.io/fire-lane/workflow.html   MASTER §12 생성물
기획서       cleveraifox.github.io/fire-lane/proposal.html   docs/proposal.md 를 구운 화면. 커밋되는 생성물이다(§425 · §444)
```

강제자  `tests/test_n1.py::test_no_doc_sends_people_to_old_pages_domain` — 옛 조직 주소(이관 전 배포)로 보내지 않는다(DECISIONS §181-6)
강제자  `tests/test_n1.py::test_the_deployed_surface_table_matches_web` — 이 표의 딱지가 `web/` 실물과 같은가. 리다이렉트를 화면처럼 적으면 운다(§258)

## 문서는 어디에

축 표의 정본은 `docs/MASTER.md` 머리다 — 이 문서 머리의 [문서는 넷이다](#문서는-넷이다) 표와 PLAN 머리는 사본이다.
어긋나면 `uv run pytest tests/test_reproducibility.py::test_doc_axis_tables_are_consistent` 가 운다.

강제자  `tests/test_reproducibility.py::test_doc_axis_tables_are_consistent`(축 표 셋이 서로 같은가 — 2026-09-28 정정. 종전에 `doc_fsck` 를 댔는데 그 도구에는 축 표를 보는 검사가 없다) · `tests/test_doc_style.py`(다섯 번째 문서 금지)

### 저장소 메타 파일 — 넣은 둘과 안 넣은 넷

> 2026-09-30 (DECISIONS §320 옆 판단). GitHub 이 권하는 파일 여섯 중 **둘만** 넣었다.
> 나머지 넷을 안 넣은 것은 잊은 것이 아니라 정한 것이고, 그래서 여기 적는다.

| 파일 | 넣었나 | 사유 |
|---|---|---|
| `LICENSE` | ✅ | 라이선스 없는 저장소는 **아무도 못 쓴다.** MIT 다. ★ 데이터 이용조건은 여기 적지 않는다 — 제공기관과 출처는 `sources.yaml` 의 `authority` 가 항목마다 들고, 그것이 정본이다. 라이선스 파일에 사본을 두면 둘이 갈린다 |
| `SECURITY.md` | ✅ | 2026-09-12 이전 커밋에 키가 평문으로 있었다. 폐기했고 역사는 안 지웠다 — **그 사실과 신고 주소가 어딘가에 있어야 한다** |
| `CONTRIBUTING.md` | ❌ | 기여자가 **없다.** 단독 개발이고 배치 절차는 `tools/fl.sh` 와 `docs/PLAN.md` 가 든다. 없는 독자를 위한 문서를 두면 그것은 곧 낡고, 낡은 절차 문서는 없는 것보다 나쁘다 |
| `CODE_OF_CONDUCT.md` | ❌ | 규율할 공동체가 없다. 사람이 둘 이상 들어오는 날 넣는다 |
| 이슈·PR 템플릿 | ❌ | PR 템플릿은 **이미 있고 강제된다**(`.github/pull_request_template.md` · `tools/pr_body_check.py`). 이슈는 쓰지 않는다 — 남은 일은 `docs/PLAN.md` §1 한 표가 들고, 두 집에 두면 갈린다 |
| `CHANGELOG.md` | ❌ | **다섯 번째 문서가 된다.** 「왜 그렇게 고쳤나」는 `docs/DECISIONS.md` 가 절 번호로 들고, 릴리즈 노트는 태그와 PR 본문이 든다 |

★ GitHub 저장소 Description 과 Topics 는 저장소 설정에 있고 파일이 아니다 —
`fire-lane` · `소방차 진입 가능성 판정 · 골목 폭 산출 · 출동 내비` 로 적는다.
그것을 여기 적는 이유는 **파일이 아닌 것은 아무 검사도 못 들기 때문**이다.

강제자  `tests/test_doc_style.py`(다섯 번째 문서 금지 — 위 넷을 안 넣는 쪽을 든다) · `tools/env_check.py` · `.gitleaks.toml`(SECURITY.md 가 약속한 것을 실제로 막는다)
