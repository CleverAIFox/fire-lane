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

ROOT = Path(__file__).resolve().parent.parent

# ★ 참조는 세 문서 어디든 가리킨다. 처음에 MASTER 만 정본으로 잡았다가
#   114건이 오탐으로 떴다 — `PLAN §4-4` · `DECISIONS §7-5` 가 그것이다.
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
    """(절번호, 제목, 줄번호)."""
    if not p.exists():
        return []
    out = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
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
    if not have:
        return

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
    #   절**로 좁힌다. 지금은 §12 하나다. 새 절이 그 체계를 갖추면
    #   자동으로 대상에 들어온다 — 목록을 손으로 관리하지 않는다.
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
