# 밤샘 보고 — 2026-11-01

## ① 관문
지시문 §2 에 따라 사람이 22:3x 에 통과시켰으므로 다시 돌리지 않았다.

## ② 배치 1 — 문서·시험
고친 곳
- README: needs_cv 278 → 283
- PLAN: #60 의 unknown 447 → 454, 521 → 531. 711·713 줄은 `#63` 행 번호를 폐기된 blocked 수로 오인해 `stale-ok` 를 달았다
- proposal: 판정 넷 · 영상판정 불가 531 · 23,137m · 39.7% · band 214 · single 10 · survey 77
- MASTER: 소방청 지정 251 · 필문대로205번길 7.72/-0.28 · 절대편차 합 10.96 · unknown 사유 band 214 / single 10
- DECISIONS: 42559 · 43451 은 과거 기록이라 값은 두고 `stale-ok` 만 달았다
- tests: test_classify_published · test_rule12_sim 을 275/283/192/531 판으로

pytest: 수정 직전 실측 빨강 12 → 문서 수치 3건을 고친 뒤 **9**.
(지시문의 「18」과 맞지 않는다. 첫 시도는 `git stash` 가 끼어들어 오염돼 버렸다.)

남은 9 (판정·잠금에 걸린 것이라 건드리지 않았다)
- test_widthcross × 2 — 현재 측정값: 모순 **11** (고정 13) · Mann-Whitney **p = 0.00106**. 시험은 건드리지 않았다. 사람이 정한다.
- test_nfa_compare · test_r3 — 판정 폐포 22 (기록 20). 늘어난 둘은 `seg/share.py` · `seg/walkcarve.py` (Zm56)
- test_layering — 같은 두 파일이 `DOMAIN` / `NOT_DOMAIN` 어디에도 없다. 순수 여부는 사람이 적는다
- test_ratchet — 래칫 실측 불일치 (`ratchet.py --write` 는 사람 몫)
- test_evalset — 중앙값 규칙 62 구간이 57 로 재현된다
- test_fix_door · test_handrolled(`seg/width.py` 에 글자 폭 어림 표식 사본)

## ③ 배치 2 — 하지 않았다
C 열 열 행 중 닫은 행 0. 행마다 코드와 대조해야 하는데 무인 실행에서 근거 없이 닫지 않기로 했다.
- #30 은 raw 재취득이 필요해 외부 접근이 든다
- #95 는 문안에 「clear 290」이 남아 있어 새 판정으로 다시 재야 한다

## ④ 배치 3 — 하지 않았다
일방통행 변환기는 쓰지 않았다. `oneway_dir_known` 은 건드리지 않았다(1 유지).

## ⑤ 멈춘 자리
- 배치 2·3 은 시간·검증 비용 때문에 시작하지 않았다.
- 밤 도중 `git stash` + `pop` 을 한 번 했다 (복원 확인함, 기존 stash 1건은 건드리지 않았다).

## 인계문(part-nav 계보, 코드 수정 여섯)에 대한 메모
이 트리(part/infra)에서 읽기 전용으로만 대조했다.
- 1번 `WMAX_CAP` 검사: `seg/width.py` 에 `WMAX_CAP` 은 있으나 `"cap"` 반환이 보이지 않는다 — 이미 다른 형태로 손봐진 듯하다. 확정은 못 했다.
- 4번 `ngii1k.py`: §283-2 · §289-1 주석으로 `sys.argv[1]` 처리가 이미 고쳐져 있다.
- 5번: `web/js/layers/mask.js` 가 이 트리에 없다.
- 3번(보도 차감 배선)은 이 트리가 이미 붙였다. 2·6번은 판정 수 변경 또는 운영 DB 가 필요해 하지 않았다.

## ⑥ 사람이 칠 명령
재잠금이 필요해진 것 없음. 폐포 22 와 widthcross 를 받아들이려면 재잠금 절차가 따라온다.
