#!/usr/bin/env python3
"""
b5_plan2.py — **닫힌 항목을 PLAN 에서 지운다. 슬롯도 안 남긴다.**

    uv run python tools/batches/b5_plan2.py            무엇을 지울지만
    uv run python tools/batches/b5_plan2.py --apply    실제로

★ `b5_plan.py` 는 본문을 DECISIONS 로 옮기고 **슬롯을 남겼다.**
  §0-2 의 *"여기는 슬롯만 남는다"* 를 따른 것인데, **그 규약이 틀렸다.**

  PLAN 은 **빚 목록**이다. 앞으로 갚을 것을 적는다. 갚으면 목록에서
  사라져야 한다. 갚았다는 기록은 DECISIONS 가 들고 있는데 PLAN 에
  영수증을 또 붙여두면 그게 곧 중복이다 — 본문을 옮겨 없앤 그 중복의
  축소판일 뿐이다.

  ★ **개발이 끝나면 PLAN 은 비어야 한다.** 남은 일이 없다는 뜻이니까.
    슬롯이 쌓이면 영원히 안 빈다. 그러면 이 문서는 "앞으로 할 일" 이
    아니라 "했던 일 목록" 이 되고, 그건 DECISIONS 가 하는 일이다.
    목적을 벗어난 구현이다.

★ 내가 슬롯을 남기자고 든 근거 둘은 무너진다.

    번호 재사용   DECISIONS 가 제목까지 들고 있다. `## 123. 단계 스크립트
                  직접 호출 방지`. 인용은 그쪽을 찾으면 된다.
                  애초에 **없어질 문서의 번호를 영구 식별자로 쓴 것이 잘못**이다.
    참조 고아     DECISIONS 의 *"PLAN #15 에서 옮겼다"* 는 **과거 서술**이다.
                  DECISIONS 는 과거 문서이고, 그때 거기 있었다는 것은 사실이다.
                  지금 PLAN 에 없어도 그 문장은 참이다. 죽은 참조가 아니라 이력이다.
                  ★ 실측 — `PLAN #N` 을 검사하는 코드는 없다. 셋 다 주석이다.

★ **검사를 뒤집는다.** 어제 만든 `test_closed_plan_items_are_slots` 는
  틀린 규약을 정확히 강제한다. **잘못된 것을 정확히 지키게 만드는 검사가
  제일 위험하다** — 아무도 의심하지 않게 되기 때문이다.
  `test_plan_has_no_closed_items` 로 바꾼다. ⬛ 가 하나라도 있으면 운다.

★ MASTER 가 가리키는 `PLAN #N` 은 **지우기 전에 본다.** MASTER 는 현재
  시제라 열린 항목을 가리키면 그대로 두고, 닫힌 항목을 가리키면 그
  참조가 죽는다. 이 배치는 **찾아서 화면에 적기만 하고 안 고친다** —
  무엇으로 바꿀지는 사람이 정한다(원칙 ⑥·⑦).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

PLAN = ROOT / "docs/PLAN.md"
ROW = re.compile(r"^\| *(\d+) *\| *(.+?) *\| *⬛ *\| *(.*?) *\|\s*$", re.M)

OLD_RULE = "| ⬛ | 완료 · 기각. 결과는 MASTER 로 갔고 여기는 슬롯만 남는다 |\n"

NEW_RULE = """
★ **닫힘 표기는 없다.** 완료·기각한 항목은 결과를 `MASTER` 로, 왜 그렇게
됐는지를 `DECISIONS` 로 옮기고 **이 문서에서 행을 지운다.**

PLAN 은 빚 목록이다 — **갚은 빚은 목록에 안 남는다.** 슬롯을 남기면
영원히 안 비고, 그러면 이 문서는 "앞으로 할 일" 이 아니라 "했던 일 목록" 이
된다. 그것은 `DECISIONS` 가 하는 일이고, 한 항목이 두 문서에 사는 것이다.

★ **개발이 끝나면 이 문서는 비어야 한다.** 남은 일이 없다는 뜻이다.
남은 일이 없는데 문서가 두꺼우면 무언가 잘못된 것이다.

