# gis 브랜치 초기 세팅

## 1. 브랜치 생성 · 초기 푸시 (GIS 담당, 1회)

```bash
git checkout -b gis
git add -A
git commit -m "gis: 전자지도 승인분 반영 + 세그먼트 판정 + 표출 지도

- sources.yaml: boundary_emd / building / building_entrance / hydrant_point 추가
- src/etl/segments.py: 노딩(끝점투영 0.5m) → 폭 밴드 → 진입판정
- src/etl/publish_web.py: web/data 경량 사본
- web/: MapLibre + deck.gl(interleaved) + V-World
- tests/test_contract.py: GIS↔UI 계약 검증 8종
- 세그먼트 641개 확정 (기존 문서의 '222'는 근거 없음)"
git push -u origin gis
```

## 2. 보호 규칙 (GitHub 웹)

`Settings > Branches > Add branch protection rule`

- Branch name pattern: `gis`
- ☑ Require a pull request before merging
- ☑ Require review from Code Owners  ← **이걸 켜야 CODEOWNERS가 동작한다**
- ☑ Require status checks to pass → `contract`
- ☐ Allow force pushes (끄기)

이걸 안 켜면 `.github/CODEOWNERS`는 그냥 텍스트 파일이다.

## 3. UI 담당 (지혜님)

```bash
git fetch origin
git checkout -b ui/base origin/gis
cd web && python -m http.server 8000
```

이후는 `docs/HANDOFF_UI.md` 참조.

---

## 왜 락이 3중인가

| 층 | 막는 것 | 한계 |
|---|---|---|
| `.gitignore` | `data/raw` 커밋 | 이미 있음 |
| `CODEOWNERS` | GIS 코어 무단 수정 | 리뷰 강제일 뿐, 승인하면 통과 |
| **계약 테스트** | **구조 파괴** | **실제로 막는 건 이것** |

CODEOWNERS는 "누가 봐야 하는가"를 정하고, 계약 테스트는 "무엇이 깨지면 안 되는가"를
정한다. 후자가 본체다. 좌표계가 5186으로 나가거나 `verdict`에 새 값이 생기면
CI가 즉시 잡는다.

## 락을 거는 대상은 값이 아니라 스키마다

폭 값은 **미검증 상태(`width_verified: false`)**다. D-25 레이저 실측 후 바뀐다.
값을 얼리면 거짓말이 되고, 스키마를 얼리면 UI가 안 깨진다.

```
얼린다:  좌표계 · 필드명/타입 · verdict 어휘 5종 · seg_id 불변성
바뀐다:  width_min_m · width_max_m · 각 구간의 verdict · route_usage
```

실측 후 갱신은 이 순서다. **UI 코드는 손대지 않는다.**

```bash
python src/etl/segments.py       # 폭 재산출
python src/etl/publish_web.py    # web/data 갱신
pytest tests/test_contract.py    # 계약 유지 확인
```

## 데이터를 저장소에 넣는 기준

| 경로 | git | 이유 |
|---|---|---|
| `data/raw/` | ✗ | 2.5GB. `.gitignore` |
| `data/processed/*.gpkg` | ✗ | 재생성 가능 |
| `data/processed/segments.geojson` | ✓ | UI 입력. 재생성에 raw가 필요하다 |
| `data/processed/_manifest.json` | ✓ | 재현성 기록 |
| `web/data/` | ✓ | UI 담당이 raw 없이 작업할 수 있어야 한다 |

**핵심은 지혜님이 2.5GB raw 없이도 지도를 띄울 수 있어야 한다는 것.**
그래서 `web/data/` 1.2MB는 커밋한다.
