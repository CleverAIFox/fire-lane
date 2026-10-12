#!/usr/bin/env python3
"""
test_ledger_fsck.py — **대장 전수 정합의 판정.** (§496)

── 왜 생겼나 ───────────────────────────────────────────────────
`firelane.ledger_check.check_all` 은 대장 72종을 전수로 심사하고,
`uv run python -m firelane.ledger_check` 가 그것을 `verify.sh` 에서 돈다.
그런데 `tools/srccov.py` 가 그 함수를 「시험이 이름으로도 안 부른다」로
셌다(§493 · §496 — `e.get(...)` 때문에 입출력으로 가려져 있었다).

★ 밀어 보니 **옳은 값에 경고를 내고 있었다.** `updated: '2026-08'` 둘이
  대장에 **사유까지 적어 두고**(「제공처 공시가 월까지만 준다. 없는 날짜를
  짓지 않는다」) 매 실행 경고를 받았다. 없는 날짜를 짓는 것보다 월로 두는
  것이 옳다(§455 회색=NULL). **오탐 공장이 된 검사는 진짜 경보를 죽인다**
  (§18-13). 그래서 월까지만도 받되 **사유와 함께만** 받는다(§69) — 사유는
  대장 원문의 주석이 들고, `yaml_span` 이 그 블록을 읽는다.

IN    sources.yaml (실물)
OUT   없음 (검사)
PARAM 없음
밖    **활용도 등급은 안 본다** — `grade` 는 `tests/test_unusedcheck.py` 가
      든다. **칸이 있는가도 안 본다** — `tools/ledgercols.py` 소관이다.
      여기가 드는 것은 **전수 판정이 지금 무엇을 말하는가** 하나다.
"""
from __future__ import annotations

import pytest

from firelane import ledger_check as lgc


def test_the_real_ledger_has_no_failures():
    """★ 본체. 실물 대장에 `FAIL` 이 **없다.**

    `FAIL` 은 「조회 인덱스에서 빠진다」 같은 것이고, 하나라도 있으면 그
    데이터셋이 반입·개명·계보에서 조용히 사라진다.
    """
    bad = [str(i) for i in lgc.check_all() if i.level == lgc.FAIL]
    assert not bad, "대장 전수 심사가 실패를 낸다:\n  " + "\n  ".join(bad)


def test_the_real_ledger_is_clean_right_now():
    """★ 경고도 **0** 이다 — 「옳은데 우는」 경고를 §496 이 걷었다.

    여기서 수가 늘면 **그 배치가 늘린 것**이다. 늘려야 할 사유가 있으면
    경고 문구와 함께 DECISIONS 에 적고 이 시험을 같이 고쳐라.
    """
    got = [str(i) for i in lgc.check_all()]
    assert not got, "대장 심사가 경고를 낸다:\n  " + "\n  ".join(got)


def test_a_month_only_date_needs_a_reason_in_the_ledger(monkeypatch):
    """★ 양방향. 사유 주석이 **없으면** 운다.

    실물 대장은 그 사유를 들고 있다(위 시험이 초록인 근거). 주석을 지운
    원문을 쥐여 주면 같은 값이 경고가 돼야 한다 — 그래야 「사유와 함께만」이
    규약이고 빈 그물이 아니다.
    """
    text = lgc.raw_text()
    line = "    updated: '2026-08'"
    assert text.count(line) >= 1, "전제 — 월까지만인 항목이 대장에 있다"
    # 그 줄들의 **주석만** 떼어낸다
    stripped = "\n".join(
        line if s.startswith(line) else s for s in text.splitlines())
    monkeypatch.setattr(lgc, "raw_text", lambda: stripped)
    got = [i for i in lgc.check_all() if "월까지만" in i.msg]
    assert got, "사유 없는 월까지만을 통과시킨다 — 사유 없는 예외를 금한다(§69)"
    assert all(i.level == lgc.WARN for i in got), "등급이 경고가 아니다"


def test_a_date_that_is_neither_a_day_nor_a_month_still_warns():
    """★ 세 번째 꼴은 그대로 운다 — 받는 것은 **월까지만**이지 아무것이나가 아니다."""
    from firelane.ledger import DATE, DATE_MONTH

    for v in ("2026", "26-08-01", "2026/08/01", "2026-8-1", "작년", ""):
        assert not DATE.match(v) and not DATE_MONTH.match(v), v
    assert DATE.match("2026-08-01") and DATE_MONTH.match("2026-08")


def test_two_entries_may_not_claim_the_same_file_with_different_scopes(monkeypatch):
    """★ 교차 판정 — 같은 실물을 두 항목이 다른 스코프로 적으면 **하나는 틀렸다.**

    그 상태에서는 어느 스코프로 집계할지 코드가 고를 수 없고, 고른 쪽이
    조용히 이긴다. 합성 대장으로 양방향을 민다.
    """
    def fake(scope_b: str):
        return {"datasets": {
            "a": {"stem": "x_one", "ext": ["csv"], "scope": "jngj-donggu",
                  "files": ["x/x_one_jngj-donggu_20260101.csv"],
                  "updated": "2026-01-01", "what": "가"},
            "b": {"stem": "x_two", "ext": ["csv"], "scope": scope_b,
                  "files": ["x/x_one_jngj-donggu_20260101.csv"],
                  "updated": "2026-01-01", "what": "나"},
        }}

    monkeypatch.setattr(lgc, "load", lambda: fake("jngj"))
    hit = [i for i in lgc.check_all() if "서로 다른 스코프" in i.msg]
    assert hit and hit[0].level == lgc.FAIL, [str(i) for i in lgc.check_all()]

    # ★ 음성 — 스코프가 같으면 그것은 교차가 아니다(묶음일 수 있다)
    monkeypatch.setattr(lgc, "load", lambda: fake("jngj-donggu"))
    assert not [i for i in lgc.check_all() if "서로 다른 스코프" in i.msg]


def test_every_issue_says_which_entry_and_why():
    """★ 판정이 **키와 까닭**을 들고 온다 — 둘 없는 경고는 못 고친다."""
    msgs = [lgc.Issue(lgc.WARN, "k", "까닭")]
    assert str(msgs[0]) == "WARN [k] 까닭"
    with pytest.raises(TypeError):
        lgc.Issue(lgc.WARN, "k")        # 칸 셋이 다 필수다
