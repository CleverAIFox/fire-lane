<!--
  PR 템플릿. 리뷰어와 LLM 이 같은 것을 읽는다.

  ★ 세 번째 절이 이 템플릿의 본체다. "어디를 보라" 가 없으면 사람은
    전부를 안 보고 도장을 찍는다. 한 곳을 지목하면 그 한 곳은 실제로 본다.
    승인이 형식이 되는 것을 규율이 아니라 형식으로 막는다.
-->

## 무엇을 · 왜

<!-- 한두 줄. 커밋 메시지 접두사와 맞춘다: gis / cv / api / ui / docs / fix -->


## 리뷰어가 볼 곳 — **한 곳만**

<!--
  파일:줄 하나를 지목한다. "전체 확인 부탁" 은 확인 안 한다는 뜻이다.
  예)  src/firelane/seg/width.py:212  — 횡단선 간격을 0.5 → 0.25 로
-->


## 산출물이 바뀌는가

- [ ] 안 바뀐다
- [ ] 바뀐다 → `tools/golden.py lock` 재잠금 + 아래에 전후 값

<!-- 바뀌면 무엇이 몇 → 몇 으로. 판정 수 · 폭 · 구간 수 -->


## 계약을 건드리는가

- [ ] 안 건드린다
- [ ] `src/contracts/` · `test_contract.py` · `web/config.js` 를 건드린다
      → **해당 파트 전원에게 리뷰 요청.** 여기가 파트 간 유일한 접점이다

---

<details>
<summary>충돌이 났을 때 (펼치기)</summary>

```
uv.lock       git checkout --theirs uv.lock && uv lock     손으로 풀지 않는다
web/data/     git checkout --theirs web/data/ 후 재생성    생성물이다
그 외          아침에 git merge origin/dev 를 빼먹은 것이다
```

LLM 에 붙일 때는 위 세 절을 그대로 넘긴다 — 무엇을 바꿨고, 어디를 봐야 하고,
산출물이 움직였는가. 그 셋이 충돌 해결에 필요한 전부다.
</details>

<details>
<summary>체크리스트 (펼치기)</summary>

- [ ] `git config core.hooksPath .githooks` 를 이 기계에서 한 번 쳤다
- [ ] 아침에 `git merge origin/dev` 를 했다
- [ ] base 브랜치가 맞다 — 개인 → `part/*` · 파트 → `dev` · 릴리즈 → `main`
- [ ] CI 초록불. 빨간불이면 **실패 메시지를 끝까지 읽었다** (고치는 법이 그 안에 있다)
</details>

