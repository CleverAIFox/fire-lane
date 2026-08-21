# 리팩터링 인수인계 — 2026-08-21

> `fire-lane-gis.zip` 기준. 두 단계를 했고 **각각 따로 검증할 수 있다.**

---

## 0. 받자마자 할 것 — 한 줄이다

```bash
fl                          # ★ 저장소로 먼저 이동. 홈에서 치면 전부 깨진다
bash tools/verify.sh        # 8단계 전부. 실패해도 끝까지 돌고 표로 보여준다
bash tools/verify.sh --fast # 파이프라인 전량(4분) 생략
```

`uv pip install -e .` 은 **치지 마라.** venv 를 따로 요구한다.
`[build-system]` 이 생겼으므로 `uv sync` 가 editable 로 알아서 깐다 —
스크립트 첫 단계가 그것이다. `uv.lock` 도 낡았으니 거기서 다시 풀린다.

스크립트가 확인하는 것:

| | 기대 |
|---|---|
| 의존성 동기화 (`uv sync`) | — |
| 패키지 import 28종 | 28/28 |
| 진입점 · cwd 독립성 | `/tmp` 에서도 동작 |
| pytest | 208 passed · 30 skipped |
| 계층 강제 | 14 passed |
| ruff | 참고만. 124 (원본 155) · **머지는 막지 않는다** |
| JS 문법·순환·import | 27개 모듈 · 순환 0 |
| JS 부팅 스모크 | 필수 레이어 16/16 |
| 파이프라인 전량 + golden | **1,101구간 판정 불변** |

마지막 하나는 사람이 봐야 한다 — 스크립트가 끝나면서 알려준다:

```bash
cd web && python -m http.server 8000
```

WebGL 렌더링은 스크립트가 못 본다. 지도가 실제로 그려지는지, 판정 색·표지판·
미니맵·검색이 눈으로 멀쩡한지는 직접 확인해야 한다.

깨지면 `web/app.js.orig` 가 분리 전 원본이다(보관용, 커밋 전 삭제).

---

## 1단계 — 패키지화

`src/etl/` → `src/firelane/`. 스크립트 더미를 패키지로 만들었다.

### 왜

`sys.path.insert` 가 **17군데**(src 14 · tests 3) 있었다. 여기서 전부 파생됐다.

| 증상 | 원인 |
|---|---|
| `# noqa: E402` 12개 | import 가 코드 뒤에 와야 했다 |
| `segments.py:69` 함수 안 `from guards import` | 순환을 못 피해 지역 import 로 땜질 |
| `seg/graph.py` 가 `paths.PROCESSED` 를 앎 | 순수 그래프 모듈이 인프라를 안다 |
| 테스트가 `sys.path` 조작 | 배포 형태와 다른 방식으로 import |

패키지가 되면 순환은 import 시점에 죽는다. 규약이 아니라 기계가 막는다.

### 한 일

- `sys.path.insert` 17개 삭제, `noqa: E402` 12개 소멸
- `ROOT = Path(__file__).resolve().parents[2]` **8중복** → `paths.ROOT` 단일정본
- `pyproject.toml` src-layout · `[project.scripts] fire-lane`
- `pipeline.py` 가 `python -m firelane.<단계>` 로 호출
- 미사용 의존성 9개를 `[api]` / `[vision]` extras 로 강등
- `seg/graph.py` 의 인프라 import 제거 → `access_corridor(..., out_dir=)` 주입
- **`tests/test_layering.py` 신설**

### `-m` 호출이 §5-5 의 구조적 해결이다

종전 `python src/etl/ingest.py` 는 **사람이 그대로 칠 수 있는 명령**이었다.
그러면 대장만 갱신되고 계보 기록이 빠져 다음 실행이 교착한다(08-21 에 세 번).
이제 단계 모듈은 파이프라인이 부르는 대상이지 사람이 치는 명령이 아니다.

### 계층을 테스트로 강제

이 저장소는 계보·판정·문서·인코딩을 전부 테스트로 강제하면서 **구조만
강제자가 없었다.** `test_layering.py` 가 넷을 본다.

- domain 모듈(`seg/params·geom·width·roadname·basisno·graph`)의 인프라 import 금지
- domain 모듈의 자기경로 파일쓰기 금지
- `sys.path` 해킹 재발
- 순환 의존

`seg/report.py` 는 예외로 명시했다 — 하는 일이 산출물 쓰기라 어댑터다.
`seg/` 아래 있을 뿐이고, 옮기는 것은 별건이다.

### 검증

| | 결과 |
|---|---|
| 전 모듈 import | 28/28 |
| pytest | 208 passed · 30 skipped |
| ruff | 155 → 124 |
| `/tmp` 에서 `fire-lane --check` | 동작 (cwd 의존 소멸) |

---

## 2단계 — app.js 분리

`web/app.js` 1,260줄 → `web/js/` **27개 모듈**. 원문 로직은 그대로다.

```
js/
  main.js            부트스트랩. 순서만 정한다 (87줄)
  data.js            ★ 데이터 접근 단일 지점
  config-access.js   전역 CONFIG 를 만지는 유일한 곳
  state.js           공유 가변 상태. import 없음(그래프 뿌리)
  map.js  basemap.js  verdict.js  dom.js
  icons/   size · truck · ops119 · hydrant · cctv
  layers/  segments · mask · hydrants · markers · coverage · signs · poi
  ui/      tooltip · search · legend · stats · minimap · theme · toggles
```

