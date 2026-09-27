# web — 배포되는 사이트

★ 2026-09-22. 옛 GIS 지도(`index.html` 의 패널 · `js/` 30모듈 · `style.css`)를 걷어냈다.
관제 화면(내비 앱의 `?view=ops`)이 그 기능 — 검색 · 출동 모드 · 기준 차량 · 판정 범례 ·
도달 불가 · 구간 툴팁 · CCTV 반경 · 정사영상 — 을 넘겨받았다.

**서버는 없다.** 파이썬 파이프라인이 `web/data/` 에 정적 JSON 을 쓰고, 앱이 `../data/` 로
그것을 읽는다. 그 파일들이 곧 둘 사이의 계약이다(`tests/test_contract.py`).

## 무엇이 있나

| 경로 | 내용 |
|---|---|
| `index.html` | 사이트 입구. `navi/?view=ops`(관제)로 넘긴다. 외부 자원 없음 · 상대 주소 |
| `navi/` | 내비 · 관제 앱(React + TypeScript + Vite · maplibre-gl 6). 배포에서는 빌드본이 이 자리에 앉는다(`.github/actions/build-navi`) |
| `data/` | 생성물. 파이프라인(`publish_*.py`) 산출. 손으로 고치지 말 것 |
| `config.js` | **파이프라인 설정**이다. `publish_navi.py` 가 판정색 · 지형을, `publish_fleet.py` 가 편성을 정규식으로 읽는다. 화면은 이 파일을 직접 안 싣는다 |
| `assets/vehicles/profiles.json` | 차종 치수 정본. `publish_fleet.py` 가 회전반경을 읽는다 |
| `proposal.html` | 기획서 뷰어. **PDF 를 띄운다**(2026-09-24 · DECISIONS §231) — `tools/proposal_pdf.py` 가 `docs/proposal.docx` 를 구워 `proposal.pdf` 를 내고, 쪽수 · 본문 · 판정 수치 · 그림 수를 대조해야 배포된다. `.docx` 원본도 같이 옮겨 내려받기로 남긴다 |
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
