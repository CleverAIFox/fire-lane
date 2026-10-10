#!/usr/bin/env python3
"""
test_sealcov.py — 봉인 **덮임**의 분모 셈이 맞는가.

── 왜 생겼나 (2026-10-04 · DECISIONS §384) ─────────────────────
`docseal` 은 절을 센다 — 「250/250 유효」. 그 수가 답하는 물음은 「찍은 절이
그대로인가」이고, 사람이 묻고 싶은 것은 **「코드의 어디까지 감사됐나」**다.
절 하나가 파일 스물을 지목할 수도 하나도 안 지목할 수도 있어서, 절을 아무리
채워도 **아무 절도 안 쳐다본 파일**은 그대로 남는다.

IN    tools/sealcov.py
OUT   없음 (검사)
PARAM 없음
밖    **절이 옳은가는 안 본다.** 지목한 절이 그 파일을 제대로 설명하는지는
      이 시험도 그 도구도 모른다. 드는 것은 분모 셈과 집합 셈이다.
"""
from __future__ import annotations

import docseal as D
import sealcov as S


def test_the_denominator_is_hand_written_code_only():
    den = S.denominator()
    assert den
    assert all(p.endswith(S.CODE_EXT) for p in den)
    assert not any(D._generated(p) for p in den), "생성물이 분모에 들었다"


#: **강제자 칸만으로** 덮인 파일 수. 「누가 지킨다」는 「읽고 판단했다」가
#: 아니므로 이 수는 **부풀림**이다 — 내려가는 쪽으로만.
#: ★ 2026-10-08 실측 39 → 2026-10-09 **38.** 이 판이 절을 더하며 산문이 경로를
#:   하나 더 집었다 — 칸만으로 덮이던 파일 하나가 **글로도 덮였다.** 내려가는
#:   쪽이라 받아 적는다(§441).
#: ★ 0 이 목표다. `PLAN #165` 가 그 길을 든다 — `covered()` 가 칸을 빼면
#:   덮임이 489 → 450 으로 내려가고, 그것은 래칫의 오르는 쪽을 거스르는
#:   큰 이사라 **그 판을 따로 받는다.**
ENFORCER_INFLATION = 38


def test_the_tool_counts_itself():
    """분모 규칙이 제 파일을 빼면 그 규칙은 신뢰할 수 없다."""
    assert "tools/sealcov.py" in S.denominator()


def test_covered_plus_gap_equals_the_denominator():
    s = S.survey()
    assert s["덮임"] + len(s["빈 곳"]) == s["분모"]
    assert 0 <= s["덮임"] <= s["분모"]


def test_the_group_counts_add_up_to_the_gap():
    s = S.survey()
    assert sum(s["묶음별 빈 곳"].values()) == len(s["빈 곳"])


def test_the_declared_ratchet_matches_what_the_tree_says():
    assert S.ratchet_values()["SEALED_FILES"] == S.SEALED_FILES


