#!/usr/bin/env python3
"""
test_pr_body_check.py — PR 본문 검사가 **성실한 사람을 벌주지 않는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-31. `tools/pr_body_check.py` 를 08-27 에 붙이고 나흘간 아무도
빨간불을 못 봤다. 검사가 옳아서가 아니었다. **아무도 템플릿의 체크리스트를
채우지 않았기 때문이다.**

`_section()` 이 `---` 를 절 끝으로 보지 않았다. `계약을 건드리는가` 가
템플릿의 마지막 `##` 절이라, 그 아래 `<details>` 안의 체크리스트 네 줄까지
같은 절로 셌다. 템플릿을 끝까지 채우면 `[x]` 가 다섯이 되고 `!= 1` 로 운다.

    템플릿을 성실히 채운 사람만 막힌다. 안내문을 지우고 한 줄 쓴 사람은
    통과한다. **강제자가 정확히 반대 방향으로 작동하고 있었다.**

초록불의 뜻이 `검사가 안 걸렸다` 가 아니라 **`아무도 검사 대상이 되는 일을
안 했다`** 였다. 사람의 태만이 강제자의 결함을 가려 준다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 정본 템플릿을 끝까지 채운 본문이 통과하는가       (거짓 빨간불)
    2. 0개 · 2개를 찍으면 실제로 우는가                   (검사가 죽었는가)
    3. 회피 문구 · 경로 없음을 여전히 잡는가
    4. 절 경계가 `<details>` 앞에서 끊기는가              (원인 자리)

★ 본문을 새로 적지 않고 **정본 템플릿을 읽어서** 만든다. 문자열을 손으로
  베끼면 템플릿이 바뀔 때 이 검사만 낡는다(R15).

IN    .github/pull_request_template.md · tools/pr_body_check.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

from pathlib import Path

import pr_body_check as P
import pytest

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / ".github/pull_request_template.md"

POINT = "src/firelane/ledger.py:248 — globs 를 stem 우선으로"


def _template() -> str:
    if not TPL.exists():
        pytest.skip("PR 템플릿이 없다")
    return TPL.read_text(encoding="utf-8")


def _filled(*, look: str = POINT, out: bool = True, con: bool = True,
            checklist: bool = True) -> str:
    """정본 템플릿을 사람이 채운 모양으로 만든다.

    `checklist=True` 가 이 파일의 핵심이다. 접힌 `<details>` 안의 네 줄까지
    채우는 사람 — 즉 규약을 가장 잘 지키는 사람 — 이 08-31 까지 막혔다.
    """
    b = _template()
    b = b.replace("## 리뷰어가 볼 곳 — **한 곳만**",
                  f"## 리뷰어가 볼 곳 — **한 곳만**\n\n{look}", 1)
    if out:
        b = b.replace("- [ ] 안 바뀐다", "- [x] 안 바뀐다", 1)
    if con:
        b = b.replace("- [ ] 안 건드린다", "- [x] 안 건드린다", 1)
    if checklist:
        for frag in ("- [ ] `git config", "- [ ] 아침에",
                     "- [ ] base 브랜치", "- [ ] CI 초록불"):
            b = b.replace(frag, frag.replace("- [ ]", "- [x]"), 1)
    return b


def test_faithfully_filled_template_passes():
    """★ 이 검사가 이 파일의 존재 이유다.

    템플릿을 안내문대로 끝까지 채운 본문은 통과해야 한다. 여기가 빨간불이면
    검사가 규약 준수를 처벌하고 있는 것이고, 사람은 곧 템플릿을 지운다.
    **우회가 습관이 되면 강제자 전체가 무력해진다.**
    """
    bad = P.check(_filled())
    assert not bad, (
        "템플릿을 성실히 채운 PR 본문이 막힌다.\n"
        + "\n".join(f"  ✗ {b.splitlines()[0]}" for b in bad)
        + "\n  절 경계가 `<details>` 를 넘어가고 있다.\n"
        "  tools/pr_body_check.py `_section()` 의 lookahead 를 보라.")


def test_details_blocks_are_outside_every_section():
    """`---` 아래 접힌 블록이 어느 절에도 속하지 않는가 — 원인 자리.

    위 검사는 증상을 본다. 이것은 자리를 지목한다. 둘 다 있어야 다음
    사람이 빨간불을 보고 어디를 고칠지 안다.
    """
    b = P._strip_comments(_filled())
    for title in ("리뷰어가 볼 곳", "산출물이 바뀌는가", "계약을 건드리는가"):
        sec = P._section(b, title)
        assert "<details>" not in sec, (
            f"`{title}` 절이 `<details>` 블록까지 삼킨다.\n"
            "  템플릿은 `---` 로 본문과 부록을 가른다. `_section()` 도\n"
            "  `---` 를 절 끝으로 봐야 한다.")


@pytest.mark.parametrize("kw", [{"con": False}, {"out": False}])
def test_unchecked_box_still_fails(kw):
    """안 찍으면 여전히 우는가. 절 경계를 좁힌 뒤에도 살아 있어야 한다."""
    assert P.check(_filled(**kw)), (
        f"체크박스를 안 찍었는데 통과한다 ({kw}).\n"
        "  절 경계를 좁히다가 검사 자체를 죽인 것이다.")


def test_double_check_fails():
    """둘 다 찍으면 우는가. `정확히 하나` 가 진짜로 하나인가."""
    b = _filled().replace("- [ ] 바뀐다", "- [x] 바뀐다", 1)
    assert P.check(b), "산출물 칸을 둘 찍었는데 통과한다 — `!= 1` 이 죽었다"


def test_dodge_phrase_fails():
    assert P.check(_filled(look="전체 확인 부탁드립니다")), (
        "회피 문구가 통과한다. `전체 확인` 은 확인 안 한다는 뜻이다.")


def test_no_path_fails():
    assert P.check(_filled(look="폭 계산 쪽 좀 봐 주세요")), (
        "파일 경로 없는 지목이 통과한다.")


def test_empty_body_fails():
    assert P.check("")
