# 일일 작업 흐름

브랜치는 `gis` 하나다. 각자 작업 브랜치를 파서 PR 로 합친다.

```
gis ─────────────────────── 정본. 여기가 항상 동작해야 한다
 ├ gis/*   오창준 (@AIMasterFox)   데이터·판정·경로
 └ ui/*    우지혜 (@marscoolcat)   화면·3D
```

## 하루 시작

```bash
git checkout gis
git pull
git checkout -b ui/오늘작업이름     # 또는 gis/오늘작업이름
```

## 하루 끝 — 푸시를 권장한다 (강제 아님)

```bash
git add -A
git commit -m "ui: 판정 색상 대비 조정"
git push -u origin ui/오늘작업이름
```

GitHub 에서 `gis` 로 PR 을 연다. 미완성이면 **Draft PR** 로 열어두면 된다.

**왜 매일 푸시하나**

- 로컬에만 있는 작업은 없는 것과 같다. 노트북이 죽으면 그대로 날아간다.
- 상대가 뭘 하고 있는지 보인다. 4달짜리 프로젝트에서 이게 제일 크다.
- CI 가 매번 돌아 계약이 깨졌는지 즉시 안다. 일주일 뒤에 알면 못 고친다.

완성해야 푸시하는 게 아니다. **동작하는 지점마다 푸시한다.**

## 자동으로 도는 것

| 워크플로 | 시점 | 하는 일 |
|---|---|---|
| `contract` | `gis` 로 push·PR | 계약 8종 검증. 깨지면 머지 차단 |
| `지도 배포` | `gis` 의 `web/**` 변경 | GitHub Pages 갱신 |

CI 가 데이터를 다시 만들지는 **않는다.** `data/raw` 2.5GB 가 저장소에 없기 때문이다.
파이프라인은 오창준 로컬에서만 돈다.

```bash
uv run python src/etl/ingest.py        # raw → processed (15종)
uv run python src/etl/segments.py      # 노딩 → 폭 → 판정 (641)
uv run python src/etl/publish_web.py   # → web/data
uv run pytest tests/test_contract.py   # 계약 확인
```

이 4줄을 돌린 뒤 `web/data` 를 커밋하면 지혜님이 `git pull` 만으로 새 판정을 받는다.

## 지도 URL

`Settings > Pages > Source: GitHub Actions` 를 한 번 켜면
`gis` 에 푸시할 때마다 아래가 자동 갱신된다.

```
https://woongtopia.github.io/fire-lane/
```

로컬 서버를 띄우지 않아도 되고, `file://` 로 열어 빈 화면을 보는 사고도 없다.

## 충돌이 나면

거의 안 난다. 파일이 갈려 있다.

| 경로 | 주인 |
|---|---|
| `src/etl/`, `sources.yaml`, `data/` | 오창준 |
| `web/index.html` | 우지혜 |
| `web/data/` | 생성물. 아무도 손으로 안 고친다 |

`web/data/` 에서 충돌이 나면 손으로 풀지 말 것.

```bash
git checkout --theirs web/data/     # gis 쪽을 취한다
uv run python src/etl/publish_web.py  # 또는 재생성
```

## 커밋 메시지

```
gis:  데이터·파이프라인·판정
ui:   화면·스타일·인터랙션
docs: 문서
fix:  버그
```

한 줄이면 충분하다. 무엇을 왜 바꿨는지만 남기면 된다.
