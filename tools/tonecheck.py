#!/usr/bin/env python3
"""
tonecheck.py — 문서와 주석의 **말투**. `FAMILIES` 가 드는 족이 새는가.  (DECISIONS §278)

    uv run python tools/tonecheck.py            검사 (종료코드 = 건수)
    uv run python tools/tonecheck.py --list     무엇을 어디까지 보는지
    uv run python tools/tonecheck.py --selftest ★ 판별식이 살아 있나

── 왜 생겼나 (2026-09-28) ─────────────────────────────────────
`DECISIONS` 에 **`## 277. 봉인지 땅따먹기`** 라는 제목이 들어갔다. 우리 둘이
대화에서 쓰던 은어를 **정본 문서의 절 제목**에 그대로 옮긴 것이다. 같은 파일
`§236` 에는 사용자 지시를 인용하면서 **욕설을 그대로** 옮긴 줄이 있었다.

★ **말투에는 강제자가 하나도 없었다.** `docseal` 은 「절과 코드가 갈렸나」를 묻고,
  `doc_fsck` 는 「가리킨 것이 실재하나」를 묻는다. 둘 다 **뭐라고 적혀 있는지**는
  안 본다. 그래서 새는 것을 아무도 못 봤고, 사람이 우연히 읽어야 알았다.

★ **기획서가 제일 위험하다.** `docs/proposal.docx` 는 문서 넷 중 **유일하게
  외부가 읽는 것**인데 `docx_check`(숫자)와 `doc_fsck ⑥`(날짜)만 물었다.
  그래서 여기는 **docx 본문까지** 연다.

IN    docs/*.md · docs/proposal.docx · README 3종 · src·tools·tests·web 의 주석
OUT   결함 목록 (비면 통과) · 종료코드 = 건수
PARAM FAMILIES · EXEMPT
밖    **뜻이 옳은가는 안 본다** — 그것은 사람이 읽고 `docseal` 로 찍는다.
      **사람 이름도 안 센다** — 저자 서명 · 담당 표 · 출처 인용이 전부 정상이고,
      세면 141건 오탐이 본문을 덮는다(2026-09-28 실측). 사람에 대한 평가는
      낱말로 못 잡는다 — 그것은 리뷰의 일이다.
      **격식 · 종결어미 · 표 형식도 안 본다** — 문서 종류마다 규칙이 달라
      한 도구가 들면 어느 쪽도 제대로 못 본다. 기획서 구조는 `tools/docstyle.py`.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 낱말 족 — 무엇을 왜 막는가. **사유가 없으면 목록에 넣지 않는다.**
#:
#: ★ 2026-09-28. 처음엔 **부분문자열 목록**이었다. `미친` 하나로 `못 미친다`
#:   셋이 걸렸다 — 「기준폭에 못 미친다」는 멀쩡한 우리말이다. 오늘 하루에만
#:   느슨한 그물을 넷 만났고(§273-13 · §276-5 · §278-1) 전부 같은 형태다.
#:   **정규식으로 못박는다** — 낱말 하나하나가 언제 결함인지를 적는다.
#: 값은 **정규식**이다. 부분문자열이 아니다.
FAMILIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "비속어": (
        "정본 문서는 밖으로 나간다. 인용이어도 옮겨 적지 않는다 — 요지를 적는다.",
        (r"좆", r"씨발", r"시발", r"개소리", r"존나", r"졸라", r"지랄", r"병신",
         # `못 미친다` · `미치지 않는다` 는 멀쩡한 말이다. **수식하는 «미친»** 만 문다.
         r"(?<!못 )(?<!에 )미친(?![다지게함])",
         r"빡치", r"개같", r"엿같", r"닥쳐", r"염병", r"개판"),
    ),
    "은어": (
        "우리 둘이 대화에서 쓰는 말이다. 다음 사람은 그 말을 모른다 — 뜻을 적는다.",
        (r"땅따먹기", r"꼬라지", r"삽질", r"뻘짓", r"노가다", r"뇌피셜",
         r"후려치", r"막장", r"깽판", r"존버", r"현타", r"킹받", r"쌉[가-힣]"),
    ),
    # ★ 2026-10-05 신설 (DECISIONS §396 · PLAN #148). 기관·조직 이름을 줄여
    #   쓰면 밖에서 읽는 사람이 **무엇인지 모른다.** 기획서는 밖으로 나가고,
    #   이 저장소는 취업 포트폴리오다 — 줄임말 하나가 「이 사람은 누구 소속이었나」를
    #   통째로 가린다. 사람이 「광인사라고 쓰지 마라」로 정했다(2026-10-04).
    #   ★ 표에 **정식 이름을 같이** 둔다. 「쓰지 마라」만 적으면 다음 사람이
    #     무엇으로 바꿀지 모르고, 모르면 또 줄여 쓴다.
    "약칭": (
        "기관 이름을 줄여 쓰면 밖에서 읽는 사람이 무엇인지 모른다. "
        "정식 이름으로 적는다 — 광인사 → 광주 인공지능사관학교.",
        (r"광인사",),
    ),
    "대화체": (
        "채팅 흔적이다. 문서는 대화록이 아니다.",
        ("ㅋㅋ", "ㅎㅎ", "ㅇㅇ", "ㄱㄱ", "ㅠㅠ", "ㅜㅜ", "ㄷㄷ", "ㅡㅡ", "ㅇㅋ"),
    ),
}

#: 「이 줄은 일부러 그 말을 인용한다」 표시. **이 저장소에 이미 있는 규약**이고
#: `MASTER §0-3` 이 선언한다 — 여기서 새 표시를 만들지 않는다. 산문 판정도
#: `tests/docparse.py` 하나를 쓴다. 두 벌이면 「무엇이 인용인가」가 갈린다.
#:
#: ★ 2026-10-05 (DECISIONS §399-5). **닫는 `-->` 를 뺐다.** 종전에는 맨몸
#:   `<!--voice-ok-->` 만 받았고, `tools/suppress.py` 는 **사유 없는 억제**를
#:   세면서 그 맨몸을 빚으로 셌다. 즉 사유를 적으면 이쪽이 울고, 안 적으면
#:   저쪽이 늘었다 — 같은 표기를 두 관문이 반대로 요구했다(2족). 접두로
#:   바꾸면 `<!--voice-ok 사람 말 그대로-->` 가 양쪽을 다 통과하고, **사유를
#:   적는 쪽이 싸진다.** 맨몸은 여전히 통하지만 빚으로 세어진다.
ALLOW = "<!--voice-ok"

#: 면제 — `"경로::낱말"` → 사유. **적는 순간 세어지고, 죽은 면제는 시험이 지운다.**
EXEMPT: dict[str, str] = {
    "tools/tonecheck.py::*": "이 파일이 목록 자신이다. 낱말을 적어야 막을 수 있다",
    "tests/test_tonecheck.py::*": "판별식 시험이 낱말을 심는다",
}

#: 문서 — 정본 넷과 README 셋.
DOCS = ("docs/MASTER.md", "docs/PLAN.md", "docs/DECISIONS.md",
        "README.md", "web/README.md", "src/firelane/README.md")
#: 주석을 볼 코드 뿌리.
CODE = ("src", "tools", "tests", "web/navi/src", "web/navi/test")
CODE_SUFFIX = (".py", ".sh", ".ts", ".tsx", ".js", ".mjs")
#: 외부가 읽는 문서. **본문을 연다.**
DOCX = "docs/proposal.docx"


def exempt(rel: str) -> bool:
    return f"{rel}::*" in EXEMPT


def _docparse():
    """`tests/docparse.py` — **산문 판정의 정본**. 여기서 다시 짜지 않는다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dp_tone", ROOT / "tests/docparse.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _docx_text(p: Path) -> str:
    """기획서 본문 + 표. 못 열면 **빈 문자열이 아니라 예외**다 — 조용한 통과 금지."""
    import docx  # noqa: PLC0415  (선택 의존성)
    d = docx.Document(str(p))
    out = [x.text for x in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            out += [c.text for c in r.cells]
    return "\n".join(out)


def targets() -> list[tuple[str, str]]:
    """(경로, 본문). **무엇을 보는지가 이 함수 하나에 있다.**"""
    out: list[tuple[str, str]] = []
    dp = _docparse()
    for rel in DOCS:
        p = ROOT / rel
        if not p.is_file():
            continue
        # ★ 코드 펜스 · 4칸 블록 · `voice-ok` 줄을 뺀다 — 인용을 위반으로 세면
        #   회고를 못 쓰게 되고, 그러면 사람이 검사를 끈다(docparse 머리말).
        keep = {i for i, _ in dp.prose_lines(p, skip_indented=True, allow=ALLOW)}
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        # ★ **표식 줄은 남긴다.** `docparse` 가 그것을 먼저 지우면 `_allowed_block`
        #   이 인용 블록의 시작을 못 보고, 그러면 표시를 달아도 안 먹는다.
        #   실제로 그렇게 짰다가 `§236` 인용이 계속 걸렸다.
        keep |= {i for i, l in enumerate(lines, 1) if ALLOW in l}
        out.append((rel, "\n".join(l if i in keep else ""
                                    for i, l in enumerate(lines, 1))))
    dp = ROOT / DOCX
    if dp.is_file():
        out.append((DOCX, _docx_text(dp)))
    for root in CODE:
        base = ROOT / root
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if (p.is_file() and p.suffix in CODE_SUFFIX
                    and "node_modules" not in p.parts and "__pycache__" not in p.parts):
                out.append((p.relative_to(ROOT).as_posix(),
                            p.read_text(encoding="utf-8", errors="replace")))
    return out


def _allowed_block(lines: list[str]) -> set[int]:
    """`<!--voice-ok-->` 가 **앞줄에 홀로** 있으면 뒤따르는 블록 전체가 인용이다.

    ★ 실측한 규약이다(2026-09-28). `docparse` 는 표시가 **같은 줄에** 있는
      경우만 빼는데, 이 저장소는 표시를 **인용 블록 바로 앞줄**에 단다 —
      `DECISIONS §236` · `tools/docx_figs.py` 둘 다 그렇다. 규약을 바꾸는 것이
      아니라 **쓰이는 대로 읽는다.** 블록은 빈 줄에서 끝난다.
    """
    out: set[int] = set()
    i = 0
    while i < len(lines):
        if ALLOW in lines[i]:
            out.add(i + 1)
            j = i + 1
            while j < len(lines) and lines[j].strip():
                out.add(j + 1)
                j += 1
            i = j
        i += 1
    return out


def scan(items: list[tuple[str, str]] | None = None) -> list[str]:
    items = targets() if items is None else items
    bad: list[str] = []
    for rel, text in items:
        if exempt(rel):
            continue
        rows = text.splitlines()
        skip = _allowed_block(rows)
        for i, line in enumerate(rows, 1):
            if i in skip:
                continue
            for fam, (_why, words) in FAMILIES.items():
                for w in words:
                    m = re.search(w, line)
                    if m:
                        bad.append(f"{rel}:{i}  [{fam}] {m.group()}  …{line.strip()[:70]}")
    return bad


def selftest() -> int:
    """★ 족마다 하나씩 심고 **전부** 울어야 한다. 하나라도 조용하면 그 족은 죽었다."""
    bad = []
    for fam, (why, words) in FAMILIES.items():
        if not words:
            bad.append(f"`{fam}` 족이 비었다 — 볼 것이 없으면 통과가 아니다")
            continue
        if len(why) < 20:
            bad.append(f"`{fam}` 의 사유가 너무 짧다 — 왜 막는지 못 읽는다")
        hit = scan([("x.md", f"앞 {words[0]} 뒤")])
        if not hit:
            bad.append(f"`{fam}` 을 심었는데 안 운다 — 빈 그물이다")
    if scan([("x.md", "멀쩡한 문장이다. 판정은 폭으로 한다.")]):
        bad.append("멀쩡한 문장에 운다")
    # ★ 초록 안내가 **족 목록에서 유도되는가.** 손으로 적으면 족이 늘 때 낡는다.
    if '" · ".join(FAMILIES)' not in pathlib.Path(__file__).read_text(encoding="utf-8"):
        bad.append("초록 안내가 족 이름을 손으로 든다 — 족이 늘면 낡는다")
    if not exempt("tools/tonecheck.py"):
        bad.append("면제가 안 먹는다 — 목록 파일 자신이 걸린다")
    if exempt("docs/MASTER.md"):
        bad.append("면제가 너무 넓다 — 정본 문서가 빠진다")
    if not EXEMPT:
        bad.append("`EXEMPT` 가 비었다 — 면제 대장이 비면 그 칸이 죽은 칸이다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 족 {len(FAMILIES)}개가 다 울고, 멀쩡한 문장에는 조용하다")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="문서·주석 말투 검사")
    ap.add_argument("--list", action="store_true", help="무엇을 어디까지 보는가")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.list:
        print(f"  문서 {len(DOCS)} · 기획서 {DOCX} · 코드 뿌리 {len(CODE)}")
        for fam, (why, words) in FAMILIES.items():
            print(f"\n  [{fam}] {len(words)}낱말 — {why}")
        print(f"\n  면제 {len(EXEMPT)}")
        for k, v in EXEMPT.items():
            print(f"    {k}  — {v}")
        return 0
    bad = scan()
    if not bad:
        n = len(targets())
        # ★ 2026-10-05 (§396). 종전에는 족 이름 셋을 **손으로** 적었다.
        #   약칭 축을 늘리자마자 그 줄이 낡았다 — 늘린 사람이 안내를
        #   고쳐야 하는 구조 자체가 드리프트 원인이다(§73 과 같은 꼴).
        print(f"✓ 말투 — {n}개 파일에서 " + " · ".join(FAMILIES) + " 0건")
        return 0
    print(f"✗ 말투 {len(bad)}건 — **정본 문서는 밖으로 나간다**")
    for b in bad:
        print(f"    {b}")
    print("\n  인용이어도 옮겨 적지 않는다 — 요지를 적어라.")
    print("  정말 필요하면 `EXEMPT` 에 **사유와 함께** 적는다.")
    return len(bad)


if __name__ == "__main__":
    sys.exit(main())
