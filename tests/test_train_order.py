#!/usr/bin/env python3
"""
test_train_order.py — 열차가 **아는 자리에서 멈추는가.**  (DECISIONS §273-5 · §273-13)

── 왜 따로 있나 ───────────────────────────────────────────────
`test_batch_tools.py` 는 배치 도구의 **동작**을 문다 — 무엇을 집고, 무엇을 얹고,
못 읽은 답에 무엇을 안 지우는가. 여기가 무는 것은 **순서**다.

    7b       스쿼시와 dev PR **사이**에 있는가
    본문 검사  전수 verify **앞**에 있는가

둘 다 「있는가」가 아니라 「어디에 있는가」다. 뒤로 밀리면 검사는 남아 있는데
값이 사라진다 — 7b 가 dev PR 뒤면 CI 가 이미 돌고, 본문 검사가 verify 뒤면
14분을 태우고 죽는다. **실제로 둘 다 그렇게 났다.**

IN    tools/fl.sh
OUT   없음 (검사)
밖    **무엇을 검사하는지는 안 본다** — 7b 의 목록과 사유는
      `tools/after_squash.py --selftest` 가 들고, 본문의 내용은
      `tools/pr_body_check.py` 가 든다. 여기는 자리만 본다.
      그리고 **실행은 안 해본다** — 도는 것은 `test_batch_tools.py` 가 합성
      저장소로 댄다.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fl_runs_the_after_squash_check_before_opening_the_dev_pr():
    """★ 7b 가 **스쿼시와 dev PR 사이에** 있는가.  (DECISIONS §273-5)

    같은 날 CI 가 로컬 verify 를 세 번 이겼다. 셋 다 「전수 verify 는 `feat` 에서
    한 번 돌고, 그 뒤 스쿼시 · 재도장 · 발행이 만든 상태는 아무도 안 본다」였다.
    7b 는 그 자리를 메운다 — **순서가 곧 그 검사의 존재 이유**라서 위치까지 문다.
    뒤로 밀리면 dev PR 이 먼저 열리고, 그때는 이미 CI 가 도는 중이다.
    """
    raw = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    # ★ **주석을 걷는다.** 처음에 원문에서 찾았더니 호출을 `true` 로 바꿔도 초록이었다 —
    #   바로 위 주석에 같은 이름이 있어서다. 인용은 호출이 아니다(§272-2 와 같은 병).
    src = "\n".join("" if ln.lstrip().startswith("#") else ln
                    for ln in raw.splitlines())
    call = src.find("tools/after_squash.py")
    assert call > 0, "fl.sh 가 7b 를 안 부른다 — 열차 뒤 상태를 아무도 안 본다"

    squash = src.find('step "7.')
    devpr = src.find('step "8.')
    assert squash > 0 and devpr > squash, "7 · 8 단계를 못 찾았다 — 이 시험이 낡았다"
    assert squash < call < devpr, (
        f"7b 가 스쿼시(7)와 dev PR(8) 사이에 없다 — 위치 {call}, 7 {squash}, 8 {devpr}")

    # ★ 빨간불에서 **멈추는가.** 찍고 지나가면 그 검사는 없는 것과 같다.
    tail = src[call:call + 400]
    assert "die" in tail, "7b 가 빨간불에서 안 죽는다 — 찍고 지나가면 CI 까지 간다"


def test_all_stops_before_verify_when_the_pr_body_is_missing():
    """★ 진단이 맞았는데 행동이 안 따랐다.  (DECISIONS §273-13)

    2026-09-27 실기. 2단계가 `! PR_BODY.md 가 없다 — --all 은 못 간다` 를 **찍고**
    그대로 3~5단계로 갔다. 전수 verify 14분39초를 태운 뒤 6단계에서 같은 사실로
    죽었다. **그 줄이 이미 알고 있었다** — 경고문이 「못 간다」라고 적는데 못 가게
    하지는 않았다.

    ★ 같은 형태를 오늘 아침에도 겪었다(배달 스크립트의 밑동 대조). 경고는
      행동이 아니다. 아는 자리에서 멈추는 것이 행동이다.
    """
    raw = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    src = "\n".join("" if ln.lstrip().startswith("#") else ln
                    for ln in raw.splitlines())          # 주석은 걷는다(§273-5 와 같은 이유)

    # ★ **줄 단위로 못박는다.** 처음에 ±400자 창 안에 `die` 가 있는지만 봤더니
    #   `die` 를 `warn` 으로 되돌려도 초록이었다 — 창 안에 다른 `die` 가 있었다.
    #   오늘 네 번째 빈 그물이고 넷 다 느슨한 창·부분문자열이었다.
    lines = [ln for ln in src.splitlines() if "--all 은 못 간다" in ln]
    assert lines, "2단계에 `--all` 본문 부재 처리가 없다 — 이 시험이 낡았다"
    bad = [ln.strip() for ln in lines if "die" not in ln]
    assert not bad, (
        "본문이 없는데 멈추지 않는다 — 경고만 하면 verify 14분을 태우고 6단계에서 죽는다.\n  "
        + "\n  ".join(bad))
    i = src.index(lines[0])

    verify = src.find("step \"5. 전수 verify\"")
    assert verify > 0, "5단계를 못 찾았다 — 이 시험이 낡았다"
    assert i < verify, "본문 검사가 전수 verify **뒤**에 있다 — 태우고 나서 멈춘다"
