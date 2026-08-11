# Fire-Lane

동명동 소방차 진입 판정 시스템 · 전남광주통합특별시 동구

골목 1,266구간의 실제 통행 가능 폭을 산출해 소방차가 지나갈 수 있는지 판정하고,
**판정할 수 없는 이유까지** 지도에 표시한다.

**지도** https://woongtopia.github.io/fire-lane/

---

## 문서는 셋뿐이다

| 문서 | 성격 |
|---|---|
| [`docs/MASTER.md`](docs/MASTER.md) | **현재 상태.** 판정 결과 · 데이터 · 용어 · UI 인수인계 · 협업 · 패치 적용 |
| [`docs/PLAN.md`](docs/PLAN.md) | **남은 일.** 설계 결정 · 미구현 항목 · 담당 공백 |
| `docs/기획서_Fire-Lane.docx` | 대외 제출용 |

`sources.yaml` 은 데이터 정본이다. 기계가 읽으므로 손으로 고칠 때 주의할 것.

**문서를 더 만들지 않는다.** 흩어지면 아무도 최신을 모른다.
완료된 일은 PLAN 에서 지우고 MASTER 에 결과를 쓴다.

---

## 실행

```bash
uv sync
uv add rasterio pillow                  # 최초 1회

export FIRE_LANE_RAW="/경로/data/raw"   # 원본을 저장소 밖에 둘 때
uv run python src/etl/normalize_raw.py <다운로드폴더>   # 원본 배치
uv run python src/etl/pipeline.py                       # 전체 파이프라인

cd web && uv run python -m http.server 8000
```

`index.html` 을 더블클릭하면 안 된다. `file://` 에서는 `fetch()` 가 CORS 로 막힌다.

### 파이프라인

```
ingest → segments → terrain → ortho → publish → 계약 테스트 → 기대값 대조
```

```bash
uv run python src/etl/pipeline.py --check          # 실행 없이 상태만
uv run python src/etl/pipeline.py --from segments  # 그 단계부터
uv run python src/etl/pipeline.py --only terrain ortho
```

**단계를 하나씩 손으로 치지 마라.** 순서가 중요하고 빠뜨리기 쉽다.

---

## 구조

```
sources.yaml              데이터 정본. ingest 가 이것만 읽는다
src/etl/
  paths.py                경로 정본. FIRE_LANE_RAW 환경변수
  normalize_raw.py        다운로드 폴더 → data/raw 명명규칙 배치
  pipeline.py             단일 진입점
  ingest.py               raw → processed (19종)
  segments.py             노딩 → 폭 → 판정 (1,266)
  terrain.py              공개DEM → Terrain-RGB 타일
  ortho.py                항공정사영상 → 배경 타일 (25cm)
  publish_web.py          → web/data
tests/test_contract.py    계약 12종. CI 가 검증한다
web/
  index.html              뼈대                     공동
  style.css               색·간격·타이포            @marscoolcat
  config.js               색상표·임계값·마커·카메라  공동
  app.js                  로직·레이어              @AIMasterFox
  data/                   생성물. 손으로 고치지 말 것
```

**`data/raw` 는 저장소에 두지 않는다.** 심링크도 쓰지 않는다.
심링크를 git 이 추적했다가 원본 2GB 가 두 번 소실된 적이 있다(2026-08-11, 08-12).
`FIRE_LANE_RAW` 환경변수로 위치만 지정한다.

---

## 지금 상태

```
세그먼트     1,266   (동명동 641 + 119안전센터 접근 회랑)
판정        도면상 통과 227 · 판정 보류 139 · 도면상 불가 67 · 판정 불가 833
기준        소방청 2025 골든타임 대책 + 2026-08-06 현장 답사 (통과 하한 3.0m)
외부 검증    소방서 지정 구간과 동명동 2건이 -0.30m · +1.34m 로 일치
데이터      19종 · 2.0GB
```

**폭 값은 아직 미검증이다**(`width_verified: false`). 레이저 실측 후 바뀐다.
값은 바뀌어도 필드와 `verdict` 어휘는 안 바뀐다. 계약 테스트가 그것을 보장한다.
