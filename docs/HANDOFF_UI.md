# UI 인수인계 — 동명동 진입판정 지도

작성 2026-08-11 · GIS 담당 오창준

---

## 30초 안에 띄우기

```bash
git clone -b gis <레포주소> fire-lane
cd fire-lane/web
python -m http.server 8000
```

`http://localhost:8000`

**`index.html`을 더블클릭하면 빈 화면이 뜬다.** 브라우저가 `file://`에서
`fetch()`를 막기 때문이다. 반드시 서버로 띄울 것. Node를 쓴다면
`npx serve` 나 `npx http-server` 도 된다.

설치할 것은 없다. MapLibre와 deck.gl은 CDN에서 온다.

---

## 이 지도가 보여주는 것

동명동 골목 641개 구간을 소방차가 지나갈 수 있는지 판정한 결과다.

| 색 | verdict | 뜻 |
|---|---|---|
| 파랑 | `clear` | 양쪽에 주차가 있어도 통과 |
| 초록 | `likely_clear` | 한쪽 주차까지는 여유 |
| 주황 | `needs_cv` | 도면만으로는 결론이 안 남. 영상판정 대상 |
| 빨강 | `blocked` | 차가 없어도 통과 불가 |
| 회색 | `unknown` | 폭을 산출할 재료가 없음 |

**선 굵기는 출동 통행량이다.** 119안전센터 두 곳(대인·지산)에서 동명동 건물
출입구 358개까지 최단경로를 전부 뽑아, 각 구간이 몇 번 밟히는지 센 값이다.
641개 중 495개만 실제로 쓰인다. 굵은 선이 소방 동선의 뼈대다.

---

## 건드려도 되는 것 / 안 되는 것

### 자유롭게

`web/index.html` 전부. CSS, 레이아웃, 인터랙션, 카메라, 애니메이션.
색·굵기 매핑도 바꿔도 된다.

### 절대 안 되는 것

**`web/data/` 안의 파일.** 전부 파이썬 스크립트 생성물이다. 손으로 고쳐도
다음 실행에 덮어써진다. 값이 이상해 보이면 고치지 말고 알려줄 것.

---

## 값은 바뀐다. 구조는 안 바뀐다.

지금 폭 값은 **미검증**이다. `width_verified: false`가 그 뜻이다.
레이저 거리계 실측(D-25)이 끝나면 값이 바뀌고, 일부 구간의 `verdict`도 바뀐다.

그때 UI를 다시 만들지 않으려면 아래 세 가지만 지키면 된다.

**1. 숫자가 아니라 `verdict` 문자열로 분기할 것**

```js
// 이렇게 (값이 바뀌어도 안 깨진다)
if (p.verdict === "blocked") ...

// 이러면 안 된다 (임계값이 바뀌면 전부 틀어진다)
if (p.width_max_m < 3.0) ...
```

임계값 3.0 / 5.0 / 7.0은 GIS 쪽 내부 규칙이다. UI에 복사해 두지 말 것.

**2. 색 매핑은 `VERDICT` 객체 한 곳에만 둘 것**

`index.html` 상단에 이미 있다. 여기만 고치면 전체에 반영된다.
여러 군데 흩뿌리면 나중에 하나를 놓친다.

**3. `verdict`는 이 5개가 전부다**

새 값이 추가되면 `tests/test_contract.py`가 CI에서 막는다.
그래도 방어적으로 기본 색(회색)을 두는 편이 안전하다.

### 계약으로 보장되는 것

| 항목 | 보장 |
|---|---|
| 좌표계 | `EPSG:4326` 고정 |
| 필드명·타입 | 고정 |
| `verdict` 어휘 | 5종 고정 |
| `seg_id` | 불변 키. 데이터가 갱신돼도 같은 구간은 같은 ID |
| `width_min_m` ≤ `width_max_m` | 항상 참 |

이건 희망사항이 아니라 **CI에서 자동 검증**된다.
`.github/workflows/contract.yml` → `tests/test_contract.py`.
GIS 쪽이 이 계약을 깨면 머지가 막힌다.

---

## 데이터 필드

`web/data/segments.geojson` — 641개 LineString

| 필드 | 타입 | 설명 |
|---|---|---|
| `seg_id` | str | 불변 키 (`DM00042`) |
| `verdict` | str | 판정 5종 |
| `width_min_m` | float\|null | 노면폭 하한 |
| `width_max_m` | float\|null | 담~담 상한. **대로에서는 null** |
| `route_usage` | int | 출동 최단경로 사용 횟수 |
| `length_m` | float | 구간 연장 |
| `width_verified` | bool | 현재 전부 false |
| `midpoint_fallback` | bool | 정상 측정이 아님 (98개) |
| `inherited` | bool | 인접 구간에서 상속 (67개) |

