# web — 배포되는 사이트

★ 2026-09-22. 옛 GIS 지도(`index.html` 의 패널 · `js/` 30모듈 · `style.css`)를 걷어냈다.
관제 화면(내비 앱의 `?view=ops`)이 그 기능 — 검색 · 출동 모드 · 기준 차량 · 판정 범례 ·
도달 불가 · 구간 툴팁 · CCTV 반경 · 정사영상 — 을 넘겨받았다.

**서버는 없다.** 파이썬 파이프라인이 `web/data/` 에 정적 JSON 을 쓰고, 앱이 `../data/` 로
그것을 읽는다. 그 파일들이 곧 둘 사이의 계약이다(`tests/test_contract.py`).

## 무엇이 있나

| 경로 | 내용 |
|---|---|
| `index.html` | **배포에서는 관제 화면 그 자체다**(§258) — `build-navi` 가 내비 빌드본을 여기 앉히고 `window.__FL_VIEW="ops"` 를 박는다. 저장소에 커밋된 판은 빌드본이 없는 로컬용 대역이고 `navi/?view=ops` 로 넘긴다. 외부 자원 없음 · 상대 주소 |
| `navi/` | 내비 · 관제 앱(React + TypeScript + Vite · maplibre-gl 6). 배포에서는 빌드본이 이 자리에 앉는다(`.github/actions/build-navi`) |
| `data/` | 생성물. 파이프라인(`publish_*.py`) 산출. 손으로 고치지 말 것 |
| `fonts/` | 지도 글자(`**/*.pbf`). **오프라인에서 도로 이름이 사라지지 않는 이유**다(§312) — 숫자·로마자 5범위 119KB. `cd web/navi && npm run glyphs` 가 뽑고 `--check` 가 데이터에 새 글자가 들어왔는지 본다. 글꼴 원본은 `web/navi/fonts-src/`(SIL OFL 1.1) |
| `404.html` | 오타 난 주소가 흰 화면이 되지 않게(§313). `naviweight` 가 존재를 든다 |
| `config.js` | **파이프라인 설정**이다. `publish_navi.py` 가 판정색 · 지형을, `publish_fleet.py` 가 편성을 정규식으로 읽는다. 화면은 이 파일을 직접 안 싣는다 |
| `assets/vehicles/profiles.json` | 차종 치수 정본. `publish_fleet.py` 가 회전반경을 읽는다 |
| `proposal.html` | 기획서 **화면**이고 **생성물**이다(2026-10-06 · DECISIONS §425) — 정본은 `docs/proposal.md` 고 `tools/build_proposal.py` 가 아래 와꾸로 굽는다. **손으로 고치지 말 것.** `--check` 가 정본 지문과 제목 · 표 · 그림 수를 대조하고, 로컬에서는 경고 · 배포 경로에서는 막는다. 화면 머리의 내려받기 두 줄은 **제출본**(`proposal.pdf` · `proposal.docx`)으로 간다 — 둘 다 `.gitignore` 이고 배포 직전에 `tools/proposal_pdf.py` · `tools/stage_pages.py` 가 만든다(DECISIONS §231) |
| `proposal.template.html` | 그 화면의 **와꾸**. 내용은 한 글자도 없고 자리표시자 일곱을 든다. **손으로 고치는 것은 이 파일이다** — 스타일을 고치는 손과 조립(`build_proposal.py`)을 고치는 손을 가른다 |
| `proposal/fig/` | 기획서 그림 24장. 상류 `docs/proposal.docx` 에서 `tools/migrate_proposal.py` 가 **한 번** 꺼냈다 — 글(`docs/proposal.md`)과 같이 들어온 같은 반입물이라 같이 커밋한다 |
| `workflow.html` | 협업 방침. `tools/render_workflow.py` 가 `playbook.html`(틀)로 만든다 |
| `playbook.html` | 위의 틀. 배포에는 안 싣는다 |

소유(리뷰)의 정본은 `.github/CODEOWNERS` 다.

## 실행

```bash
cd web/navi && npm run dev          # 개발 — vite 가 ../data 도 같이 준다
# 또는 배포 모양 그대로:
cd web/navi && npm run build && cd ../.. && uv run python tools/serve.py
```

`file://` 로 열면 안 된다. `fetch()` 가 CORS 로 막힌다.

## 값을 바꿀 때

판정 임계값(3.0 / 7.0 / 25.0)의 **정본은 `src/firelane/seg/params.py`** 다.
`config.js` 의 같은 숫자는 사본이고 `tests/test_declaration_sync.py` 가 같은지를 본다.
판정색을 바꾸려면 `config.js` 의 `verdict` 를 고치고 파이프라인을 다시 돌린다 —
`navi_graph.json.style` 로 실려 앱에 닿는다.
