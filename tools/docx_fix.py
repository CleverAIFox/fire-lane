#!/usr/bin/env python3
"""
docx_fix.py — 기획서의 낡은 숫자·용어를 산출물 기준으로 고친다.

── 왜 별도 도구인가 ────────────────────────────────────────────
`docx_check.py` 는 어긋남을 **찾을** 뿐이다. docx 는 텍스트가 run 단위로
쪼개져 있어 손으로 고치면 반드시 빠뜨린다 — 같은 문장이 표 안에 다시
나오는 자리가 여섯 곳이었다.

★ R9(문자열 치환 패처 금지)의 예외가 아니다. R9 가 막는 것은 **소스
  코드**를 스크립트로 고치는 것이다. docx 는 git diff 가 안 되는 바이너리라
  사람이 diff 로 검토할 수 없고, 그래서 도구가 필요한 반대 경우다.

IN    docs/*.docx · 규칙표는 `tools/docxrules.py`
OUT   docs/*.docx (제자리 수정) · `--touch` 일 때만 `docs/proposal.md` 의 날짜 두 줄
PARAM --write 없이는 아무것도 쓰지 않는다
밖    **`docs/*.md` 의 숫자는 안 고친다.** 정본 셋(MASTER · PLAN · DECISIONS)의
      숫자는 `docnum_check.py` 가 대조하고 사람이 고친다 — `.md` 는 diff 가
      되므로 도구가 손댈 이유가 없고, 손대면 R9(문자열 치환 패처 금지)를 어긴다.
      **무엇이 옳은 문장인가는 안 고른다** — 규칙은 사람이 쓰고 정본은 골든이다.
      ★ 2026-10-09 (§440-8). **`--touch` 만 예외다.** 종전 이 칸은 「`docs/*.md`
        는 안 고친다」였고 그 사이 기획서 정본이 md 로 옮겨(§425) **표지 날짜가
        여드레 낡았다.** 날짜는 위 문단이 지키려는 것(사람이 판단할 숫자)이
        아니라 **그날을 받아 적는 한 값**이고, R9 가 막는 것은 소스 코드다.
        경계를 옮겼으므로 조용히 넘지 않고 여기 적는다.

★ **2026-09-30 (DECISIONS §333). 고친 뒤 스스로 대조한다** — `--write` 가
  끝나면 `unreachable()` 이 찾는 쪽을 직접 부른다. 사유는 그 절이 든다.
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docxrules import inserts, rules

ROOT = Path(__file__).resolve().parent.parent


def touch_rules(day: str) -> list[tuple[str, str, str]]:
    """`--touch YYYY-MM-DD` — 표지 최종 수정일과 수치 기준일을 그날로 옮긴다.

    ★ 2026-09-22 (DECISIONS §218). 날짜는 **규칙이 아니다** — 규칙에 넣으면 다음 날
      `docx_check` ⑤ 가 「아직 바꿀 것이 있다」로 매일 운다. 사람이(배치가) 기획서를 고친 날
      명시적으로 찍는다. `doc_fsck` ⑥ 이 「고쳤는데 표지가 그대로인가」를 본다.
    """
    y, m, d = day.split("-")
    return [
        (r"최종 수정 \d{4}\. \d{2}\. \d{2}\.", f"최종 수정 {y}. {m}. {d}.", "--touch"),
        (r"모든 수치는 \d{4}-\d{2}-\d{2} 기준으로", f"모든 수치는 {day} 기준으로", "--touch"),
    ]


def touch_md(day: str, write: bool) -> int:
    """`docs/proposal.md` 의 표지 날짜도 같이 옮긴다.  (2026-10-09 · §440-8)

    ★ **정본이 md 다**(§425). 날짜를 docx 에만 찍으면 둘이 갈리고, 실측에서
      갈려 있었다 — docx 표지 `2026. 10. 09.` · md 표지 `2026. 10. 01.`
      그리고 사람이 읽는 `web/proposal.html` 은 **md 쪽**을 띄운다. 낡은 날짜가
      밖으로 나가는 쪽이 정본이었다.
    ★ 규칙은 `touch_rules` 와 **같은 둘**을 쓴다. 두 벌로 적으면 한쪽만 고친다.
    ★ docx 가 은퇴하면 이 함수가 `--touch` 의 전부가 된다.
    """
    md = ROOT / "docs" / "proposal.md"
    if not md.is_file():
        return 0
    src = md.read_text(encoding="utf-8")
    out = src
    for rx, rep, _ in touch_rules(day):
        out = re.sub(rx, rep, out)
    n = sum(1 for a, b in zip(src.splitlines(), out.splitlines(), strict=True) if a != b)
    if write and out != src:
        md.write_text(out, encoding="utf-8")
    print(f"  proposal.md  줄 {n}개 {'수정' if write else '수정 예정'}")
    return n


def fix(p: Path, write: bool, extra: list | None = None) -> int:
    import docx
    from docx.oxml.ns import qn
    d = docx.Document(str(p))
    R = rules() + (extra or [])
    n = 0

    def do(par) -> int:
        """run 단위로 먼저, 안 되면 문단 단위로.

        ★ docx 는 텍스트가 run 으로 임의 분할된다. `PostGIS 적재` 가
          `PostG` + `IS 적재` 두 run 에 걸쳐 있으면 run 단위 치환이
          조용히 통과한다 — 이 저장소가 계속 겪은 조용한 실패다.
          그래서 문단 전체로 한 번 더 본다.

        ★ 2026-09-24 (DECISIONS §244). `par.runs` 는 문단의 **직계 `w:r` 만**
          준다. 하이퍼링크(`w:hyperlink`) 안의 run 은 거기 안 잡히고, 그런
          문단은 `par.text` 로는 보이는데 **고칠 수는 없었다** — `par.runs`
          가 비거나 짧아 아래 문단 단위 경로도 못 쓴다(첫 run 에 몰아넣으면
          링크 밖 텍스트가 사라진다). 실제로 §1 요약 문단이 그 꼴이라
          「통행 불가 191」이 한 자리만 고쳐지고 다른 자리는 남았다.
          그래서 **`w:t` 를 직접 순회한다** — 링크 안이든 밖이든 텍스트는
          거기 있다.
        """
        c = 0
        for t_el in par._p.iter(qn("w:t")):
            t0 = t_el.text or ""
            t = t0
            for rx, rep, _ in R:
                t = re.sub(rx, rep, t)
            if t != t0:
                t_el.text = t
                c += 1

        # run 경계를 넘는 구절
        whole = par.text
        fixed = whole
        for rx, rep, _ in R:
            fixed = re.sub(rx, rep, fixed)
        if fixed != whole and par.runs:
            # ★ 첫 run 에 몰아넣으면 그 문단의 부분 서식이 사라진다.
            #   숫자·용어 교정이 서식보다 중요하므로 감수하되 세어서 알린다.
            par.runs[0].text = fixed
            for r in par.runs[1:]:
                r.text = ""
            c += 1
        return c

    import copy

    def ins(pars) -> int:
        """앵커 뒤에 새 문단을 넣는다. 이미 있으면 안 넣는다.

        ★ 2026-09-24 (DECISIONS §244). **삽입 문장은 치환 규칙과 같은 문서를
          쓴다.** 규칙이 「통행 불가 191」을 「191(하한)」으로 고치는데 여기
          하드코딩된 문장이 옛 꼴이면, `do()` 가 고친 뒤 이 함수가
          「그 문단이 없다」고 보고 **옛 문장을 다시 넣는다** — 같은 문단이
          둘이 되고 하나는 영원히 안 고쳐진다. 실제로 그렇게 났다.
          규칙을 더할 때 이 목록도 같이 본다.
        """
        c = 0
        for anchor, new, _ in inserts():
            for i, par in enumerate(pars):
                if par.text != anchor:
                    continue
                if i + 1 < len(pars) and pars[i + 1].text == new:
                    continue
                el = copy.deepcopy(par._p)
                par._p.addnext(el)
                from docx.text.paragraph import Paragraph
                q = Paragraph(el, par._parent)
                q.runs[0].text = new
                for r in q.runs[1:]:
                    r.text = ""
                c += 1
        return c

    for par in d.paragraphs:
        n += do(par)
    # 이어 붙는 삽입(①→②→③ …)은 한 번으로 안 끝난다 — 더 넣을 것이 없을 때까지 돈다
    while (k := ins(d.paragraphs)):
        n += k
    seen = set()
    for t in d.tables:
        for r in t.rows:
            for cell in r.cells:
                # ★ 병합 셀은 행마다 같은 `_tc` 로 되풀이된다. id() 로 세면 proxy 가 버려진 뒤
                #   번호가 재사용돼 **다른 셀을 건너뛴다** — 원소 자체를 쥔다
                if cell._tc in seen:
                    continue
                seen.add(cell._tc)
                for par in cell.paragraphs:
                    n += do(par)
                # 넣은 뒤 다시 읽는다 — 1.4 뒤에 1.5 가 이어 붙는다
                while (k := ins(cell.paragraphs)):
                    n += k

    if write and n:
        d.save(str(p))
    return n


def unreachable() -> list[str]:
    """고친 뒤에도 찾는 쪽이 잡는 것 — **이 도구의 규칙이 못 닿는 자리다**(§333).

    ★ `tools/` 는 패키지가 아니라 `import` 로 못 부른다. `sys.path` 를 만지면
      `test_layering` 이 운다 — 파일로 적재한다(시험들이 쓰는 그 방법이다).
    ★ `exec_module` **앞에** `sys.modules` 에 넣는다. `@dataclass` 가
      `cls.__module__` 로 저를 되짚으므로 없으면 그 도구가 dataclass 를 갖는 날
      `AttributeError` 다 — 지금 안 터져도 지연 신관이고,
      `test_tools_are_wired::test_a_by_path_loader_registers_the_module` 가 든다.
    """
    import importlib.util
    q = ROOT / "tools" / "docx_check.py"
    spec = importlib.util.spec_from_file_location("docx_check_probe", q)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return [f"{p.name}  {line}"
            for p in sorted((ROOT / "docs").glob("*.docx"))
            for line in m.audit(p)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--touch", metavar="YYYY-MM-DD",
                    help="표지 최종 수정일 · 수치 기준일을 그날로 (기획서를 고친 배치가 찍는다)")
    a = ap.parse_args()
    extra = touch_rules(a.touch) if a.touch else None
    total = 0
    if a.touch:
        total += touch_md(a.touch, a.write)
    for p in sorted((ROOT / "docs").glob("*.docx")):
        c = fix(p, a.write, extra)
        total += c
        print(f"  {p.name}  run {c}개 {'수정' if a.write else '수정 예정'}")
    if not a.write:
        print("\n아무것도 안 썼다. 적용하려면 --write")
        print("★ docx 는 git diff 가 안 된다. 적용 후 워드로 눈으로 확인할 것.")
    else:
        print(f"\n{total}개 run 수정.")
        left = unreachable()
        if left:
            print("\n✗ 고친 뒤에도 `docx_check` 가 잡는 것이 남았다 — "
                  "**찾는 쪽이 고치는 쪽보다 넓다**(§333)")
            for x in left:
                print(f"   {x}")
            print("\n   규칙을 넓히거나, 그 자리를 손으로 고쳐라. "
                  "「대조해라」로 사람에게 넘기지 않는다.")
            return 1
        print("✓ `docx_check` 가 잡을 것이 없다 — 고정점에 닿았다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

