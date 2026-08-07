# 적용 방법 — 2026-08-06 야간 갱신

이 zip 은 `.git` 과 정사영상 원본(1.2GB)을 제외한 프로젝트 전체다.

## 1. 로컬 삭제 전

```bash
git status                              # 커밋 안 한 변경분 확인
ls ~/Downloads/*정사영상_2025_*.tif      # 원본 4장 확인 ★
```

## 2. clone → 덮어쓰기

```bash
cd ~/Downloads
git clone https://github.com/woongtopia/fire-lane.git fire-lane-new
cd fire-lane-new
git checkout 오창준

unzip ~/Downloads/fire-lane-full.zip -d /tmp/fl
cp -r /tmp/fl/fire-lane/. .
```

## 3. 정사영상 원본 넣기 (수동)

```bash
cp ~/Downloads/*정사영상_2025_*.tif data/raw/ortho/
```

자리와 안내는 `data/raw/ortho/README.md` 참조.

## 4. 환경 + 재생성

```bash
uv sync
uv run python src/etl/crop_ortho.py     # tfw/prj 생성 + 모자이크
```

출력 원점이 `data/georef/*.tfw` 와 일치하면 정상.

## 5. 커밋 전 확인 ★

```bash
git status --short | grep -E "\.tif|\.venv|digitalmap"
```

**아무것도 안 나와야 한다.** `.gitignore` 에 `data/raw/` 와 `data/processed/*.tif` 가
들어 있다. 1.2GB 가 커밋되면 히스토리에서 제거할 수 없다.

## 6. 푸시

```bash
git add -A
git commit -m "feat(gis): 도로폭 소스 확정 및 222구간 전수 재산출

- 도로폭 주소스를 수치지도 도로경계면(NF_A_A01000)으로 확정
- 최협소 골목 14구간은 실폭도로 폴백 (커버리지 221/222)
- 판정 재계산: 69개 변경 (YELLOW→RED 38)
- 정사영상 4도엽 지오레퍼런싱 복원 (EPSG:5186, 도곽+50m)
- road_bt/road_lt 폐기, 지적도 제거
- 현장 실측 5곳 기록 (data/survey/)
- 문서: PROJECT_MASTER 2판, GIS_ROADMAP 신규"

git push origin 오창준
```

---

## 신규/변경 파일

### 문서
| 파일 | 내용 |
|---|---|
| `docs/PROJECT_MASTER.md` | **마스터 2판.** §0 변경 요약부터 읽을 것 |
| `docs/GIS_ROADMAP.md` | **GIS 고도화 플랜.** Phase 1~4, DL 도입 경로 |

### 코드
| 파일 | 역할 |
|---|---|
| `src/etl/crop_ortho.py` | 정사영상 지오레퍼런싱 복원 + 동명동 모자이크 |
| `src/etl/extract_width.py` | 도로폭 추출 (소스 독립, 이중 검증) |

### 데이터
| 경로 | 내용 |
|---|---|
| `data/processed/road_width.csv` | **222구간 폭 + 재분류 결과** |
| `data/survey/` | 현장 실측 5곳. **유일한 정답지. 반드시 커밋** |
| `data/georef/` | 정사영상 4도엽 원점 (.tfw/.prj) |
| `data/raw/digitalmap/sheet037~048/` | 수치지도 4도엽 |
| `data/raw/ortho/` | 메타데이터 XML + README (원본 TIFF 는 수동 배치) |

## 폐기

- 지적도 관련 계획 전부 (V-World 지적도 API 미사용)
- `road_bt` 를 최종 폭으로 쓰는 로직 → 대조용 컬럼으로만 보존
- `road_lt` 컬럼 → 222행 중 59행 오류, 사용 금지

## 다음

`docs/GIS_ROADMAP.md` §3 우선순위 참조.
1순위는 Phase 1 (road_lt 재계산 → 그래프 구축 → 다익스트라).
