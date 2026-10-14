"""셸이 **겹따옴표 안의 백틱**을 실행한다 — 그 자리를 센다.  (DECISIONS §529)

── 왜 생겼나 ───────────────────────────────────────────────────
`"…`foo`…"` 는 문서 표기가 아니라 **명령 치환**이다. 이 저장소는 문서를
백틱으로 쓰므로 셸 문자열에도 손이 그렇게 간다.

★ **두 번 당했다.** §323 이 한 번 적었고, 2026-10-14 에 `tools/fl.sh` 의
  거절 문구가 또 그랬다 — `` `data/processed/*.gpkg` `` 가 글롭으로 풀려
  **gpkg 파일을 실행**했고(`Permission denied`), `` `git status` `` 출력이
  문장 한가운데 박혀 메시지가 통째로 깨졌다. 같은 날 세어 보니 같은 꼴이
  `fl.sh` 에 **두 줄 더** 살아 있었다.

★ §323 뒤에도 재는 자가 없었다 — `.github/actions/build-navi/action.yml` 이
  주석으로 「겹따옴표 안에서 백틱을 쓰지 않는다」를 적어 두었을 뿐이다.
  **사람이 기억으로 지키는 자리는 강제자가 아니다**(§390).

IN    `*.sh` · `.github/**/*.yml`
OUT   위반 줄
PARAM 없다 — 0 이거나 아니거나다(래칫이 아니다)
밖    **heredoc 안은 안 본다.** `<<'PY' … PY` 안은 파이썬이고 거기 백틱은
      무해하다. 그 구분을 안 하면 이 검사가 거짓 빨강으로 꺼진다.
      **이스케이프한 백틱**(`\\``)도 안 본다 — 그것은 글자다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
#: 겹따옴표 한 덩이. 이스케이프(`\"`)를 건너뛴다.
_DQ = re.compile(r'"(?:[^"\\]|\\.)*"')
#: heredoc 시작. 따옴표가 붙으면 본문이 셸 확장을 안 받는다 — 그 안은 남의 말이다.
_HD = re.compile(r"<<-?\s*'([A-Za-z_][A-Za-z0-9_]*)'")


def _live_lines(text: str):
    """셸이 **실제로 해석하는** 줄만 (번호, 글자)로 준다."""
    end = None
    for i, ln in enumerate(text.splitlines(), 1):
        if end is not None:
            if ln.strip() == end:
                end = None
            continue
        if (m := _HD.search(ln)):
            end = m.group(1)
            continue
        if ln.lstrip().startswith("#"):
            continue
        yield i, ln


def _bad(text: str):
    out = []
    for i, ln in _live_lines(text):
        for m in _DQ.finditer(ln):
            s = m.group(0)
            if re.search(r"(?<!\\)`", s):
                out.append((i, s[:72]))
    return out


def _targets():
    for p in sorted(ROOT.glob("tools/*.sh")):
        yield p
    for p in sorted(ROOT.glob(".github/**/*.yml")):
        yield p


def test_no_backtick_inside_double_quotes_in_shell():
    """**0 이어야 한다.** 백틱은 글자가 아니라 실행이다."""
    bad = []
    for p in _targets():
        for i, s in _bad(p.read_text(encoding="utf-8")):
            bad.append(f"  {p.relative_to(ROOT)}:{i}  {s}")
    assert not bad, (
        "겹따옴표 안에 **백틱**이 있다 — 셸이 그것을 명령으로 실행한다.\n"
        + "\n".join(bad)
        + "\n\n  백틱을 빼거나 홑따옴표로 바꿔라. 꼭 글자로 보여야 하면 \\` 다.\n"
          "  (DECISIONS §323 · §529 — 같은 꼴로 두 번 당했다)")


def test_the_net_bites():
    """**양방향.** 진짜 자리를 만들어 집히는지 본다 — 한쪽만 밀면 빈 그물이다."""
    assert _bad('die "  `git status` 가 안 보여준다"'), "살아 있는 백틱을 못 집는다"
    assert _bad('warn "`*.gpkg` 는 gitignore 다"'), "글롭 백틱을 못 집는다"


def test_the_net_does_not_bite_what_it_should_not():
    """거짓 빨강 셋 — 주석 · heredoc 안 · 이스케이프."""
    assert not _bad('# "  `git status` 가 안 보여준다"'), "주석을 집는다"
    assert not _bad('python3 - <<\'PY\'\nprint("  `mode` 다")\nPY\n'), "heredoc 안을 집는다"
    assert not _bad('die "브랜치는 반드시 \\`feat/**\\` 다"'), "이스케이프한 백틱을 집는다"