def test_the_enforcer_column_inflation_is_measured_not_assumed():
    """★ 강제자 칸이 덮임을 **얼마나 부풀리나.** 전제가 아니라 수다.

    ── 왜 바뀌었나 (2026-10-08 · DECISIONS §438-6 · PLAN #165) ─────
    종전 이 시험의 이름은 `..._does_not_count_as_coverage` 였고 산문은
    「`body(strip=True)` 가 그 칸을 뺀다」고 적었다. **거짓이다** — `strip` 은
    끝의 빈 줄을 떼는 깃발이고 강제자 칸과 상관이 없다. 실측: 칸이 경로를
    적는 절 778 중 **761 에서 그 글자가 본문 안에 있다.**

    ★ 그런데 **이 시험이 그 전제를 한 번도 안 물었다.** 단정은
      「덮임 < 분모 × 0.95」라는 **비율**이었고, 비율은 전제를 안 묻는다.
      §435 가 적은 「산문이 들지도 않는 강제자를 증인으로 세웠다」와 같은
      자리 — 여기서는 **산문이 제 단정과 다른 것을 증인으로 세웠다.**

    ★ 비율은 또 **고치면 울었다.** `#154` 가 열다섯을 읽어 489/514(95.1%)가
      되자 좋은 일이 빨간불로 찍혔다. 이 파일 아래쪽이 같은 교훈을 이미
      적고 있다(§411) — **같은 덫을 두 번 밟았다.**

    ★ 그래서 묻는 것을 바꿨다: 부풀림을 **세고 그 수가 늘지 않는가.**
      0 이 목표이고 `PLAN #165` 가 그 길을 든다. 수를 아는 채로 두는 쪽이
      모르고 초록인 쪽보다 낫다(§286).
    """
    den = set(S.denominator())
    cov, prose = S.covered() & den, S.prose_only() & den
    assert prose <= cov, "산문만이 본문 전체보다 많다 — 칸 빼기가 글자를 더 지웠다"
    assert (len(cov) - len(prose)) == ENFORCER_INFLATION, (
        f"강제자 칸만으로 덮인 파일이 {len(cov) - len(prose)}개 — 기록은 "
        f"{ENFORCER_INFLATION}개다. 늘었으면 절을 **읽지 않고 칸에만 적었다**")
    assert S.survey()["빈 곳"], "빈 곳이 0 이다 — 분모나 집합이 샜다"


def test_the_uncovered_side_is_mostly_the_web_client():
    """★ 실측. 빈 곳에서 `web/navi` 가 **제일 큰 묶음**이다 — 문서가 파이썬 쪽만 봤다.

    ★ 2026-10-06 (DECISIONS §411). 종전 단정은 「빈 곳의 40% 이상」이었다.
      그 배치가 `domain` 스무 파일을 읽어 42/109(38.5%)로 내려가자 **좋은 일이
      빨간불로 찍혔다.** §410 이 같은 날 배운 것과 같은 자리다 — 고치면 우는
      단정은 사람이 끄게 된다.

      묻는 것은 그대로 둔다: **빈 곳이 아직 화면 쪽에 몰려 있는가.** 임의의
      비율 대신 **묶음 순위**로 묻는다 — 다 읽으면 그때 이 단정이 자연스럽게
      풀린다(`web/navi` 가 1위에서 내려간다).
    """
    s = S.survey()
    navi = sum(n for k, n in s["묶음별 빈 곳"].items() if k.startswith("web/navi"))
    other = sum(n for k, n in s["묶음별 빈 곳"].items() if not k.startswith("web/navi"))
    assert navi * 2 >= other, (
        f"web/navi 가 빈 곳의 {navi}/{len(s['빈 곳'])} — 분포가 바뀌었으면 "
        "§384 를 다시 읽어라")


def test_the_tool_passes_its_own_selftest():
    assert S.selftest() == 0


def test_the_printed_percentage_is_the_two_numbers_it_shows(capsys):
    """★ 찍는 백분율이 **그 자리의 두 수**와 맞는가.

    ── 왜 생겼나 (2026-10-08 · DECISIONS §438-6) ──────────────────
    돌연변이 측정에서 `pct = cov / den * 100` 의 `100` 을 `101` 로 흔들었더니
    **아무도 안 울었다.** 그 줄은 `main()` 의 보고 경로이고 §428-5 가 적은
    「붙잡이가 없는 자리」와 같은 족이다.

    ★ 보고 경로라서 안 잡는다는 말은 **여기서는 안 통한다.** 사람이 읽는
      유일한 수가 그 백분율이고, 1% 틀린 백분율은 「95% 넘었다」와 「안
      넘었다」를 뒤집는다 — 그 자리에 임의의 비율 단정이 있었다는 것이
      이 절의 사고다. 찍는 수는 **찍는 두 수에서 유도된다.**
    """
    s = S.survey()
    S.show(s, listing=False)
    out = capsys.readouterr().out
    want = s["덮임"] / s["분모"] * 100
    assert f"**{s['덮임']} / {s['분모']}**" in out, "두 수를 그대로 안 찍는다"
    assert f"({want:.1f}%)" in out, (
        f"찍힌 백분율이 {want:.1f}% 가 아니다 — 두 수와 유도가 갈렸다\n  {out[:200]}")
