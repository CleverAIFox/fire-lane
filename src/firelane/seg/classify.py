#!/usr/bin/env python3
"""
seg/classify.py — 판정 사슬의 **실행 정본**.

── 왜 이 파일이 생겼나 (2026-09-29 · DECISIONS §303) ──────────────
`seg/geom.py` 의 `VERDICT_RULE` 은 스스로를 「판정 규칙의 문언 정본」이라
적는다. 그 말은 참이었다 — **문언은** 한 집에 있었다. 그런데 **실행이
둘이었다.**

    VERDICT_RULE[0]   wmax < 3.0 -> blocked              geom.verdict()
    VERDICT_RULE[1]   ROAD_BT < 3.0 -> blocked           segments.main()  ★
    VERDICT_RULE[2]   wmin >= 7.0 + 표본 2+ -> clear      geom.verdict()
    VERDICT_RULE[3]   wmin >= 7.0 + 표본 1 -> needs_cv    geom.verdict()
    VERDICT_RULE[4]   wmin 있음 -> needs_cv               geom.verdict()
    VERDICT_RULE[5]   그 외 -> unknown                    geom.verdict()
    VERDICT_RULE[6]   CCTV 밖 -> unknown                  segments.main()  ★

★ 둘은 1,041줄 `main()` 안에, 노딩·병합·도로명·CCTV 인덱스 사이에 끼어
  있었다. 결과가 셋이다 —

  ① **배달 전에 규칙 변경을 잴 수 없었다.** 규칙 하나를 건드리면 호수
     전체를 다시 돌려야 판정 이동이 보인다. 호수가 없는 곳에서는 아예
     못 잰다. PLAN §1 #4 가 「전후를 재라」고 적은 것이 그래서 반년째
     미결이었다.
  ② `geom.verdict()` 의 결과를 **판정이라고 읽는 자리가 생겼다.** 그것은
     7줄 중 5줄일 뿐인데 이름이 `verdict` 다. 실제로 `blocked` 191건 중
     **131건(69%)은 `verdict()` 가 내지 않는다** — `main()` 의 두 줄이
     낸다.
  ③ 그래서 산출물 스키마의 필드 서술이 규칙과 어긋난 것을 아무도 못
     봤다(§305). `road_bt_m` 을 「판정에는 쓰지 않는다」고 적어둔 채로
     그 열이 blocked 의 69% 를 만들고 있었다.

이 파일은 로직을 **한 줄도 바꾸지 않는다.** `main()` 의 두 조각을 여기로
옮겨 붙였을 뿐이다. 동일함의 증거는 주장이 아니라 실측이다 —
`tests/test_classify_published.py` 가 공개본 1,281행의 `verdict` ·
`unknown_reason` 을 이 함수로 재현한다(1,281/1,281 · 불일치 0).

★ `verdict()` 는 지우지 않는다. `VERDICT_RULE` 다섯 줄의 순수 분기로
  남기고, 이 파일이 그것을 부른다. 지우면 그 다섯 줄만 보는 기존 시험
  스물여섯이 전부 이 파일로 옮겨와야 하고, 그 이사는 이 고침의 내용이
  아니다. 두 집이 아니라 **한 집과 그 방**이다 — `classify()` 만이 판정을
  낸다고 말할 수 있고, `verdict()` 를 판정이라고 부르는 자리는 이제
  없다(강제자 `tests/test_classify.py::test_verdict_alone_is_not_a_verdict`).

── 이 함수가 안 보는 것 ────────────────────────────────────────
`wmin` · `wmax` 를 **만드는** 일은 여기 없다(`seg/width.py`). 폭 소스
우선순위·커버율 자격·교차부 제외는 전부 그 위쪽이다. 여기는 폭이
정해진 뒤의 분기만 든다. 그래서 커버율 자격의 구멍(§306)은 이 함수로
잴 수 없다 — 잴 수 없다고 적는 것이 이 파일의 범위다.
"""
from __future__ import annotations

from firelane.seg.geom import verdict
from firelane.seg.params import CCTV_RANGE, MIN_SEG_LEN, PARK, TRUCK

#: 판정 어휘. `fragment` 는 **중간 상태**이며 산출물에 나가지 않는다 —
#: `segments.main()` 이 인접 상속을 시도한 뒤 실패하면 unknown/width 로
#: 떨어뜨린다. 스키마의 `verdict` 열거에 fragment 가 없는 것이 맞다.
VERDICTS = ("blocked", "clear", "needs_cv", "unknown")
INTERIM = ("fragment",)

#: `unknown_reason` 어휘. 스키마가 이 순서로 서술한다.
REASONS = ("no_cctv_narrow", "no_cctv_thin", "no_cctv_band",
           "no_cctv_single", "width")

#: `VERDICT_RULE` 중 **이 함수가** 실행하는 줄의 번호. 전부다.
#: 강제자 `tests/test_classify.py::test_covers_every_declared_rule` 가
#: `VERDICT_RULE` 의 길이와 이것을 댄다 — 규칙을 한 줄 더 적고 여기
#: 구현을 안 하면 운다.
IMPLEMENTS = (0, 1, 2, 3, 4, 5, 6)

