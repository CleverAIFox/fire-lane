"""`tonecheck` 가 코드 주석까지 보고, 욕설 · 반말 질책은 `voice-ok` 로도 못 푼다.  (감사 3절 · Zm20)

문체 요지화 대상이 문서가 아니라 **코드 주석 · docstring** 에도 있었다(`.py` · `.sh` · `.ts`).
그리고 인용 표시(`<!--voice-ok-->`)는 용어(은어 · 약칭)를 위한 규약인데 욕설까지 통과시키는 구멍이었다.

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **말투가 옳은가**는 안 본다 — 도구가 족을 물고 풀 수 있는 족/없는 족을 가르는지만 본다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tc():
    spec = importlib.util.spec_from_file_location("tonecheck_t", ROOT / "tools" / "tonecheck.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def test_repo_is_clean() -> None:
    assert _tc().scan() == []


def test_selftest_is_alive() -> None:
    assert _tc().selftest() == 0


def test_code_comments_are_in_scope() -> None:
    """py · sh · ts 의 주석과 docstring 을 본다 — 심으면 운다."""
    tc = _tc()
    rels = {rel for rel, _ in tc.targets()}
    for suf in (".py", ".sh", ".ts"):
        assert any(r.endswith(suf) for r in rels), f"{suf} 가 범위 밖이다"
    assert tc.scan([("src/x.py", '"""\n앞 씨발 뒤\n"""')])
    assert tc.scan([("tools/x.sh", "# 앞 존나 뒤")])
    assert tc.scan([("web/navi/src/x.ts", "// 앞 지랄 뒤")])
    assert tc.scan([("src/x.py", "# 사용자가 「왜 안 되냐」를 물었다")])


def test_voice_ok_does_not_release_abuse_or_scolding() -> None:
    tc = _tc()
    assert tc.scan([("docs/x.md", "<!--voice-ok-->\n> 앞 씨발 뒤")])
    assert tc.scan([("docs/x.md", "```\n앞 개소리 뒤\n```")])
    assert tc.scan([("docs/x.md", "<!--voice-ok-->\n사용자가 「이게 뭐냐」를 물었다")])
    assert tc.scan([("docs/x.md", "    사용자가 「이게 뭐냐」를 물었다")])


def test_voice_ok_still_releases_a_term_family() -> None:
    tc = _tc()
    assert tc.scan([("docs/x.md", "<!--voice-ok-->\n> 앞 땅따먹기 뒤")]) == []
    assert tc.scan([("docs/x.md", "```\n앞 땅따먹기 뒤\n```")]) == []
    assert tc.scan([("docs/x.md", "앞 땅따먹기 뒤")])


def test_a_neutral_quote_is_not_a_scolding() -> None:
    tc = _tc()
    assert tc.scan([("docs/x.md", "이 도구가 무엇이냐는 물음에 답한다")]) == []


def test_colloquial_quotes_are_caught_without_context_words() -> None:
    """구어 어미로 끝나는 인용은 문맥어(사용자 · 물었다)가 없어도 문다 — 합성 문장으로(요청서 3절 · Zm22)."""
    tc = _tc()
    for line in ("「이 부분은 왜 이렇게 한 거임」", "> 이건 맞는 방향 아니냐", "// 「이거 되는 거 맞냐」", "# 「그게 지금 있냐」"):
        assert tc.scan([("src/x.py", line)]), line
    assert not tc.scan([("src/x.py", "# 「법선이냐 내접원이냐」 양자택일을 둔다")])
    assert not tc.scan([("src/x.py", "# 「0 보다 크냐」 로 두면 안 된다")])


def test_pending_waivers_are_alive_and_few() -> None:
    """사람이 정하기로 한 면제는 **실재하는 줄**에만 있다. 죽은 면제는 사각지대다."""
    tc = _tc()
    text = "\n".join((ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8").splitlines())
    dead = [w for w in tc.PENDING_HUMAN if w not in text]
    assert not dead, f"줄이 사라졌는데 면제가 남았다: {dead}"
    assert len(tc.PENDING_HUMAN) <= 5, "면제를 늘리지 않는다 — 요지화하고 지운다"
