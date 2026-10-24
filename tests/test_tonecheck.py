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
