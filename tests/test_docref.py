#!/usr/bin/env python3
"""
test_docref.py — 절 참조가 실재하는가. 하위 절 번호가 유일한가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-30. `MASTER §12` 를 4계층 브랜치 구조로 재작성하면서 하위 절을
앞에 끼워 넣었다. **번호가 겹쳤다** — `12-1` 이 둘(룰셋 · 하루 흐름),
`12-2` 가 둘(소유권 · 커밋 메시지). 문서는 멀쩡해 보였고
`test_doc_style` 은 통과했다. 그 검사가 상위 `##` 만 보기 때문이다.

겹친 것을 11개 연속으로 다시 매기자 이번에는 **참조가 깨졌다.**
`DECISIONS.md:2377` 과 `src/firelane/manifest.py:7` 이
`재현성 기록이다(MASTER §12-6)` 이라 적는데, 재번호 뒤 `12-6` 은
`커밋 메시지` 가 됐다. 원래 가리키던 절은 `12-10` 이다.

**두 사고 다 조용했다.** 문서를 읽는 사람만 엉뚱한 곳으로 간다.
`docnum_check.py` 가 문서의 숫자를 산출물과 대조하듯, 절 참조도 대조한다.

★ 이 저장소가 반복해 배운 형태다 — 규약은 존재하고 강제하는 검사가
  없다(MASTER §17). 일회성으로 고치면 다음에 또 겪는다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. `§N-M` 참조가 가리키는 절이 실재하는가
    2. 한 문서 안에서 하위 절 번호가 유일한가
    3. 하위 절 번호가 1부터 연속인가

★ 상위 절(`## N.`)의 연속성은 `test_doc_style` 이 이미 본다. 겹치지 않게
  하위 절만 본다 — 같은 것을 두 곳에서 검사하면 한쪽이 낡는다.

IN    README.md · docs/*.md · src/**/*.py · tools/*.py · tests/*.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

import docparse

ROOT = Path(__file__).resolve().parent.parent

# ★ 참조는 세 문서 어디든 가리킨다. 처음에 MASTER 만 정본으로 잡았다가
#   114건이 오탐으로 떴다 — `PLAN §4-4` · `DECISIONS §7-5` 가 그것이다.  ref-ok
#   **어느 문서를 가리키는지는 글에 안 적히는 경우가 많다.** 그래서
#   세 문서의 절 번호를 합집합으로 두고, 그 어디에도 없을 때만 잡는다.
#   느슨하지만 오탐이 없다 — 검사가 시끄러우면 사람이 끈다.
CANON = [ROOT / "docs/MASTER.md", ROOT / "docs/PLAN.md",
         ROOT / "docs/DECISIONS.md"]

# `### 12-2. 제목` · `### 18-2a. 제목` 둘 다 잡는다.
SUB = re.compile(r"^###\s+(\d+)-(\d+)([a-z]?)\.\s*(.+?)\s*$", re.M)

# 본문의 참조. `§12-6` · `MASTER §18-5` · `(§19-1)`
REF = re.compile(r"§\s*(\d+)-(\d+)([a-z]?)")

SCAN_DIRS = ("src", "tools", "tests", "docs")


def _sections(p: Path) -> list[tuple[str, str, int]]:
    """(절번호, 제목, 줄번호).

    ★ 2026-09-24 (PLAN §13 W12-5). 종전에는 **코드 펜스 안까지 봤다.**
      같은 물음을 보는 시험 셋 중 여기만 그랬다 — 펜스 안에 절 제목을
      인용하는 회고 한 줄이 들어오면 이 시험만 빨개진다. 펜스 처리의
      집을 `tests/docparse.py` 하나로 올렸다.
    """
    if not p.exists():
        return []
    out = []
    for i, line in docparse.prose_lines(p):
        m = SUB.match(line)
        if m:
            out.append((f"{m.group(1)}-{m.group(2)}{m.group(3)}",
                        m.group(4), i))
    return out


def _sources() -> list[Path]:
    """참조를 적을 수 있는 모든 파일."""
    out = [ROOT / "README.md"]
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for ext in ("*.md", "*.py"):
            out += [p for p in base.rglob(ext) if "_backup" not in str(p)]
    return sorted(set(p for p in out if p.exists()))


# ── 1 · 참조 무결성 ────────────────────────────────────────────
def test_section_references_resolve():
    """★ `§N-M` 이 가리키는 절이 실재하는가.

    번호를 다시 매기면 참조가 조용히 다른 절을 가리킨다. 문서는 멀쩡해
    보이고 읽는 사람만 엉뚱한 곳으로 간다.
    """
    have: set[str] = set()
    for c in CANON:
        for n, _, _ in _sections(c):
            have.add(n)
            # ★ `### 18-1a` 는 `§18-1` 로도 인용된다. 알파벳 접미를 벗긴
            #   형태도 유효한 참조로 인정한다.
            have.add(re.sub(r"[a-z]$", "", n))
    # ★ 2026-09-22 (PLAN §13 W10-1 · deadcheck ③). 종전 `if not have: return` — 절 파서가 죽으면 **모든 참조가
    #   검사 없이 통과**했다. 정본 문서에는 절이 반드시 있다.
    assert have, f"정본 문서 {[c.name for c in CANON]} 에서 절을 하나도 못 읽었다 — 절 파서가 죽었다"

    # ★ **하위 절 제목이 실제로 연속 체계를 이루는 상위 절만** 본다.
    #
    #   처음에는 `§N-M` 을 전부 절 참조로 봤다가 114건이 오탐이었다.
    #   문서에는 절이 아닌 `N-M` 표기가 세 종류나 있다 —
    #
    #     PLAN §1-16     §1 남은 일 **표의 행 번호**
    #     MASTER §18-5   §18 본문의 **규칙 R1~R18 목록**
    #     PLAN §0-0      묶음 구분 주석의 관용 표기
    #
    #   특히 DECISIONS §66 이 명시한다 — `§11` · `§18-1` · `§18-5` ·
    #   `§18-12` · `§19` 는 **코드 주석과 대장에서 60여 곳이 인용하는
    #   관용 번호**이며 절 제목이 아니다. 그것까지 강제하면 오탐이
    #   본문을 덮고, 그러면 사람이 검사를 끈다.
    #
    #   그래서 대상을 **`### N-M.` 제목이 3개 이상 연속으로 붙은 상위
    #   절**로 좁힌다. 새 절이 그 체계를 갖추면 자동으로 대상에 들어온다 —
    #   목록을 손으로 관리하지 않는다.
    #   ★ 2026-09-24 (§239). 이 자리에 「지금은 §12 하나다」라고 적혀 있었다.
    #     실측 **99개**다(DECISIONS §78~§237 이 전부 들어온다). 규칙이 스스로
    #     넓어진 것이고 그것이 설계인데, **주석이 범위를 99분의 1로 적고 있었다.**
    #     검사가 선언보다 넓으면 거짓 초록은 아니지만 거짓 빨강의 출처를 못 찾는다.
    #   판정은 **실제 제목만** 센다. 위에서 별칭(`18-1a`→`18-1`)을 have 에
    #   넣었으므로 그것까지 세면 §18 이 대상이 되어 버린다.
    real: dict[str, list[int]] = {}
    for c in CANON:
        for n, _, _ in _sections(c):
            m = re.match(r"^(\d+)-(\d+)$", n)      # 알파벳 접미는 제외
            if m:
                real.setdefault(m.group(1), []).append(int(m.group(2)))

    #   1 부터 연속이고 셋 이상일 때만 "번호 체계" 로 본다.
    #     §12  1..11  → 대상
    #     §18  전부 알파벳 접미 → 제외
    #     PLAN §1  23,24,25 (1 부터 아님) → 제외. 표의 행 번호와 섞인다
    tops = {k for k, v in real.items()
            if len(v) >= 3 and sorted(v) == list(range(1, len(v) + 1))}

    bad: list[str] = []
    for p in _sources():
        try:
            txt = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(txt.splitlines(), 1):
            if line.lstrip().startswith("###"):
                continue                       # 절 제목 자체는 참조가 아니다
            for m in REF.finditer(line):
                ref = f"{m.group(1)}-{m.group(2)}{m.group(3)}"
                if m.group(1) not in tops:
                    continue                   # 하위 절을 안 쓰는 상위 절
                if ref not in have:
                    rel = p.relative_to(ROOT)
                    bad.append(f"  {rel}:{i}  §{ref} 이 문서 셋 어디에도 없다\n"
                               f"      {line.strip()[:80]}")

    assert not bad, (
        f"실재하지 않는 절을 가리키는 참조 {len(bad)}건\n"
        + "\n".join(bad[:20])
        + (f"\n  ... 외 {len(bad) - 20}건" if len(bad) > 20 else "")
        + "\n\n  절 번호를 다시 매겼으면 참조도 같이 고친다.\n"
        "  현재 번호는 `grep -n '^### ' docs/MASTER.md` 로 본다.")


# ── 2 · 번호 유일성 ────────────────────────────────────────────
def test_subsection_numbers_are_unique():
    """★ 한 문서 안에서 하위 절 번호가 겹치지 않는가.

    2026-08-30 에 `12-1` 과 `12-2` 가 각각 둘이었다. 겹치면 외부에서
    인용할 수 없고, 인용해도 어느 쪽인지 알 수 없다.
    """
    for name in ("MASTER.md", "PLAN.md", "DECISIONS.md"):
        p = ROOT / "docs" / name
        secs = _sections(p)
        seen: dict[str, tuple[str, int]] = {}
        dup: list[str] = []
        for num, title, ln in secs:
            if num in seen:
                t0, l0 = seen[num]
                dup.append(f"  §{num}  {p.name}:{l0} {t0[:30]}"
                           f"  ↔  :{ln} {title[:30]}")
            else:
                seen[num] = (title, ln)
        assert not dup, (
            f"{p.name} 의 하위 절 번호가 겹친다 {len(dup)}건\n"
            + "\n".join(dup)
            + "\n\n  절을 끼워 넣었으면 뒤를 밀어야 한다.\n"
            "  ★ 번호를 바꾸면 참조도 깨진다. 같은 PR 에서 함께 고친다 —\n"
            "     test_section_references_resolve 가 그것을 잡는다.")


# ── 3 · 번호 연속성 ────────────────────────────────────────────
def test_subsection_numbers_are_contiguous():
    """하위 절이 1부터 연속인가.

    건너뛴 번호는 "지운 절" 인지 "빠뜨린 절" 인지 구분되지 않는다.
    지운 절은 슬롯을 유지하고 제목에 그 사실을 적는다(MASTER §0).
    """
    p = ROOT / "docs/MASTER.md"
    by_top: dict[str, list[int]] = {}
    for num, _, _ in _sections(p):
        m = re.match(r"^(\d+)-(\d+)([a-z]?)$", num)
        if not m or m.group(3):
            continue                           # 18-2a 류는 알파벳 분기다
        by_top.setdefault(m.group(1), []).append(int(m.group(2)))

    # ★ 0 부터 시작하는 것을 인정한다. `§10-0` 처럼 **머리말 슬롯**이
    #   앞에 붙는 절이 있고, MASTER 자신이 `## 0. 서술 규약` 을 쓴다.
    #   섞이는 것만 막으면 된다 — 0..n-1 이거나 1..n 이거나 하나여야 한다.
    bad = []
    for top, nums in sorted(by_top.items(), key=lambda kv: int(kv[0])):
        got = sorted(nums)
        ok = (got == list(range(1, len(got) + 1))
              or got == list(range(0, len(got))))
        if not ok:
            bad.append(f"  §{top}: {got} — 1..{len(got)} 또는 "
                       f"0..{len(got) - 1} 이어야 한다")

    assert not bad, ("하위 절 번호가 연속이 아니다\n" + "\n".join(bad)
                     + "\n\n  지운 절은 슬롯을 유지한다(MASTER §0).")


# ── 코드 → 문서 방향 ─────────────────────────────────────────────
#
# ★ 2026-09-24 (PLAN §13 W12-3 · DECISIONS §239). 위 검사들은 **문서 안의**
#   참조를 본다. `tools/*.py` 주석이 드는 `MASTER §N-M` 은 아무도 안 봤고,
#   `tools/docx_fix.py` 가 **실재하지 않는 절 넷**을 규칙의 근거로 들고 있었다
#   (`PLAN §12-4` · `§12-7` · `§12-2` · `MASTER §16-3`). 기획서를 실제로  ref-ok
#   고치는 도구의 근거라, 확인할 수 없으면 규칙을 검증할 수 없다.
#
# ★ 범위를 좁게 선언한다 — **문서 이름이 붙은 하위 절 참조**만 본다.
#   `PLAN §1-16`(표 행 번호) · `MASTER §18-5`(규칙 번호) · `§0-0`(묶음 표기)은
#   이 저장소의 관용이고 위 주석이 이미 그것을 든다. 그 셋은 대상이 아니다.
CODE_REF = re.compile(r"\b(MASTER|PLAN|DECISIONS)\s*§\s*(\d+)-(\d+)\b")

#: 절이 아닌 `N-M` 표기. 위 주석의 셋을 그대로 옮긴 것이다.
IDIOM = {("PLAN", "1"), ("PLAN", "0"), ("MASTER", "18")}

#: 일부러 **죽은 참조를 인용하는** 줄. 고친 경위를 적는 자리라 살아 있으면 안 된다.
REF_OK = "ref-ok"


def _code_files():
    for d in ("tools", "src", "tests"):
        for p in sorted((ROOT / d).rglob("*")):
            if p.suffix in (".py", ".sh", ".mjs") and "__pycache__" not in str(p):
                yield p


def _headings(doc: str) -> set[str]:
    t = (ROOT / "docs" / f"{doc}.md").read_text(encoding="utf-8")
    return set(re.findall(r"^### (\d+-\d+)\.", t, re.M))


def test_code_comments_do_not_cite_a_section_that_does_not_exist():
    """코드가 드는 `<문서> §N-M` 이 실재하는가."""
    have = {d: _headings(d) for d in ("MASTER", "PLAN", "DECISIONS")}
    assert all(len(v) > 40 for v in have.values()), \
        f"절 제목 수집이 죽었다: { {k: len(v) for k, v in have.items()} }"
    bad = []
    for p in _code_files():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore")
                                 .splitlines(), 1):
            if REF_OK in line:
                continue
            for doc, top, sub in CODE_REF.findall(line):
                if (doc, top) in IDIOM or f"{top}-{sub}" in have[doc]:
                    continue
                bad.append(f"  {p.relative_to(ROOT)}:{i}  {doc} §{top}-{sub}")
    assert not bad, (
        "코드 주석이 **없는 절**을 근거로 든다:\n" + "\n".join(bad) + "\n\n"
        "  절 번호를 고치거나, 일부러 죽은 참조를 인용하는 줄이면 그 줄에\n"
        f"  `{REF_OK}` 를 적어라. 근거를 확인할 수 없으면 규칙을 검증할 수 없다.")


def test_the_code_ref_probe_bites():
    """★ 빈 그물인가 — 0건이 되므로 합성 입력으로 확인한다."""
    have = {"MASTER": {"2-2"}, "PLAN": set(), "DECISIONS": set()}

    def judge(line: str) -> list[str]:
        if REF_OK in line:
            return []
        return [f"{d} §{t}-{s}" for d, t, s in CODE_REF.findall(line)
                if (d, t) not in IDIOM and f"{t}-{s}" not in have[d]]

    assert judge("# 근거는 MASTER §16-3 이다") == ["MASTER §16-3"]  # ref-ok
    assert judge("# 근거는 MASTER §2-2 이다") == []
    assert judge("# PLAN §1-16 행") == [], "표 행 번호를 절로 본다 — 오탐이 쏟아진다"
    assert judge("# MASTER §18-5 규칙") == [], "규칙 번호를 절로 본다"
    assert judge("# 종전에 MASTER §16-3 을 들었다  ref-ok") == []


def test_fence_handling_has_exactly_one_home():
    """★ 2026-09-24 (PLAN §13 W12-5). 같은 규칙이 시험 셋에 각자 살아 있었고
    그중 하나(`test_docref`)는 **펜스를 안 뺐다.** 오늘은 발현 안 하지만,
    펜스 안에 절 제목을 인용하는 회고 한 줄이 들어오면 이쪽만 빨개진다.

    이 저장소는 「정본이 둘이면 갈린다」를 강제자로 세운다
    (`tests/test_sources_of_truth.py`). 그 저장소에서 파서가 셋이었다.
    """
    assert docparse.selftest() == 0, "펜스 처리기의 자기검사가 빨갛다"
    users = ["tests/test_docref.py", "tests/test_doc_style.py",
             "tests/test_reproducibility.py"]
    bad = []
    for rel in users:
        src = (ROOT / rel).read_text(encoding="utf-8")
        if "docparse.prose_lines" not in src:
            bad.append(f"  {rel} 가 제 펜스 루프를 다시 짠다")
        # 손으로 짠 토글이 되살아났는가
        if re.search(r"fence\s*=\s*not\s+fence", src):
            bad.append(f"  {rel} 에 손으로 짠 펜스 토글이 있다")
    assert not bad, (
        "펜스 처리의 집이 둘 이상이다:\n" + "\n".join(bad) + "\n\n"
        "  `tests/docparse.prose_lines` 를 써라. 규칙이 갈리면 같은 문서에\n"
        "  대해 시험마다 다른 답이 나온다.")