강제자 — `tests/test_doc_fsck.py::test_plan_has_no_closed_items`
"""

OLD_TEST = "def test_closed_plan_items_are_slots():"
NEW_TEST = "def test_plan_has_no_closed_items():"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    plan = PLAN.read_text(encoding="utf-8")
    rows = list(ROW.finditer(plan))
    if not rows:
        print("  = ⬛ 가 없다. 이미 적용됨")
        return 0

    keep = [m for m in rows if "DECISIONS §" not in m.group(3)
            and "MASTER §" not in m.group(3)]
    if keep:
        print("★ 옮겨지지 않은 ⬛ 가 있다. 먼저 b5_plan.py 를 돌려라.")
        for m in keep[:5]:
            print(f"    #{m.group(1)}  {m.group(2)[:50]}")
        return 1

    ids = {m.group(1) for m in rows}
    print(f"  ⬛ {len(rows)}행을 지운다 — #{min(ids, key=int)} … #{max(ids, key=int)}")

    # ── 지우기 전에 가리키는 곳을 본다 ────────────────────────
    print("\n  가리키는 곳 — **고치지 않는다. 사람이 정한다.**")
    for rel in ("docs/MASTER.md", "docs/DECISIONS.md"):
        t = (ROOT / rel).read_text(encoding="utf-8")
        hit = sorted({n for n in re.findall(r"PLAN #(\d+)", t)} & ids, key=int)
        tag = "★ 현재 시제다. 닫힌 항목을 가리키면 그 참조가 죽는다" \
            if rel.endswith("MASTER.md") else "과거 서술이라 그대로 둔다"
        print(f"    {rel:20s} {len(hit):3d}건  {tag}")
        if rel.endswith("MASTER.md") and hit:
            for n in hit:
                title = next(m.group(2) for m in rows if m.group(1) == n)
                print(f"        PLAN #{n} → {title[:46]}")

    if not a.apply:
        print("\n  ★ dry-run. --apply 를 붙일 것")
        return 0

    # ── ① 행 삭제 ────────────────────────────────────────────
    out, last = [], 0
    for m in rows:
        out.append(plan[last:m.start()])
        last = m.end() + 1 if plan[m.end():m.end() + 1] == "\n" else m.end()
    out.append(plan[last:])
    plan = "".join(out)

    # ── ② 규약 교체 ──────────────────────────────────────────
    if OLD_RULE in plan:
        plan = plan.replace(OLD_RULE, "")
        idx = plan.find("### 0-2. 상태 표기")
        end = plan.find("\n## ", idx)
        plan = plan[:end] + NEW_RULE + plan[end:]
    PLAN.write_text(plan, encoding="utf-8")

    # ── ③ 검사 뒤집기 ────────────────────────────────────────
    tp = ROOT / "tests/test_doc_fsck.py"
    t = tp.read_text(encoding="utf-8")
    if OLD_TEST in t:
        head, _, body = t.partition(OLD_TEST)
        body = body[body.index('"""', body.index('"""') + 3) + 3:]
        body = body[body.index("\n"):]
        t = head + NEW_TEST + '''
    """PLAN 에 닫힌 항목(⬛)이 **하나도 없어야 한다.**

    ★ 2026-09-13. 어제 만든 `test_closed_plan_items_are_slots` 를 뒤집었다.
      그 검사는 "슬롯이면 통과" 였고 §0-2 의 *"슬롯만 남는다"* 를 그대로
      강제했다. **그 규약이 틀렸다.** PLAN 은 빚 목록이고 갚은 빚은
      목록에 안 남는다. 개발이 끝나면 이 문서는 비어야 한다.

    ★ **잘못된 것을 정확히 지키게 만드는 검사가 제일 위험하다.**
      아무도 의심하지 않게 되기 때문이다. 검사가 있다는 사실 자체가
      규약을 검증한 것처럼 보이게 한다.

    닫는 법 — 결과는 MASTER 로, 이유는 DECISIONS 로 옮기고 **행을 지운다.**
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    plan = (root / "docs/PLAN.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\\| *(\\d+) *\\| *(.+?) *\\| *⬛ *\\|", plan, re.M)
    assert not rows, (
        f"PLAN 에 닫힌 항목이 {len(rows)}개 남아 있다. **행을 지워라.**\\n  "
        + "\\n  ".join(f"#{i} {t[:46]}" for i, t in rows)
        + "\\n\\n  PLAN 은 앞으로 할 일만 담는다(§0-2). 끝난 것은\\n"
          "  결과를 MASTER 로, 이유를 DECISIONS 로 옮기고 행을 지운다.\\n"
          "  옮기는 도구 — tools/batches/b5_plan.py\\n"
          "  ★ 갚은 빚은 목록에 안 남는다. 개발이 끝나면 이 문서는 빈다.")
''' + body
        tp.write_text(t, encoding="utf-8")

    print(f"\n  ✓ PLAN {len(rows)}행 삭제 · §0-2 규약 교체")
    print("  ✓ tests/test_doc_fsck.py 검사 뒤집음")
    print("\n다음 —")
    print("  uv run python tools/render_workflow.py   ★ MASTER 를 그린다")
    print("  uv run python -m pytest tests/ -q")
    print("  ★ 일부러 깨뜨린다 — PLAN 에 ⬛ 한 줄을 넣고 우는지 본다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
