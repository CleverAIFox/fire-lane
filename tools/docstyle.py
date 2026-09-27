#!/usr/bin/env python3
"""
docstyle.py — 기획서에 **개요 층**이 있는가. 목차·북마크가 만들어지는가.  (DECISIONS §278-3)

    uv run python tools/docstyle.py            검사 (종료코드 = 결함 수)
    uv run python tools/docstyle.py --tree     잡힌 제목을 층째로 본다
    uv run python tools/docstyle.py --renumber 편 계층을 맞바꿔 셋을 같게 한다
    uv run python tools/docstyle.py --write    개요 층을 넣는다 (기획서를 고친다)
    uv run python tools/docstyle.py --selftest ★ 판별식이 살아 있나

── 왜 생겼나 (2026-09-28 실측) ────────────────────────────────
`docs/proposal.docx` 는 **문서 넷 중 유일하게 밖이 읽는 것**인데 —

    본문 522단락 중 `pStyle` 이 붙은 것      0개
    `styles.xml` 의 Heading 1~6 선언         있다 (아무도 안 쓴다)
    제목 흉내                                 굵은 글씨로만
    web/proposal.pdf 63쪽의 북마크            0개

★ **제목 계층이 사람 눈에만 있다.** 기계에는 평단락 522개뿐이다. 그래서
  자동 목차가 안 만들어지고 63쪽 PDF 에 북마크가 하나도 없다 — 읽는 쪽이
  스크롤로만 찾는다.

★ **Heading 스타일은 안 씌운다.** 씌우면 글꼴·크기·색이 워드 기본값으로
  바뀌어 **제출본 모양이 달라진다.** `w:outlineLvl` 만 넣으면 보이는 것은
  그대로이고 개요만 생긴다 — 목차도 북마크도 그것으로 만들어진다.

★ **Part 마다 계층이 다르다.** Part I·III 은 장을 `1.` 로 쓰고 그 아래를
  `□` 로 쓰는데, **Part II 는 장을 `□` 로 쓰고 `1.` 을 그 아래 항으로 쓴다.**
  꼴 하나로 층을 정하면 Part II 의 부모·자식이 뒤집힌다. 그래서 지도를
  Part 별로 나눠 선언한다 — 짐작하지 않는다.

IN    docs/proposal.docx
OUT   결함 목록 (비면 통과) · `--write` 면 개요 층을 넣은 docx
PARAM HIER · MAX_LEN
밖    **말투 · 어휘는 안 본다** — `tools/tonecheck.py` 소관이다.
      **내용이 산출물과 맞는지도 안 본다** — `tools/docx_check.py` 가 든다.
      **PDF 를 굽지 않는다** — `tools/proposal_pdf.py` 가 굽고, 개요가 있으면
      북마크는 그쪽이 자동으로 만든다. 여기는 **개요가 있는가**만 본다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "docs" / "proposal.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: 편(篇) 제목. 무조건 0층이다.
PART_RX = r"^Part\s+([IVX]+)\.\s"

#: 제목 꼴 — **바깥에서 안으로**. 차례가 곧 개요 층이다 (편이 0층).
#:
#: ★ **편이 달라도 같다.** 2026-09-28 첫 판에서는 편마다 다른 지도를 뒀었다 —
#:   Part I·III 은 `1.` 이 장인데 Part II 만 `□` 가 장이고 `1.` 이 그 아래
#:   항이었기 때문이다. 그것은 **엉망을 코드로 박제한 것**이지 고친 것이 아니다.
#:   기획서를 통일하고(`--renumber`) 지도를 하나로 되돌렸다(§278-7).
HIER: tuple[str, ...] = (
    r"^\d+\.\s",                  # 1층 — 장
    r"^□\s",                       # 2층 — 절
    r"^[a-d]\.\s",                 # 3층 — 항 (SWOT 교차 전략 넷)
)
#: 앞 제목보다 **한 층 안**으로 붙는 이름표. 절대층이 아니다 — `3. 시장현황`
#: 바로 아래에도 붙고 `□ 유사 서비스 분석` 아래에도 붙는다. 절대층으로 박으면
#: 앞의 경우가 두 층을 건너뛴 것으로 보여 「층 건너뜀」 검사가 헛울음을 운다.
LABEL_RX = r"^\[.+\]$|^\[\s*[\w/ ]+\]\s+\S"
#: 이보다 긴 줄은 제목이 아니라 문장이다. 굵게 쓴 강조 문장이 있다.
MAX_LEN = 70


def _bold_only(p) -> bool:
    rs = [r for r in p.runs if r.text.strip()]
    return bool(rs) and all(r.bold for r in rs)


def part_of(text: str) -> str | None:
    m = re.match(PART_RX, text.strip())
    return m.group(1) if m else None


def level_of(text: str, under: int = 0) -> int | None:
    """이 줄의 개요 층. 제목 꼴이 아니면 None.

    `under` 는 **바로 앞 절대층 제목**의 층이다. 이름표(`[…]`)만 그것을 쓴다.
    """
    s = text.strip()
    if not s or len(s) > MAX_LEN:
        return None
    if part_of(s):
        return 0
    for depth, rx in enumerate(HIER, start=1):
        if re.match(rx, s):
            return depth
    if re.match(LABEL_RX, s):
        return under + 1
    return None


def headings(doc) -> list[tuple[int, int, str, str | None]]:
    """(단락번호, 개요층, 글, 그 편) — 굵은 제목만. 이름표는 앞 절대층에 붙는다."""
    out, part, under = [], None, 0
    for i, p in enumerate(doc.paragraphs):
        s = p.text.strip()
        if not s or not _bold_only(p):
            continue
        lvl = level_of(s, under)
        if lvl is None:
            continue
        if not re.match(LABEL_RX, s):
            under = lvl                     # 이름표는 앞 절대층을 안 바꾼다
        part = part_of(s) or part
        out.append((i, lvl, s, part))
    return out


def survey(doc) -> tuple[list, list, list, list]:
    """(빠진 제목, 성한 제목, 꼴 밖인 줄, **층이 틀린** 제목).

    ★ 2026-09-28. 처음엔 「빠졌나」만 봤다. `--renumber` 로 `□ 요구사항 ID 체계`
      가 `2. 요구사항 ID 체계` 가 되자 **글은 1층인데 박힌 개요는 2층**으로
      남았다 — 빠진 것이 아니라 **틀린 것**이고, 「빠졌나」만 보는 검사는
      그것을 초록으로 통과시킨다. 셋째 갈래가 그 자리다.
    """
    miss, have, wrong = [], [], []
    seen = {i for i, _l, _s, _q in headings(doc)}
    for i, lvl, s, _q in headings(doc):
        pr = doc.paragraphs[i]._p.find(f"{W}pPr")
        cur = pr.find(f"{W}outlineLvl") if pr is not None else None
        if cur is None:
            miss.append((i, lvl, s))
        elif int(cur.get(f"{W}val") or -1) != lvl:
            wrong.append((i, lvl, s, int(cur.get(f"{W}val") or -1)))
        else:
            have.append((i, lvl, s))
    odd, part = [], None
    for i, p in enumerate(doc.paragraphs):
        s = p.text.strip()
        part = part_of(s) or part
        if s and i not in seen and _bold_only(p) and len(s) <= MAX_LEN:
            odd.append((i, part, s))
    return miss, have, odd, wrong


def skips(doc) -> list[str]:
    """★ 개요가 층을 **건너뛰는가.** 편마다 계층이 갈리면 여기서 걸린다.

    2026-09-28 이전 Part II 가 `Part(0) → □(2) → 1.(1)` 이었다 — 0 에서 2 로
    건너뛰고 그 아래에 더 얕은 1 이 붙었다. 목차가 그 편만 한 칸 밀려 나오고
    부모·자식이 뒤집힌다. **쪽수도 북마크 수도 안 변해서** 수치로는 안 걸린다.
    """
    bad, prev = [], -1
    for _i, lvl, s, q in headings(doc):
        if lvl > prev + 1:
            bad.append(f"Part {q} — L{prev} 다음에 L{lvl} 이 온다: {s[:52]}")
        prev = lvl
    return bad


def _dead(doc) -> list[str]:
    """`HIER` · `LABEL_RX` 에 선언했는데 실물에서 한 번도 안 걸린 꼴.

    선언이 한 번도 안 걸리면 그것은 통과가 아니라 **죽은 선언**이다 — 볼 것이
    없는 그물은 초록으로 위장한다(§230 과 같은 자리).
    """
    live = set()
    for _i, _l, s_, _q in headings(doc):
        for rx in (*HIER, LABEL_RX):
            if re.match(rx, s_):
                live.add(rx)
                break
    return [f"`{rx}`" for rx in (*HIER, LABEL_RX) if rx not in live]


def swap_plan(doc) -> list[tuple[int, str, str]]:
    """편 계층이 뒤집힌 곳의 (단락번호, 옛 글, 새 글).

    ★ 규칙은 하나다 — **편 바로 아래 첫 층이 `□` 면 그 편의 `□` 와 `N.` 을
      맞바꾼다.** Part II 만 걸리지만 규칙은 편을 안 가린다. 고친 뒤 다시 돌리면
      아무것도 안 나온다(멱등).

    ★ `N.` 이 `□` 로 내려갈 때 번호를 버린다. 그 번호는 원래 군 번호였고
      (`1. REQ-DAT` … `10. REQ-EVL`) 군 이름 자체가 식별자라 중복이다.
      `□` 가 `N.` 으로 올라갈 때는 편 안에서 1부터 다시 센다.
    """
    plan, cur, bucket = [], None, []

    def flush():
        if not bucket or bucket[0][1] != 2:
            return
        n = 0
        for i, lvl, txt in bucket:
            if lvl == 2:
                n += 1
                plan.append((i, txt, re.sub(r"^□\s*", f"{n}. ", txt)))
            elif lvl == 1:
                plan.append((i, txt, re.sub(r"^\d+\.\s*", "□ ", txt)))

    for i, lvl, txt, _q in headings(doc):
        if lvl == 0:
            flush(); bucket = []; cur = txt
            continue
        if lvl in (1, 2):
            bucket.append((i, lvl, txt))
    flush()
    _ = cur
    return plan


def renumber() -> int:
    """기획서를 고쳐 **세 편의 계층을 같게** 만든다. 보이는 글이 바뀐다."""
    d = _open()
    plan = swap_plan(d)
    if not plan:
        print("  맞바꿀 것이 없다 — 편 계층이 이미 같다")
        return 0
    for i, old, _new in plan:
        if len(doc_runs := [r for r in d.paragraphs[i].runs if r.text]) != 1:
            print(f"✗ 단락 {i} 이 run {len(doc_runs)}개다 — 손대면 서식이 갈린다: {old[:48]}")
            return 1
    for i, _old, new in plan:
        [r for r in d.paragraphs[i].runs if r.text][0].text = new
    d.save(str(DOCX))
    print(f"✓ 제목 {len(plan)}개를 맞바꿨다 — 세 편의 계층이 같아졌다")
    for _i, old, new in plan[:6]:
        print(f"    {old[:44]:<46} → {new[:44]}")
    if len(plan) > 6:
        print(f"    … {len(plan) - 6}개 더")
    print("  ★ 개요 층을 다시 넣어라:  uv run python tools/docstyle.py --write")
    return 0


def _set_level(p, lvl: int) -> None:
    """`w:outlineLvl` 만 넣는다. **글꼴 · 크기 · 색은 안 건드린다.**"""
    from docx.oxml.ns import qn  # noqa: PLC0415
    from docx.oxml.shared import OxmlElement  # noqa: PLC0415
    pr = p._p.get_or_add_pPr()
    if (old := pr.find(f"{W}outlineLvl")) is not None:
        pr.remove(old)
    e = OxmlElement("w:outlineLvl")
    e.set(qn("w:val"), str(lvl))
    pr.append(e)


def _open():
    import docx  # noqa: PLC0415
    return docx.Document(str(DOCX))


def check() -> int:
    if not DOCX.is_file():
        print(f"✗ {DOCX.relative_to(ROOT)} 가 없다 — 못 잰 것을 통과로 세지 않는다")
        return 1
    d = _open()
    miss, have, odd, wrong = survey(d)
    bad: list[str] = []
    for s in _dead(d):
        bad.append(f"{s} 가 실물에서 한 번도 안 걸린다 — 죽은 선언이다. 지워라")
    if not (miss or have):
        bad.append("제목이 하나도 안 잡혔다 — `HIER` 가 실물과 갈렸다. 판별식을 의심하라")
    for t in skips(d):
        bad.append(f"개요가 층을 건너뛴다 — {t}")
    if swap_plan(d):
        bad.append("편마다 장(章) 꼴이 다르다 — `--renumber` 가 맞바꾼다")
    if wrong:
        bad.append(f"개요 층이 **틀린** 제목 {len(wrong)}개 — 글은 바뀌었는데 층이 안 따라왔다")
        for _i, lvl, t, got in wrong[:6]:
            bad.append(f"      L{got} 로 박혀 있는데 L{lvl} 이어야 한다: {t[:48]}")
    if miss:
        bad.append(f"개요 층이 없는 제목 {len(miss)}/{len(miss) + len(have) + len(wrong)}")

    if not bad:
        print(f"✓ 개요 층 — 제목 {len(have)}개 전부에 `outlineLvl` 이 있다 "
              f"(목차 · PDF 북마크가 만들어진다)")
        if odd:
            print(f"  참고 — 꼴 밖인데 굵은 짧은 줄 {len(odd)}개는 제목으로 안 본다 (`--tree`)")
        return 0

    print("✗ " + "\n✗ ".join(bad))
    for _i, lvl, s in miss[:10]:
        print(f"      L{lvl}  {s[:64]}")
    if len(miss) > 10:
        print(f"      … {len(miss) - 10}개 더 (`--tree`)")
    if miss:
        print("\n  제목 계층이 **사람 눈에만** 있다 — 자동 목차도 PDF 북마크도 안 만들어진다.")
        print("  넣는 법:  uv run python tools/docstyle.py --write")
        print("  ★ 글꼴 · 크기 · 색은 안 바뀐다. `w:outlineLvl` 만 넣는다.")
    return len(bad) + len(miss)


def write() -> int:
    d = _open()
    if t := skips(d):
        print("✗ 개요가 층을 건너뛴다 — 먼저 `--renumber` 로 편 계층을 맞춰라")
        for x in t:
            print(f"    {x}")
        return 1
    miss, have, _odd, wrong = survey(d)
    if not (miss or wrong):
        print(f"  넣을 것이 없다 — 제목 {len(have)}개 전부 제 층에 있다")
        return 0
    for i, lvl, _s in miss:
        _set_level(d.paragraphs[i], lvl)
    for i, lvl, _s, _got in wrong:      # ★ 틀린 것도 고친다. 빠진 것만 채우면 안 된다
        _set_level(d.paragraphs[i], lvl)
    d.save(str(DOCX))
    print(f"✓ 개요 층 — 넣음 {len(miss)} · 고침 {len(wrong)} (성했던 것 {len(have)})")
    print("  ★ 글꼴 · 크기 · 색은 안 건드렸다. 다음 `proposal_pdf` 굽기부터 북마크가 생긴다.")
    return 0


def tree() -> int:
    miss, have, odd, wrong = survey(_open())
    for _i, lvl, s in sorted(miss + have + [(a, b, c) for a, b, c, _d in wrong]):
        print(f"  {'   ' * lvl}{'·' if lvl else '■'} {s[:76]}")
    if odd:
        print(f"\n  꼴 밖 — 제목으로 안 본다 ({len(odd)}개)")
        for _i, p, s in odd:
            print(f"      [{p or '편 밖'}] {s[:70]}")
    return 0


def selftest() -> int:
    """★ 꼴이 제 층으로 가는가. 층 건너뜀과 맞바꿈 규칙이 실제로 도는가."""
    bad = []
    if level_of("Part II. 요구사항 분석서") != 0:
        bad.append("편 제목을 못 잡는다")
    for depth, rx in enumerate(HIER, start=1):
        ex = {1: "1. 프로젝트 개요", 2: "□ 강제연결법", 3: "a. SO 전략"}[depth]
        if level_of(ex) != depth:
            bad.append(f"`{rx}` 의 예시 {ex!r} 가 L{level_of(ex)} 로 잡힌다 — 선언은 L{depth}")
    if len(HIER) != len(set(HIER)):
        bad.append("`HIER` 에 같은 꼴이 두 번 있다")
    # ★ 이름표는 **앞 제목 한 층 안**이다. 절대층으로 박으면 층 건너뜀이 헛울음을 운다.
    if level_of("[분석 요약]", under=1) != 2 or level_of("[분석 요약]", under=2) != 3:
        bad.append("이름표가 앞 제목을 안 따라간다 — 절대층으로 굳었다")
    if level_of("[ road_segment ] 노딩 완료된 도로 세그먼트", under=2) != 3:
        bad.append("`[ 표이름 ] 설명` 꼴을 제목으로 안 본다")
    if level_of("이것은 제목이 아니라 그냥 문장이다. 판정은 꼴과 폭으로 한다.") is not None:
        bad.append("평범한 문장을 제목으로 본다")
    if level_of("1. " + "가" * 90) is not None:
        bad.append(f"{MAX_LEN}자를 넘는 줄을 제목으로 본다 — 굵게 쓴 강조 문장이 있다")
    if level_of("") is not None:
        bad.append("빈 줄을 제목으로 본다")
    if not HIER:
        bad.append("`HIER` 가 비었다 — 볼 것이 없으면 통과가 아니다")

    # ★ 합성 문서로 「층 건너뜀」과 「맞바꿈」을 실제로 돌린다. 2026-09-28 이전
    #   Part II 가 정확히 이 꼴이었다 — 0 에서 2 로 뛰고 그 아래에 더 얕은 1.
    class _R:
        def __init__(s_, t): s_.text, s_.bold = t, True
    class _P:
        def __init__(s_, t): s_.text, s_.runs = t, [_R(t)]
    class _D:
        def __init__(s_, ts): s_.paragraphs = [_P(t) for t in ts]
    bent = _D(["Part II. 요구사항 분석서", "□ 체계도", "1. REQ-DAT", "□ 제약사항"])
    if not skips(bent):
        bad.append("편이 뒤집힌 문서에서 층 건너뜀을 안 잡는다")
    plan = swap_plan(bent)
    if [n for _i, _o, n in plan] != ["1. 체계도", "□ REQ-DAT", "2. 제약사항"]:
        bad.append(f"맞바꿈이 틀렸다 — {[n for _i, _o, n in plan]}")
    flat = _D(["Part I. 제안서", "1. 개요", "□ 절", "2. 다음 장"])
    if skips(flat):
        bad.append(f"성한 문서를 건너뜀으로 본다 — {skips(flat)}")
    if swap_plan(flat):
        bad.append("성한 편을 맞바꾸려 한다 — 멱등이 깨진다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 꼴 {len(HIER) + 1}개가 제 층으로 가고, "
          "뒤집힌 편을 잡고, 성한 편은 안 건드린다")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="기획서 개요 층 검사")
    ap.add_argument("--write", action="store_true", help="개요 층을 넣는다")
    ap.add_argument("--renumber", action="store_true",
                    help="편 계층을 맞바꿔 셋을 같게 한다 (보이는 글이 바뀐다)")
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.renumber:
        return renumber()
    if a.tree:
        return tree()
    return write() if a.write else check()


if __name__ == "__main__":
    sys.exit(main())