`width_max_m`이 `null`인 것은 오류가 아니다. 큰 도로는 건물이 40m 밖이라
담~담을 잴 수 없고, 그런 구간은 노면폭만으로 이미 판정이 끝난다.

`midpoint_fallback` / `inherited`가 true인 165개는 정상 산출이 아니다.
발표 자료에 수치를 쓸 때는 구분해서 표기할 것. 툴팁에 이미 표시돼 있다.

`web/data/buildings.geojson` — 2,085동, `h`(높이 m) = 층수 × 3.3.
`web/data/hydrants.geojson` — 공개된 소화전. **동명동은 1개뿐이다.**
관할 588개 중 31개만 공개된 상태이고, 이 자체가 발표 논거다. 버그가 아니다.

---

## V-World 배경으로 바꾸기

지금은 CARTO 다크 타일로 뜬다. `index.html` 상단:

```js
const USE_VWORLD = false;   // ← true
```

바꾸기 전에 V-World(vworld.kr)에 서비스 URL을 등록해야 한다.
`&domain=` 파라미터가 등록한 문자열과 **정확히** 일치해야 타일이 나온다.
로컬이면 `http://localhost:8000`을 등록한다.

WMTS 축 순서는 `{z}/{y}/{x}`다. `{z}/{x}/{y}`로 쓰면 타일이 어긋나서
지도가 미묘하게 밀린다. 코드에 이미 맞춰져 있으니 손대지 말 것.

---

## 지도 범위는 고정돼 있다

동명동 약 1.04 × 1.04 km 밖으로는 **이동도 축소도 되지 않는다.** 4중으로 막았다.

| 수단 | 효과 |
|---|---|
| `maxBounds` | 카메라 팬 한계. 서울까지 끌고 갈 수 없다 |
| `minZoom: 14.2` | 축소 한계. 지구본이 안 나온다 |
| 타일 소스 `bounds` | 범위 밖 타일을 아예 요청하지 않는다 |
| 마스크 레이어 | 동 경계 밖을 어둡게 덮는다 |

**UI 작업 범위가 동명동을 넘을 일이 구조적으로 없다.** 화면에 안 보이는 곳을
디자인할 필요가 없다는 뜻이다.

범위 값은 `web/data/view.json` 에 있고, 이 파일은 `publish_web.py` 가 동 경계
데이터에서 계산해 낸다. **`index.html` 에 좌표를 하드코딩하지 말 것.**
경계가 바뀌면 자동으로 따라간다.

마스크가 거슬리면 좌측 패널 `동 경계 밖 가리기` 토글로 끌 수 있다.
끄더라도 `maxBounds` 는 살아 있어서 범위 밖으로는 못 나간다.

## 렌더링 구조

| 레이어 | 렌더러 |
|---|---|
| 건물 3D | MapLibre `fill-extrusion` |
| 세그먼트 | deck.gl `GeoJsonLayer` (interleaved) |
| 소화전·안전센터 | MapLibre `circle` |

deck.gl은 `MapboxOverlay({interleaved: true})`로 MapLibre의 WebGL2 컨텍스트에
직접 그린다. 그래서 건물 뒤로 지나가는 도로가 제대로 가려진다.
`interleaved`는 maplibre-gl 3 이상에서만 동작하므로 CDN 버전을 내리지 말 것.

3D 변환 작업을 확장할 때도 이 구조를 유지하는 게 좋다. deck.gl을 별도
캔버스(overlaid)로 빼면 z-오클루전이 깨져서 건물을 뚫고 선이 보인다.

---

## 작업 흐름

```
gis        ← GIS 담당이 데이터·파이프라인을 올린다
 └ ui/*    ← UI 작업 브랜치. 여기서 작업하고 gis로 PR
```

1. `git checkout gis && git pull`
2. `git checkout -b ui/작업이름`
3. 작업 후 push → `gis`로 PR
4. CI(계약 검증) 통과 확인
5. `web/index.html`만 건드렸다면 승인 후 머지

`web/data/`나 `src/etl/`을 건드린 PR은 CODEOWNERS 때문에 GIS 담당 승인이
필요하다. 실수로 커밋했을 때 잡으라고 걸어둔 것이다.

---

## 막히면

| 증상 | 원인 |
|---|---|
| 빈 화면, 콘솔에 CORS | `file://`로 열었다. 서버로 띄울 것 |
| 지도는 뜨는데 선이 없다 | `web/data/` 없음. GIS 담당에게 요청 |
| 타일이 회색 | V-World `domain` 미등록. `USE_VWORLD=false`로 되돌릴 것 |
| 건물이 납작하다 | 줌 15.2 미만이다. 확대할 것 |
| 선이 건물을 뚫고 보인다 | `interleaved: false`로 바뀌었다 |

수치가 이상해 보이면 고치지 말고 물어볼 것. 대부분은 버그가 아니라
데이터의 실제 상태이고, 그 자체가 이 프로젝트의 결과다.
