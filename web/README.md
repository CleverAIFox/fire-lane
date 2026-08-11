# web — 동명동 진입판정 지도

MapLibre GL JS 5 + deck.gl 9 (interleaved) + V-World 배경.

## 실행

```bash
cd web && python -m http.server 8000
# http://localhost:8000
```

`fetch()`로 `./data/*.geojson`을 읽으므로 **file:// 로 열면 CORS로 막힌다.** 반드시 서버로 띄울 것.

## V-World 배경 켜기

`index.html` 상단:

```js
const USE_VWORLD = false;   // ← true 로 바꾸면 V-World
```

기본값이 `false`이고 CARTO 다크 타일로 뜬다. V-World는 `&domain=` 파라미터가
등록 URL과 **문자열까지 정확히** 일치해야 타일이 나오므로, V-World 사이트에
`http://localhost:8000`을 먼저 등록한 뒤 `true`로 바꿀 것.
WMTS 축 순서는 `{z}/{y}/{x}`다. `{z}/{x}/{y}`로 쓰면 타일이 어긋난다.

## 데이터

`data/` 는 `src/etl/segments.py` 산출물의 경량 사본이다. 직접 수정하지 말 것.
갱신은 아래 순서.

```bash
python src/etl/ingest.py
python src/etl/segments.py
python src/etl/publish_web.py
```

## 렌더링 분담

| 레이어 | 렌더러 | 이유 |
|---|---|---|
| 건물 3D | MapLibre `fill-extrusion` | 네이티브가 가장 빠르다. 라이브러리 추가 불필요 |
| 세그먼트 | deck.gl `GeoJsonLayer` | 속성 기반 색·굵기와 피킹이 압도적으로 편하다 |
| 소화전·안전센터 | MapLibre `circle` | 단순 포인트 |

deck.gl은 `MapboxOverlay({interleaved:true})`로 MapLibre의 WebGL2 컨텍스트에
직접 그린다. 그래서 건물 뒤로 지나가는 도로가 제대로 가려진다.
`interleaved`는 maplibre-gl 3 이상에서만 동작한다.

## 넘길 때 지켜야 할 것

`data/segments.schema.json`의 `width_verified`가 **false**다.
`width_min_m` / `width_max_m`는 D-25 레이저 실측 후 값이 바뀐다.

- `verdict` **문자열**만 참조할 것. 임계값(3.0 / 5.0 / 7.0)을 UI 코드에 하드코딩하지 말 것.
- 색상 매핑은 `VERDICT` 객체 한 곳에만 둘 것. 값이 바뀌어도 여기만 고치면 된다.
- `midpoint_fallback` / `inherited`가 true인 구간은 정상 산출이 아니다. 결과 해석 시 구분할 것.
