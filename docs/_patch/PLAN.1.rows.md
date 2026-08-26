| 31 | `web/data` 타일 1,445장이 추적된다 | 🟡 | `.gitignore` 40행 `!web/data/**` 가 벡터뿐 아니라 정사영상 1,423장 · 음영기복 22장까지 포함한다. `ortho.py` · `terrain.py` 가 재생성하며 UI 작업에 원본을 요구하지 않는다. 저장소 36.0MB 중 23.6MB. §8-5 |
| 32 | 봉인 베이스라인이 전량 복사다 | 🟡 | `data/baseline/*` 세 벌이 `segments.geojson` 을 통째로 담는다. `segments.schema.json` 은 계층까지 합쳐 다섯 벌이며 전부 해시가 다르다. 태그 + `golden/segments.fingerprint.json` 으로 대체 가능한지 판정한다. #30 과 함께 처리한다 |
| 33 | 계층 간 스키마 드리프트 | 📄 | `data/processed` 만 `cov_ngii` · `cov_ngii1k` · `cov_silpok` · `merge_why` · `merged_n` 를, `web/data` 만 `seg_no` 를 가진다. 2026-08-26 에 판정 규칙·임계값은 강제자로 막았으나 **필드 집합 차이는 아직 대조하지 않는다** |
| 34 | `tools/` 에 조사 스크립트가 상주한다 | 🟡 | `clearance_probe` · `corner_probe` · `jijeok_probe` · `lanes_probe` · `route_probe` 는 조사가 끝났고 `naver_check` · `naver_join` · `naver_page` 는 한 작업이 셋으로 갈려 있다. 릴리스 도구(`ship` · `golden` · `verify`)와 같은 자리에 있어 무엇을 실행해야 하는지 구분되지 않는다 |
| 35 | `DECISIONS §1~§9` 가 삭제된 파일을 적는다 | 🟡 | 아홉 절 전부 이미 지운 일회성 스크립트의 부검이며 이력은 git 이 보관한다. 절 번호는 자산이므로 비우지 않고 같은 시제의 다른 내용으로 채운다(MASTER §0-2) |
| 36 | 문서의 죽은 경로 참조 | 🟡 | `MASTER` 가 `data/processed/nfa_compare.json` 을, `PLAN §7` 이 `data/processed/eval.json` 을 가리키나 두 파일 모두 추적되지 않는다. 경로 참조 유효성에는 강제자가 없다 |
| 37 | 문서 세 곳이 데이터 관리를 적는다 | 🟡 | `README 데이터 계층` · `MASTER §18` · `PLAN §8`. 정본을 `MASTER §18` 로 두고 나머지는 참조만 남긴다. 지금은 `test_doc_style.py` 가 그 정합을 대신 붙잡고 있다 |
| 38 | `sources.yaml` AUTO 블록 재생성 확인 | 🟡 | 2026-08-26 에 `inventory` 를 `data/interim/inventory.json` 으로 뺐다(2,986 → 1,551줄). `python -m firelane.inventory` 를 raw 가 붙은 기계에서 한 번 돌려 산출 형식이 같은지 확인한다. `at` 은 2026-08-17 자로 9일 낡았다 |
| 39 | 계층 밖 경로 조립 잔존 | 📄 | 2026-08-26 에 `golden` · `baseline` 을 계층으로 등재하고 `paths.GOLDEN` · `paths.BASELINE` 을 신설했다. `pipeline.py` 가 아직 `ROOT / "data/golden/..."` 를 문자열로 조립한다. 상수로 바꾼다 |