#: 대장폭이 판정에 드는 문턱. `VERDICT_RULE[1]` 의 숫자다.
#: ★ 이름을 준 이유 — 종전에는 `main()` 안에서 `TRUCK` 을 그대로 썼고,
#:   그래서 「노면 하한」과 「대장 확정 문턱」이 같은 숫자라는 것이 우연인지
#:   뜻인지 읽을 수 없었다. 뜻이다: 두 근거가 **같은 질문**("트럭이 지나는가")
#:   에 독립으로 답해 일치할 때만 확정한다(§3-3).
LEDGER_BLOCK_M = TRUCK

#: clear 문턱. `wmin >= TRUCK + 2*PARK`. 표시용 사본이 `web/config.js` 에 있다.
CLEAR_M = TRUCK + 2 * PARK


def classify(
    *,
    wmin: float | None,
    wmax: float | None,
    nreg: int | None,
    road_bt: float | None,
    length_m: float,
    cctv_dist: float,
) -> tuple[str, str | None]:
    """구간 하나의 (판정, 회색 사유).

    인자는 전부 **산출물에 실재하는 열**이다. 그래서 파이프라인을 돌리지
    않고 공개본만으로 이 함수를 다시 먹일 수 있다 — `tools/verdictsim.py`
    가 그것으로 규칙 변경의 전후를 잰다.

    `length_m` 은 **반올림하지 않은** 길이를 받는다. 파이프라인은
    `g.length` 를 넘기고, 공개본으로 되먹이는 자리는 `round(g.length, 1)`
    을 넘긴다 — 두 값이 갈리는 것은 길이가 정확히 3.0 근처인 구간뿐이고
    현재 그런 구간은 없다(공개본 1,281 중 3m 미만 6건, 전부 2.9 이하).
    `verdictsim` 이 이 근사를 머리에 적는다.
    """
    # VERDICT_RULE[0] · [2] · [3] · [4] · [5]
    v = verdict(wmin, wmax, nreg)

    # 길이 3m 미만인데 폭을 아예 못 낸 것은 교차로 파편이다. 판정이 아니라
    # **인접 상속 대상**이라는 표시다. 여기서 내는 것은 중간 상태다.
    if length_m < MIN_SEG_LEN and wmin is None:
        v = "fragment"

    # ── VERDICT_RULE[1] · 도로대장 명목폭에 의한 확정 ──────────────
    # `verdict()` 는 blocked 를 wmax 로만 낸다. wmax(담~담)가 없으면 아무리
    # 좁아도 blocked 로 갈 길이 없다. 결손 496건 중 노면폭 3.0m 미만이
    # 160건이었고 그중 blocked 는 0 이었다(대조군 24%). 폭 0.38m 짜리가
    # 「CCTV 가 없어 판정 보류」로 표시됐다 — 결손이 관대한 쪽으로
    # 해석되고 있었다.
    #
    # 두 근거가 **독립으로 일치할 때만** 건다. 대장폭 단독으로 실측을
    # 뒤집지 않는다(§3-3). 실측이 3.0 이상인데 대장이 미만인 모순 6건은
    # 이 규칙에 걸리지 않는다.
    #
    # ★ CCTV 강등보다 앞이다. blocked 는 도면으로 확정되므로 카메라 유무와
    #   무관하다. 뒤에 두면 needs_cv → unknown 으로 먼저 내려가 이 규칙을
    #   비껴간다.
    if (wmax is None
            and (wmin is None or wmin < TRUCK)
            and road_bt is not None and road_bt < LEDGER_BLOCK_M):
        v = "blocked"

    # ── VERDICT_RULE[6] · 영상판정 불가에 의한 강등 ────────────────
    # needs_cv 인데 CCTV 사각이면 영상판정이 성립하지 않는다. 도면으로도
    # 확정 못 하고 영상으로도 확정 못 하므로 unknown 이다.
    # blocked / clear 는 도면만으로 확정되므로 CCTV 와 무관하다.
    #
    # ★ 회색 하나를 넷으로 가른 이유(2026-08-22) — unknown 352구간이 전부
    #   "no_cctv" 하나였다. 화면에서 한 덩어리로 보이지만 안에 성격이 다른
    #   넷이 있다. 판정은 전부 정당했고(오분류 0건) 화면이 「왜 회색인가」를
    #   설명하지 못한 것이었다. 색도 판정도 안 바뀌고 툴팁만 정확해진다.
    reason = None
    if v == "needs_cv" and cctv_dist > CCTV_RANGE:
        if wmin is None:
            reason = "width"
        elif wmin >= CLEAR_M:
            # wmin 은 clear 문턱을 넘었는데 표본이 하나라 보류된 것.
            # DM02825 사고(2.7m 구간이 표본 하나로 42.1m → clear)의 방어다.
            reason = "no_cctv_single"
        elif wmin < TRUCK:
            # 대장폭이 같이 좁으면 근거 둘, 아니면 하나다. 갈라 적는다 —
            # 근거 하나로 좁다고 말하는 것은 더 약한 주장이다(§3-3).
            reason = ("no_cctv_narrow"
                      if road_bt is not None and road_bt < LEDGER_BLOCK_M
                      else "no_cctv_thin")
        else:
            reason = "no_cctv_band"        # 3~7m. 주정차로 갈린다
        v = "unknown"
    elif v == "unknown":
        # 대장폭에 의한 확정은 위로 올렸다. 여기 남은 unknown 은 대장폭도
        # 없거나 3.0m 이상인 구간이다.
        reason = "width"

    return v, reason
