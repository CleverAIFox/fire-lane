#!/usr/bin/env python3
"""
test_proposal_pdf.py — 기획서 PDF 판정기가 **빈 그물이 아닌가.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24 (DECISIONS §231). 뷰어를 `.docx` 브라우저 렌더에서 PDF 로 바꿨다.
  종전 선택의 근거가 「굽는 과정에서 깨졌나를 확인할 방법이 없다」였으므로,
  **확인하는 쪽이 이 배치의 값어치 전부**다. 그 확인이 죽으면 종전보다 나쁘다 —
  깨진 PDF 가 초록불로 배포된다.

★ 변환기(`soffice`)가 없어도 도는 시험이다. 판정기 `judge()` 는 순수 함수라
  합성 입력으로 부른다. **실물 PDF 로 「지금 초록인가」만 보면 0건이 청결인지
  죽음인지 못 가른다**(`deadcheck` 가 2026-09-21 에 배운 것).

IN    tools/proposal_pdf.py
OUT   없음 (검사)
밖    **실제로 구운 PDF 가 예쁜가는 안 본다.** 쪽이 밀렸는지 · 표가 잘렸는지 ·
      글꼴이 의도한 그것인지는 사람이 본다. 그리고 이 파일은 변환 자체를
      안 돌린다 — 변환은 CI 의 `stage-site` 액션이 하고 `--check` 가 판정한다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import proposal_pdf as pp
import pytest

ROOT = Path(__file__).resolve().parents[1]

OK_TEXT = ("가나다라마바사\n" * (pp.KOREAN_LINES_MIN + 10)) + "1,281 구간\n"


def test_normal_input_is_green():
    assert pp.judge(pp.PAGES_MIN, pp.IMAGES_MIN, OK_TEXT, {"구간 수": 1281}) == []


@pytest.mark.parametrize(("pages", "images", "text", "want", "갈래"), [
    (pp.PAGES_MIN - 1, pp.IMAGES_MIN, OK_TEXT, {}, "쪽수"),
    (pp.PAGES_MIN, pp.IMAGES_MIN - 1, OK_TEXT, {}, "그림"),
    (pp.PAGES_MIN, pp.IMAGES_MIN, "abc\n" * 9999, {}, "한글 줄"),
    (pp.PAGES_MIN, pp.IMAGES_MIN, OK_TEXT, {"구간 수": 9999}, "판정 수치"),
])
def test_every_branch_cries(pages, images, text, want, 갈래):
    bad = pp.judge(pages, images, text, want)
    assert bad, f"{갈래} 갈래가 안 운다 — 빈 그물이다"
    assert any(갈래 in b for b in bad), bad


def test_korean_lines_are_counted_by_line_not_by_character():
    """한 줄에 한글이 몇 자든 **한 줄**이다. 글자로 세면 하한이 뜻을 잃는다."""
    one = "가" * 10000 + "\n"
    assert any("한글 줄" in b for b in pp.judge(pp.PAGES_MIN, pp.IMAGES_MIN, one, {}))


def test_numbers_match_with_or_without_thousand_separator():
    """`1281` 과 `1,281` 둘 다 인정한다 — 기획서 표기가 자리마다 다르다."""
    base = "가나다\n" * (pp.KOREAN_LINES_MIN + 1)
    assert pp.judge(pp.PAGES_MIN, pp.IMAGES_MIN, base + "1281", {"n": 1281}) == []
    assert pp.judge(pp.PAGES_MIN, pp.IMAGES_MIN, base + "1,281", {"n": 1281}) == []


def test_canonical_numbers_come_from_golden_not_from_here():
    """판정 수치의 정본이 `golden` 지문 하나인가. 여기 적으면 정본이 둘이 된다."""
    want = pp.wanted_numbers()
    assert want, "판정 수치를 못 읽었다 — golden 지문이 없다"
    assert "구간 수" in want and want["구간 수"] > 0, want
    # ★ **코드만 본다.** 주석·독스트링과 `selftest()` 의 합성 픽스처는 정본이
    #   아니다 — 합성 입력에 숫자를 쓰는 것은 판정기를 시험하는 일이다.
    import ast
    tree = ast.parse((ROOT / "tools" / "proposal_pdf.py").read_text(encoding="utf-8"))
    inside = {id(x) for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "selftest"
              for x in ast.walk(f)}
    lit = [n.value for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, int)
           and id(n) not in inside and n.value in set(want.values())]
    assert not lit, (
        f"판정 수치가 도구 코드에 literal 로 박혀 있다: {lit} — 정본은 golden 하나다")


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "proposal_pdf.py"),
                        "--selftest"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_viewer_points_at_the_pdf_and_keeps_a_fallback():
    """뷰어가 PDF 를 가리키고, 없을 때 내려받기 안내로 바뀌는가."""
    import re as _re
    raw = (ROOT / "web" / "proposal.html").read_text(encoding="utf-8")
    # ★ **주석을 뺀 뒤에 본다.** 이 파일 자신의 `<!-- … docx-preview … -->` 이력을
    #   배선으로 읽으면 안 된다 — `test_tools_are_wired` 가 2026-09-20 에 배운 것.
    html = _re.sub(r"<!--.*?-->", "", raw, flags=_re.S)
    assert "./proposal.pdf" in html, "뷰어가 PDF 를 안 가리킨다"
    assert "docx-preview" not in html, (
        "브라우저 .docx 렌더러가 되살아났다 — 글꼴·그림이 받는 기계에 의존한다")
    assert "fallback" in html and "./proposal.docx" in html, (
        "PDF 가 없을 때의 길이 없다 — 로컬에 변환기가 없으면 빈 화면이 된다")


def test_pdf_is_not_committed():
    """생성물이다. 커밋하면 2MB 가 이력에 박히고 뺄 수 없다."""
    r = subprocess.run(["git", "ls-files", "web/proposal.pdf", "web/proposal.docx"],
                       capture_output=True, text=True, cwd=ROOT)
    assert not r.stdout.strip(), f"생성물이 추적되고 있다:\n{r.stdout}"
