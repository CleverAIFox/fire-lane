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
#: ★ 2026-10-08 (DECISIONS §436 · PLAN #140). **여섯째가 늘었다.**
#:   앞 다섯은 전부 「폭이 어떠하다」 또는 「표본이 얇다」를 말한다. 폭도 표본도
#:   충분한데 **대장이 반박해** 확정을 못 주는 자리를 부를 낱말이 없었고, 그래서
#:   화면이 그 구간을 「표본이 하나라서」(`no_cctv_single`)라고 **거짓으로** 설명했다.
#:   빈칸은 「모른다」를 말하지만 틀린 낱말은 **아는 척한다**(§369).
# ★ 2026-10-23. **일곱째 `needs_survey`** — 채택에서 밀린 소스가 clear 를 반박하는데(`width_min_any_m < TRUCK`) 영상으로 풀 수도 없는 자리.
#   CCTV 가 없으면 「영상 보면 풀린다」(needs_cv)가 **거짓 약속**이다. 그래서 회색이되 사유는 「현장에서 재야 안다」이다.
REASONS = ("ledger_disputes",
           "no_cctv_narrow", "no_cctv_thin", "no_cctv_band",
           "no_cctv_single", "needs_survey", "width")

#: `VERDICT_RULE` 중 **이 함수가** 실행하는 줄의 번호. 전부다.
#: 강제자 `tests/test_classify.py::test_covers_every_declared_rule` 가
#: `VERDICT_RULE` 의 길이와 이것을 댄다 — 규칙을 한 줄 더 적고 여기
#: 구현을 안 하면 운다.
IMPLEMENTS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)

#: 대장폭이 판정에 드는 문턱. `VERDICT_RULE[1]` 의 숫자다.
#: ★ 이름을 준 이유 — 종전에는 `main()` 안에서 `TRUCK` 을 그대로 썼고,
#:   그래서 「노면 하한」과 「대장 확정 문턱」이 같은 숫자라는 것이 우연인지
#:   뜻인지 읽을 수 없었다. 뜻이다: 두 근거가 **같은 질문**("트럭이 지나는가")
#:   에 독립으로 답해 일치할 때만 확정한다(§3-3).
LEDGER_BLOCK_M = TRUCK

#: clear 문턱. `wmin >= TRUCK + 2*PARK`. 표시용 사본이 `web/config.js` 에 있다.
CLEAR_M = TRUCK + 2 * PARK

#: 규칙 [11] — 구간 안에서 폭이 이 배수 이상 변하면(`wmax / wmin`) 대표폭이 없다. **유도된 수가 아니다**(2026-10-23 · Zm19 ·
#: DECISIONS §564). 분포를 보고 정했다: `width_max_m` 이 있는 `clear` 132개의 비 분포는 중앙 1.29 · 75% 1.81 · 90% 2.95 이고, 2.5 는 그
#: 75% 와 90% 사이의 둥근 수다(2.0 이면 30개 · 3.0 이면 14개가 거둬진다). 사례 DM01576(입구 12.3m · 안쪽 2.4~3.2m)은 3.27 이다.
#: ★ `width_max_m` 은 1,281 중 606구간에만 있다 — **없는 구간은 이 규칙이 안 걸린다.**
SPREAD_MAX = 2.5


