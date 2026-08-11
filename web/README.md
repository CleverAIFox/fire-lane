# web — 동명동 진입판정 지도

MapLibre GL JS 5 + deck.gl 9 (interleaved) + V-World.

## 실행

```bash
cd web && python -m http.server 8000
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
| `app.js` | **@AIMasterFox** | 데이터 로딩·레이어·판정 렌더링 |
| `data/` | 생성물 | `publish_web.py` 산출. 손으로 고치지 말 것 |

**UI 작업은 `style.css` 와 `config.js` 만 만지면 된다.** `app.js` 를 건드릴 일이
생기면 그건 로직 문제이므로 GIS 담당에게 알릴 것.

## 출동 모드 · 미니맵

`@marscoolcat` 기여(faf9774). 파일 분리 과정에서 새 구조로 옮겼다.

| 기능 | 위치 |
|---|---|
| 출동 모드 토글 · FAB 버튼 | `index.html` + `style.css` + `app.js` |
| 미니맵 (줌 16↑ 표시, 뷰박스·현위치 동기화) | `app.js` + `style.css` |
| 소화전 물결 (출동 모드에서만) | `app.js` |
| 출동 시 통과 구간 강조 · 나머지 흐림 | `app.js` + `config.js` |

조정값은 `config.js` 의 `dispatch` 와 `minimap` 에 있다.

```js
dispatch: { clearWidthScale: 1.6, dimAlpha: 102, pulseMs: 1200 }
minimap : { showFromZoom: 16 }
```

소화전 물결은 지면에 링이 퍼지고 그 위에 3D 기둥이 서는 구조다.
원본은 2D 원 마커 위에 그렸는데, 마커가 3D 로 바뀌면서 링만 지면에 남겼다.

## 값을 바꿀 때

판정 임계값(3.0 / 7.0 / 25.0)의 **정본은 `src/etl/segments.py`** 다.
`config.js` 의 같은 숫자는 화면 설명용 사본이라 바꿔도 판정은 안 바뀐다.
파이프라인을 먼저 고치고 `config.js` 를 맞출 것.

## V-World 배경

`config.js` 의 `vworld.enabled` 를 `true` 로 바꾼다. 그 전에 V-World 에
서비스 URL(`http://localhost:8000`) 을 등록해야 한다. `&domain=` 이 등록 문자열과
정확히 같아야 타일이 나온다.

## 지형

`config.js` 의 `terrain.scale` 로 기복을 조절한다. 1.0 이 실제 비율이다.

**공개DEM 90m 를 8배 보간한 표현용 값이다.** 판정에는 쓰지 않는다.
90m 격자는 골목 20개를 한 픽셀로 덮으므로 구간별 경사 산출이 불가능하다.
