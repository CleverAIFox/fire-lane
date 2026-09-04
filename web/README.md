# web — 동명동 진입판정 지도

MapLibre GL JS 5 + deck.gl 9 (interleaved) + V-World.

## 실행

```bash
uv run python tools/serve.py        # 캐시 없는 개발 서버
# http://localhost:8000
```

`index.html` 을 더블클릭하면 안 된다. `file://` 에서는 `fetch()` 가 CORS 로 막힌다.

## 파일 구조

한 파일에 다 넣으면 두 사람이 같은 줄을 고쳐 충돌한다. 계층으로 나눴다.

| 파일 | 주인 | 내용 |
|---|---|---|
| `index.html` | 공동 | 뼈대. 패널 마크업. 거의 안 바뀐다 |
| `style.css` | **@marscoolcat** | 색·간격·타이포·레이아웃 |
| `config.js` | **공동** | 색상표·임계값·마커 형상·카메라 |
| `js/main.js` | **공백** | 부트스트랩. 초기화 순서만 |
| `js/data.js` | **공백** | ★ 데이터 접근 단일 지점 |
| `js/layers/` | **공백** | 레이어·판정 렌더링 |
| `js/icons/` | 공동 | 표지판 캔버스 그림 |
| `js/ui/` | 공동 | 범례·검색·테마·토글·미니맵 |
| `data/` | 생성물 | `publish_web.py` 산출. 손으로 고치지 말 것 |

★ **`공백` 은 소유자가 이탈해 비었다는 뜻이다.** `CODEOWNERS` 에는 아직
`@AIMasterFox` 로 적혀 있고 GitHub 은 그 줄을 조용히 무시한다 — 리뷰가 걸리는
것처럼 보이지만 안 걸린다(`MASTER §8` · `PLAN #79`).

**UI 작업은 `style.css` 와 `config.js` 만 만지면 된다.** `js/layers/` 를 건드릴 일이
생기면 그건 로직 문제이므로 GIS 담당에게 알릴 것.

## 출동 모드 · 미니맵

`@marscoolcat` 기여(faf9774). 파일 분리 과정에서 새 구조로 옮겼다.

| 기능 | 위치 |
|---|---|
| 출동 모드 토글 · FAB 버튼 | `index.html` + `style.css` + `js/ui/toggles.js` |
| 미니맵 (줌 16↑ 표시, 뷰박스·현위치 동기화) | `js/ui/minimap.js` + `style.css` |
| 소화전 물결 (출동 모드에서만) | `js/layers/hydrants.js` |
| 출동 시 통과 구간 강조 · 나머지 흐림 | `js/layers/segments.js` + `config.js` |

조정값은 `config.js` 의 `dispatch` 와 `minimap` 에 있다.

```js
dispatch: { clearWidthScale: 1.6, dimAlpha: 102, pulseMs: 1200 }
minimap : { showFromZoom: 16 }
```

소화전 물결은 지면에 링이 퍼지고 그 위에 3D 기둥이 서는 구조다.
원본은 2D 원 마커 위에 그렸는데, 마커가 3D 로 바뀌면서 링만 지면에 남겼다.

## 값을 바꿀 때

판정 임계값(3.0 / 7.0 / 25.0)의 **정본은 `src/firelane/seg/params.py`** 다.
`config.js` 의 같은 숫자는 화면 설명용 사본이라 바꿔도 판정은 안 바뀐다.
파이프라인을 먼저 고치고 `config.js` 를 맞출 것.

## V-World 배경

`config.js` 의 `vworld.enabled` 를 `true` 로 바꾼다. 그 전에 V-World 에
서비스 URL(`http://localhost:8000`) 을 등록해야 한다. `&domain=` 이 등록 문자열과
정확히 같아야 타일이 나온다.

## 지형

`config.js` 의 `terrain.exaggeration` 으로 기복을 조절한다. 1.0 이 실제 비율이다.

**공개DEM 90m 를 8배 보간한 표현용 값이다.** 판정에는 쓰지 않는다.
90m 격자는 골목 20개를 한 픽셀로 덮으므로 구간별 경사 산출이 불가능하다.


## 모듈 구조 (2026-08-21)

`app.js` 1,260줄을 `web/js/` 29개 모듈로 쪼갰다. 원문 로직은 그대로다.

```
js/
  main.js            부트스트랩. 순서만 정한다. 로직을 여기 쓰지 마라
  data.js            ★ 데이터 접근 단일 지점. SOURCE() 한 줄이 정적↔API 전환
  config-access.js   전역 CONFIG 를 만지는 유일한 곳
  state.js           공유 가변 상태. import 없음(그래프 뿌리)
  map.js  basemap.js  verdict.js  dom.js
  icons/   size · truck · ops119 · hydrant · cctv
  layers/  segments · mask · hydrants · markers · coverage · signs · poi
  ui/      tooltip · search · legend · stats · minimap · theme · toggles
```

검사 3종이 CI 에서 돈다:

| 도구 | 잡는 것 |
|---|---|
| `tools/js_graph_check.mjs` | ESM 문법 · 미해결 import · 순환 의존 |
| `tools/web_boot_check.mjs` | 실제 부팅. 모듈 최상단 부수효과 등 |
| `tests/test_contract.py` | DOM id · 토글 · 데이터 파일 대조 |

★ `node --check` 는 ES 모듈 문법 오류를 **못 잡는다**. `.js` 를 CommonJS 로
읽다 `export` 에서 실패하면 조용히 넘어간다(실측: `export const a=1;
const b={{{;` → 종료코드 0). 그래서 `js_graph_check` 가 `--input-type=module`
로 다시 본다. `node --check` 만 믿으면 검사가 죽은 채 초록불이 뜬다.