def classify(
    *,
    wmin: float | None,
    wmax: float | None,
    nreg: int | None,
    road_bt: float | None,
    length_m: float,
    cctv_dist: float,
    wmin_any: float | None = None,
    wsym: float | None = None,
    clear_med: float | None = None,
    spread_max: float | None = SPREAD_MAX,
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
    # ★ Zm12 ① (DECISIONS §554). 이 관문은 **두 조건이 모두 참일 때만** 건다 — 짧아도 폭이 하나라도 나오면(wmin 이 있으면)
    #   지나간다. 3m 미만 6개(0.8 ~ 2.6m)가 전부 표본 1개의 wmin 을 가져 이 관문을 지났다. `MIN_SEG_LEN` 을 읽는 곳은
    #   여기 말고 width.py 의 두 줄(짧은 조각 교차부 제외 해제 · 정규 표본 0개 폴백 불신)과 report.py 의 스키마 한 줄이다.
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
    # ── VERDICT_RULE[7] · 대장이 반박하면 회색, 사유는 그 반박이다 ────
    # ★ 2026-10-08 (DECISIONS §436 · PLAN #140). **CCTV 관문보다 앞이다.**
    #   「대장이 반박한다」는 카메라 유무와 **무관한 사유**다. 뒤에 두면
    #   `no_cctv_single` 이 먼저 걸려 거짓 낱말이 계속 이긴다 — `greycheck` 가
    #   그 분기를 「거짓」으로 세고 있었고, 그 수가 이 줄의 근거다.
    #
    # ★ **판정은 안 움직인다.** 조건에 맞는 구간은 공개본 1,281 중 아홉이고
    #   여덟이 `clear`(여기 안 온다) · 하나가 이미 `unknown` 이다. `needs_cv`
    #   중 이 조건에 맞는 것은 **0 이다** — 그래서 이 줄이 강등시키는 구간이 없다.
    #   그 하나(`DM02946`)의 사유가 `no_cctv_single` 에서 이 낱말로 바뀐다.
    #
    # ★ 두 근거가 **반대로** 말할 때만 걸린다. 노면 실측은 clear 문턱을 넘고
    #   대장 명목폭은 차단 문턱 미만이다 — §3-3 이 「두 근거가 독립으로 일치할
    #   때만 확정한다」고 적었고, 여기는 그 거울이다: **어긋나면 확정하지 않는다.**
    reason = None
    if (v == "needs_cv"
            and wmin is not None and wmin >= CLEAR_M
            and road_bt is not None and road_bt < LEDGER_BLOCK_M):
        reason = "ledger_disputes"
        v = "unknown"
    elif v == "needs_cv" and cctv_dist > CCTV_RANGE:
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

    # ── VERDICT_RULE[8] · 채택에서 밀린 소스가 clear 를 반박하면 clear 를 거둔다 ─────────────────
    # ★ 2026-10-23. `wmin_any` 는 **소스 무관** 최솟값(`width_min_any_m`)이다. 구간 폭(`wmin`)은 채택된 한 소스의 표본만으로
    #   내므로 다른 소스가 소방차 폭 미만을 쟀어도 clear 가 나갈 수 있었다. 과소판정은 출동을 늦추지만 **과대판정은 소방차를
    #   못 들어가는 길로 보낸다.** needs_cv 로 보내지 않는다 — CCTV 가 없으면 「영상 보면 풀린다」가 거짓 약속이다.
    #   CCTV 유효범위 안이면 영상으로 풀 수 있으니 needs_cv, 밖이면 unknown(needs_survey).
    # ★ **이 규칙은 판정을 움직인다**(골든 재잠금은 사람이 한다). clear 만 건드린다 — blocked · needs_cv 는 그대로다.
    # ★ 감사 N7 (Zm20). **[8] ⊂ [10]** — `wmin_any < TRUCK`(3.0) 이면 `wmin_any < CLEAR_M`(7.0) 이고, 두 갈래의 행선지(needs_cv/source_conflict ·
    #   unknown/needs_survey)가 같다. 그래서 [10] 이 켜진 뒤 [8] 이 혼자 바꾸는 판정은 없다. **코드는 지우지 않는다** — `VERDICT_RULE` 번호와
    #   `IMPLEMENTS` 가 [8] 을 선언하고, [10] 의 문턱을 올려 정할 때 [8] 이 다시 따로 설 수 있다.
    if v == "clear" and wmin_any is not None and wmin_any < TRUCK:
        if cctv_dist <= CCTV_RANGE:
            v, reason = "needs_cv", "source_conflict"
        else:
            v, reason = "unknown", "needs_survey"

    # ── VERDICT_RULE[9] · 중심선이 폴리곤 경계에 붙어 있으면 그 wmin 은 도로 중앙의 폭이 아니다 ──────────────
    # ★ 2026-10-23 (Zm4). `wsym` 은 채택 표본의 대칭폭 `2·min(left, right)` 중 최솟값이다. **전면 도입이 아니다** — 대칭폭을 판정에 쓰면
    #   blocked 가 192 → 583 으로 3배가 된다(정상 도로도 중심선이 조금 치우치면 죽는다). `clear` 만 건드리고 3.0 미만인 구간만 내린다.
    #   DM01820(2순환로 · 대장 35m)은 한쪽이 7.6cm 인데 wmin 이 넓어서 clear 였다. [8] 과 같은 갈래(CCTV 안 → needs_cv · 밖 → needs_survey).
    if v == "clear" and wsym is not None and wsym < TRUCK:
        if cctv_dist <= CCTV_RANGE:
            v, reason = "needs_cv", None
        else:
            v, reason = "unknown", "needs_survey"

    # ── VERDICT_RULE[10] · 소스 하나라도 CLEAR(7.0) 미만이라 말하면 「양쪽 주차해도 통과」를 주장할 수 없다 ────────────────
    # ★ 2026-10-23 (Zm6 · DECISIONS §548). `clear` 는 **「양쪽 주차해도 통과」(`CLEAR_M` = TRUCK + 2·PARK = 7.0)라는 주장**이다. 소스 하나가 그 선 미만이라 말하면
    #   그 주장을 할 수 없다 — **어느 폭 축이 맞는지와 무관하다**(축 논쟁 밖의 규칙이다).
    # ★ 문턱이 왜 `TRUCK`(3.0)이 아니라 `CLEAR_M`(7.0) 인가: 3.0 은 「소방차가 아예 못 지난다」이고 이미 0개다(규칙 [8] 이 10개를 거뒀다 — 지금 clear 중 any < 3.0 은 0).
    #   7.0 은 `clear` 가 하는 주장의 기준선이고 **그 주장을 못 하게 되는 선**이다. 중간값(4 · 5 · 6m)을 쓸 근거가 없다 — clear 416 중 any < 4: 2 · < 5: 7 · < 6: 15 이고
    #   어느 값도 소방 기준이나 측정이 고른 수가 아니다(근거 없는 상수를 더 만들지 않는다 · MASTER §16-2). `PARK`/`TRUCK` 에서 나온 `CLEAR_M` 를 그대로 쓴다.
    # ★ 갈래는 [8] · [9] 와 같다: CCTV 19m 안이면 영상으로 풀 수 있으니 `needs_cv`(사유 `source_conflict`), 밖이면 `unknown`(`needs_survey`).
    # ★ 2026-10-23 (Zm19 · DECISIONS §564). **소스에서 축으로 넓혔다**: 내접원 **중앙값**(`clear_med`)이 7.0 미만이어도 거둔다. `clear_min` ·
    #   대칭폭(`wsym`)은 이 자리에 안 쓴다 — 둘 다 `2·min(좌,우)` 라 중심선 편심에 전부 노출된다(제봉로 DM00115: 법선 26.53 · c_med 23.80 ·
    #   대장 30.0 으로 셋이 맞는데 c_min 만 1.15). 법선(`wmin`) 자체는 `clear` 의 전제(≥ 7.0)라 이 조건에서 비어 있다. blocked 에는 안 닿는다.
    if v == "clear" and ((wmin_any is not None and wmin_any < CLEAR_M) or (clear_med is not None and clear_med < CLEAR_M)):
        if cctv_dist <= CCTV_RANGE:
            v, reason = "needs_cv", "source_conflict"
        else:
            v, reason = "unknown", "needs_survey"

    # ── VERDICT_RULE[11] · 구간 안에서 폭이 `SPREAD_MAX` 배 넘게 변하면 대표폭이 없다 ─────────────────────────────────────────────
    # ★ 2026-10-23 (Zm19 · DECISIONS §564). DM01576(동명로98번길): 사용자가 네이버 거리재기로 입구 12.3m · 안쪽 2.4~3.2m 를 확인했다. 우리 값은
    #   wmin 8.1 · wmax 26.48 · 측량 3.9 · 대장 4.0 이고 유효표본 4개뿐이며 앞 6m 는 교차부로 빠졌다. 행선지는 [8]~[10] 과 같다(새 상수 없음).
    # ★ **`wmax` 가 있는 구간에만 걸린다**(606/1,281). 없으면 건드리지 않는다 — 「없다」를 「균일하다」로 읽지 않는다.
    if (v == "clear" and spread_max is not None and wmax is not None and wmin is not None
            and wmin > 0 and wmax / wmin >= spread_max):
        if cctv_dist <= CCTV_RANGE:
            v, reason = "needs_cv", "source_conflict"
        else:
            v, reason = "unknown", "needs_survey"

    return v, reason
