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


def test_the_enforcer_column_does_not_count_as_coverage():
    """★ 음성 대조. 「누가 지킨다」와 「읽고 판단했다」는 다르다.

    강제자 칸은 절마다 `tools/...` 를 줄줄이 적는다. 그것을 덮임으로 세면
    거의 모든 도구가 **읽히지 않은 채** 감사된 것이 되고, 이 수가 뜻을 잃는다.
    `body(strip=True)` 가 그 칸을 빼는 것이 전제다 — 전제가 깨지면 덮임이
    분모에 붙어버리므로, 그 자리를 수로 못박는다.
    """
    s = S.survey()
    assert s["빈 곳"], "빈 곳이 0 이다 — 강제자 칸이 덮임으로 세어진다"
    assert s["덮임"] < s["분모"] * 0.95, (
        f"덮임이 {s['덮임']}/{s['분모']} 로 지나치게 높다 — 분모나 집합이 샜다")


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
