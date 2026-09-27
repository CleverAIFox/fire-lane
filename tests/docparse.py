"""문서 줄 읽기 — **코드 펜스 처리의 집이 여기 하나다.**

★ 2026-09-24 (PLAN §13 W12-5 · DECISIONS §239). 절 번호 유일성을 **세 파일이
  각각 다른 규칙으로** 보고 있었다 —

      test_doc_style           `##` 만 · 펜스 제외 **함** · 들여쓴 블록도 제외
      test_reproducibility     `##`+`###` · 펜스 제외 **함**
      test_docref              `###` 만 · 펜스 제외 **안 함**

  PLAN 의 `### N-M.` 유일성은 뒤 둘이 겹쳐서 보고, 펜스 처리가 갈린다.
  오늘은 발현하지 않는다 — 세 문서의 코드펜스 안에 절 제목꼴 줄이 0건이다.
  **회고 한 줄이 펜스 안에 절 제목을 인용하는 순간** `test_docref` 만
  빨개지고 나머지 둘은 초록이다. 한쪽 파서를 고쳐도 다른 쪽은 제 규칙을 쓴다.

★ 이 저장소는 「정본이 둘이면 갈린다」를 강제자로 세운다
  (`tests/test_sources_of_truth.py`). 그 저장소에서 파서가 셋이었다.

★ **읽는 규칙만 여기 둔다.** 무엇을 셀지(상위 절인가 하위 절인가, 번호 없는
  제목을 잡을 것인가)는 세 시험이 각자 정한다 — 그것은 물음이 다른 것이지
  규칙이 갈린 것이 아니다.
"""
from __future__ import annotations

from pathlib import Path

#: 「이 줄은 일부러 옛 것을 인용한다」 표시. `docnum_check` 와 같은 자리다.
#: ★ 문서마다 마커가 다르다 — 숫자는 `stale-ok`, 문체는 `voice-ok`.
#:   그래서 **무엇을 넘길지는 부르는 쪽이 정한다**(`allow` 인자).
ALLOW = "<!--stale-ok-->"


#: 코드 펜스를 여는/닫는 표기. 마크다운은 둘 다 인정한다.
FENCE = ("```", "~~~")


def outside_fences(lines):
    """줄 **목록**에서 코드 펜스 안을 뺀다. 파일이 아니라 이미 자른 본문용."""
    fence = False
    for line in lines:
        if line.lstrip().startswith(FENCE):
            fence = not fence
            continue
        if not fence:
            yield line


def prose_lines(p: Path, *, skip_indented: bool = False,
                allow: str | None = None) -> list[tuple[int, str]]:
    """`(줄번호, 줄)`. **코드 펜스 안은 언제나 뺀다.**

    펜스 안은 인용이지 주장이 아니다 — DECISIONS 는 폐기한 문장을 증거로
    인용하고, 인용을 위반으로 세면 회고를 쓸 수 없게 된다. 그러면 사람이
    검사를 끈다.

    :param skip_indented: 4칸 들여쓴 블록도 뺀다. 같은 이유의 다른 꼴이다.
    :param allow: 이 표시가 달린 줄을 뺀다(`<!--stale-ok-->` · `<!--voice-ok-->`).
    """
    out: list[tuple[int, str]] = []
    fence = False
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith(FENCE):
            fence = not fence
            continue
        if fence:
            continue
        if allow and allow in line:
            continue
        if skip_indented and line.startswith("    ") and line.strip():
            continue
        out.append((i, line))
    return out


def selftest() -> int:
    """펜스 안을 정말로 빼는가. 세 시험이 이 함수를 믿는다."""
    import tempfile
    doc = ("## 1. 산문\n"
           "```\n"
           "## 1. 펜스 안 인용 — 이것은 절이 아니다\n"
           "```\n"
           "    ## 1. 들여쓴 인용\n"
           "## 2. 또 산문  <!--stale-ok-->\n")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.md"
        p.write_text(doc, encoding="utf-8")
        plain = [s for _, s in prose_lines(p)]
        assert "## 1. 펜스 안 인용 — 이것은 절이 아니다" not in plain, "펜스를 안 뺀다"
        assert "## 1. 산문" in plain and "    ## 1. 들여쓴 인용" in plain
        ind = [s for _, s in prose_lines(p, skip_indented=True)]
        assert "    ## 1. 들여쓴 인용" not in ind, "들여쓴 블록을 안 뺀다"
        assert len(plain) == 3, plain          # 펜스 세 줄이 빠진다
        kept = [s for _, s in prose_lines(p, allow=ALLOW)]
        assert not any(ALLOW in s for s in kept), "stale-ok 줄을 안 뺀다"
        assert len(kept) == 2, kept
        assert len([s for _, s in prose_lines(p, allow="<!--voice-ok-->")]) == 3, \
            "다른 마커를 넘기면 안 된다 — 무엇을 넘길지는 부르는 쪽이 정한다"
        assert list(outside_fences(["a", "~~~", "b", "~~~", "c"])) == ["a", "c"], \
            "`~~~` 펜스를 안 본다 — 마크다운은 둘 다 인정한다"
    print("docparse OK — 펜스(``` · ~~~) · 들여쓰기 · stale-ok 를 뺀다")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
