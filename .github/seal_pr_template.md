<!--
  봉인 PR 본문 — tools/merge_batch.sh 의 A-0 이 `{HEAD}` 를 채워 쓴다.
  ★ 2026-09-21 (DECISIONS §210). 처음에는 본문을 한 줄로 썼다. CI 의
    `pr_body_check.py` 가 「리뷰어가 볼 곳」과 체크박스를 요구하므로 25초 만에
    빨개졌고(PR #141), 봉인은 part/infra 에 못 들어갔다. **자동 절차가 여는 PR 도
    사람이 여는 PR 과 같은 관문을 지난다** — 그래서 템플릿을 채운다.
  ★ `tests/test_seal_survives_squash.py` 가 이 파일을 채워 `pr_body_check.check()`
    에 넣어 본다. 템플릿이 관문과 갈리면 거기서 운다.
-->

## 무엇을 · 왜

`seal` — 릴리즈 A-0 이 스쿼시 뒤 `part/infra` 머리 `{HEAD}` 에서 찍은 봉인이다.
봉인이 가리키는 커밋은 이미 `part/infra` 에 있으므로 이 PR 을 스쿼시해도 사라지지 않는다
(DECISIONS §209). `tools/dms.py ancestry` 가 다음 verify 에서 그것을 잰다.

## 리뷰어가 볼 곳 — **한 곳만**

data/dms/SEAL.json — `commit` 이 `{HEAD}` 이고 `denominator` 가 직전 봉인보다 늘지 않았는가.

## 산출물이 바뀌는가

- [x] 안 바뀐다
- [ ] 바뀐다 → `tools/golden.py lock` 재잠금 + 아래에 전후 값

## 계약을 건드리는가

- [x] 안 건드린다
- [ ] `src/contracts/` · `test_contract.py` · `web/config.js` 를 건드린다