`map.on("load")` 880줄이 `main.js` 의 호출 목록으로 바뀌었다.
아이콘 캔버스 250줄은 **재타이핑하지 않고 원문을 잘라냈다.**

### 상태 공유

원본은 전체가 IIFE 하나라 `map`·`lightTheme`·`dispatchMode` 가 클로저였다.
모듈로 쪼개면 그 클로저가 사라진다. `state.js` 의 객체 `S` 에 모았다 —
`export let` 은 값 복사라 갱신이 전파되지 않지만 객체 필드는 참조가 공유된다.

### 검증

| 검증 | 결과 |
|---|---|
| ESM 문법 27개 | 통과 |
| 미해결 import · 순환 | 0 · 0 |
| 레이어·소스·DOM id | 원본 52 / 신본 52 · **누락 0 · 추가 0** |
| 이벤트 핸들러 | 원본 13 / 신본 13 · 누락 0 |
| 실제 부팅(jsdom) | 필수 레이어 16개 전부 생성 |

---

## 작업 중 잡은 것 — 6건

### ★ 1. `node --check` 는 ES 모듈 문법 오류를 못 잡는다

```
export const a = 1;
const b = {{{;              ← 명백한 문법 오류

node --check bad.js   → 종료코드 0   ★ 통과한다
node --check bad.mjs  → 종료코드 1
```

Node 가 `.js` 를 CommonJS 로 읽다 `export` 에서 실패하면 조용히 넘어간다.
**app.js 를 모듈로 쪼갠 순간 CI 의 JS 문법 검사가 무력화된다.**
`turn_restriction` 이 전국 44,125행을 읽고 `[OK]` 를 찍은 것과 구조가 같다 —
검사가 죽었는데 초록불이 뜬다.

작업 중 실제로 당했다. "문법 OK" 를 찍은 시점에 2개 파일이 깨져 있었다.
`tools/js_graph_check.mjs` 가 `--input-type=module` 로 다시 본다.

### ★ 2. `window.CONFIG` 는 undefined 다

`config.js` 는 `const CONFIG = {...}` 인데, 클래식 스크립트의 최상위
`const`/`let` 은 전역 **선언적 환경**에 들어가고 `window` 프로퍼티가
되지 않는다. `var` 와 함수 선언만 된다. node vm 실측:

```
const CONFIG = {a:1};  var LEGACY = 2;
typeof CONFIG             → "object"
typeof globalThis.CONFIG  → "undefined"   ★
typeof globalThis.LEGACY  → "number"
```

처음에 `window.CONFIG` 로 썼으면 **지도가 통째로 안 떴다.**
`config-access.js` 가 `typeof` 로 확인한다.

### 3. 모듈 최상단 부수효과 (부팅 테스트가 잡음)

`layers/signs.js` 최상단에 원본의 `placeSigns();` 가 딸려 들어왔다.
원본에서는 `map.on("load")` 본문이라 map 이 있었다. 모듈 최상단은 import
시점이라 `S.map` 이 null 이다. **문법 검사도 그래프 검사도 통과한다.**

### 4. 스코프를 넘어간 상수 (부팅 테스트가 잡음)

`icons/{truck,ops119,cctv}.js` 가 `SIGN_PX` 를 참조하는데 그건 `signs.js` 에
있었다. 원본은 같은 스코프였다. `icons/size.js` 로 정본을 만들었다.
`hydrant.js` 만 `192` 를 손으로 박아 쓰고 있었다 — 같은 값이라 안 드러났을
뿐, 갈라지면 `bake()` 의 `getImageData` 가 잘린다.

### 5. 원본에 죽은 코드 3개

`zOf()` · `width(f)` · `POPUP` — 전부 정의만 있고 호출부 0곳.
deck.gl 로 그리던 시절 잔해다. 옮기지 않았다. 죽은 코드를 모듈로 옮기면
다음 사람이 "쓰이나 보다" 하고 유지한다.

### 6. CI 의 ruff 가 한 번도 green 이 아니었다

원본에서 이미 155개 터진다. **지금 PR 을 열면 CI 가 빨간불이다.**
`ruff --fix` 로 46개는 즉시. `E702`(세미콜론 34개) · `E501` 은 판단 필요.

---

## 논의 필요 — DECISIONS 안건

**`sample_design.py` 의 FIELD 경로 불일치.** `paths.FIELD` 는
`FIRE_LANE_DATA` 가 있으면 SSD 인데, 이 스크립트는 저장소 안(`data/field`)에
써왔고 그 산출물이 커밋돼 있다(`sample_segments.csv`·`obs_points.csv`·
`fieldsheet.md`). 갈아끼우면 야장이 조용히 SSD 로 이사한다.
**패키지화는 동작을 안 바꾸는 작업이므로 종전 경로를 유지하고 주석만 달았다.**
어느 쪽이 정본인지는 정해야 한다.

---

## PR 순서 — 반드시 나눠라

위생 커밋 19개에 구조 변경을 섞으면 리뷰를 못 받는다.

1. **PR #1** — 기존 `chore/hygiene-basisno` (base 를 `gis` 로!). 지금 열어라
2. **PR #2** — 1단계 패키지화. `flgold` 통과 확인 후
3. **PR #3** — 2단계 app.js 분리. 지도 육안 확인 후
4. ruff 정리는 별 PR

`CODEOWNERS` 도 갱신했다 — `js/layers/` GIS 단독, `js/ui/`·`js/icons/` 공동.
파일 하나를 둘이 건드리던 구조가 사라져 충돌이 경로로 갈린다.
