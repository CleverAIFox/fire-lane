#!/usr/bin/env python3
"""
plan_renumber.py — `PLAN §1` 표 번호를 1..N 으로 당긴다. **참조도 따라간다.**

    uv run python tools/plan_renumber.py            검사 (기본)
    uv run python tools/plan_renumber.py --apply    실제로

★ 왜 `tools/` 인가 — 판별식은 *"내년에도 이걸 돌릴 일이 있나"* 다.
  **있다.** PLAN 항목이 닫히면 행을 지우고(§0-2), 지우면 결번이 생기고,
  결번은 `test_plan_row_numbers_are_contiguous_and_sorted` 가 잡는다.
  닫을 때마다 반복되는 일이므로 배치가 아니라 도구다.

★ 번호는 **영구 식별자가 아니라 현재 목록의 순번**이다.
  그래서 당겨도 된다. 영구 식별자는 `DECISIONS §N` 이 맡는다 —
  그쪽은 append-only 라 번호가 안 움직인다.
  종전 안내문은 *"뒤 번호를 당기지 말고 슬롯을 채운다"* 였는데,
  그것은 슬롯을 남기던 시절의 규약이다. 슬롯을 안 남기기로 했으므로
  당기는 것이 맞다(2026-09-13).

★ **대응표에 있는 것만 바꾼다.** 본문에는 `#N` 처럼 생겼지만 PLAN 항목이
  아닌 것이 섞여 있다 — `184번` · `289번` 은 도로 번호이고 `RDS1109` 도
  그렇다. 표의 번호 열로 만든 대응표에 없으면 **안 건드린다.**
  기계가 짐작해서 바꾸면 오탐이 나고, 오탐은 되돌리기가 더 비싸다.

★ 지워진 항목을 가리키던 참조는 **손대지 않고 화면에 적는다.**
  그것이 가리킬 곳은 `DECISIONS §N` 인데 어느 절인지는 이 도구가 모른다.
  모르는 것을 아는 척하지 않는다(HANDOFF 원칙 ⑥).

IN    docs/PLAN.md
OUT   docs/PLAN.md  (--apply 일 때만)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs/PLAN.md"

ROW = re.compile(r"^(\| )(\d+)( \|)", re.M)
# ★ 앞에 `§<숫자> ` 가 붙은 것은 **다른 문서·절의 항목**이다.
#   `§12 #18` 은 기획서 §12 의 18번이지 PLAN 항목이 아니다.
#   2026-09-13 에 그것을 PLAN 번호로 알고 바꿨다 — 표 범위는 §1 로
#   좁혀놓고 참조 치환만 문서 전체에 걸었던 탓이다. `§1 #N` 은 자기
#   표를 가리키므로 바꾸는 것이 맞고, 그 외 `§N #M` 은 남의 것이다.
#   ★ 첫 판이 `(?<!§\\d )` 였는데 그것은 `§1 #31` 까지 막았다.
#     `§1` 은 PLAN 자기 표라 바꿔야 하는 쪽이다. **예외의 예외**를
#     빠뜨리면 안 바꿔야 할 것과 바꿔야 할 것이 같이 얼어붙는다.
REF = re.compile(
    r"(?<!§2 )(?<!§3 )(?<!§4 )(?<!§5 )(?<!§6 )(?<!§7 )(?<!§8 )(?<!§9 )"
    r"(?<!§10 )(?<!§11 )(?<!§12 )(?<!§13 )(?<!§14 )(?<!§15 )(?<!§16 )"
    r"(?<!§17 )(?<!§18 )(?<!§19 )(?<!§20 )"
    r"(?<![0-9A-Za-z])#(\d+)(?![0-9])")
# ★ 2026-09-15. 위가 `#(\\d+)` 였다. r-문자열 안의 `\\d` 는 역슬래시+d 라
#   **숫자를 안 잡는다.** 그래서 이 도구는 만들어진 날부터 참조를 0건
#   찾았다. 결과가 둘이었다 —
#     ① 죽은 참조 안전장치(아래 `dead`)가 한 번도 안 돌았다.
#        2026-09-13 에 "경고는 읽히지 않는다. 멈추는 것만 읽힌다" 며
#        만든 그 방어가 만든 날부터 죽어 있었다.
#     ② 참조 치환(`REF.sub`)이 0건을 바꿨다. 이 도구 제목이
#        "**참조도 따라간다**" 인데 안 따라갔다. 행 번호만 당기고
#        참조는 옛 번호에 남는다 — 조용히 틀린다.
#   찾을 것이 없는 정규식은 0건을 내고, 0건은 초록이다.
#   그래서 아래 `_canary()` 가 생겼다.


def _canary() -> None:
    """정규식이 살아 있는가. **양성 대조다.**

    ★ 0건이 목표인 검사는 0건을 성공으로만 읽으면 안 된다. 그것이
      깨끗해서인지 프로브가 죽어서인지 구별할 수 없기 때문이다
      (DECISIONS §150 · §159). 합성 문자열로 확인한다.
    """
    probe = "보라 #63 과 `#45` 를. §12 #18 은 남의 것이다."
    got = REF.findall(probe)
    if got != ["63", "45"]:
        sys.exit("★ REF 정규식이 죽었다 — 합성 문자열에서 "
                 f"{got} 를 찾았다(기대 ['63', '45']).\n"
                 "  참조를 못 찾는 재배번은 행만 당기고 참조를 남긴다.\n"
                 "  **죽은 참조보다 나쁘다. 조용히 틀린다.**")
    if ROW.findall("| 7 | 제목 |") != [("| ", "7", " |")]:
        sys.exit("★ ROW 정규식이 죽었다 — 표 행을 못 찾는다.")


def _span(text: str) -> tuple[int, int]:
    """`## 1. 남은 일` 부터 다음 `### ` 앞까지.

    ★ 검사(`test_declaration_sync._plan_rows`)와 **같은 범위를 봐야 한다.**
      처음엔 문서 전체의 표 행을 긁었고 다른 절의 표까지 섞여
      `#1 → #9` 같은 엉뚱한 대응이 나왔다. 범위가 다르면 도구와
      검사가 다른 것을 세고, 그러면 고쳐도 계속 운다.
    """
    lines = text.splitlines(keepends=True)
    i = next(k for k, x in enumerate(lines) if x.startswith("## 1. 남은 일"))
    j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith("### "))
    return sum(len(x) for x in lines[:i]), sum(len(x) for x in lines[:j])


def _rows(text: str) -> list[int]:
    s, e = _span(text)
    return [int(m.group(2)) for m in ROW.finditer(text[s:e])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    _canary()
    text = PLAN.read_text(encoding="utf-8")
    nums = _rows(text)
    if not nums:
        sys.exit("★ PLAN 에서 표 행을 못 찾았다 — 프로브를 의심하라")

    gaps = sorted(set(range(1, max(nums) + 1)) - set(nums))
    if not gaps and nums == sorted(nums):
        print(f"✓ 없음 — 행 {len(nums)}개가 1..{max(nums)} 로 연속이다")
        return 0

    old2new = {o: i for i, o in enumerate(sorted(nums), 1)}
    moved = {o: n for o, n in old2new.items() if o != n}
    print(f"결번 {len(gaps)}개 · 재배번 {len(moved)}행  ({len(nums)}행 → 1..{len(nums)})")
    for o in sorted(moved)[:8]:
        print(f"    #{o} → #{old2new[o]}")
    if len(moved) > 8:
        print(f"    … {len(moved) - 8}행 더")

    # ── 지워진 것을 가리키는 참조 ────────────────────────────
    dead = sorted({int(m.group(1)) for m in REF.finditer(text)} - set(nums))
    if dead:
        print(f"\n★ 지워진 항목을 가리키는 참조 {len(dead)}건 — **안 고친다.**")
        print(f"    {', '.join('#' + str(d) for d in dead)}")
        print("    가리킬 곳은 `DECISIONS §N` 인데 어느 절인지 이 도구는 모른다.")
        print("    사람이 정한다. grep 'PLAN #<번호>' 로 자리를 찾아라.")
        print("\n★ 재배번을 하지 않는다. 먼저 위 참조를 고쳐라.")
        print("  ★ 2026-09-13. 종전에는 경고만 하고 진행했다. 그 결과")
        print("    `§1 #16`(지워진 norm 계층 이관)이 재배번 뒤 다른 항목을")
        print("    가리키게 됐다 — **죽은 참조보다 나쁘다. 조용히 틀린다.**")
        print("    경고는 읽히지 않는다. 멈추는 것만 읽힌다.")
        return 1

    if not a.apply:
        print("\n★ 검사만 했다. 고치려면 --apply")
        return 1

    # ── 치환. 두 단계로 한다 ─────────────────────────────────
    #   한 단계로 바꾸면 이미 바뀐 값을 또 바꾼다(4→1 뒤에 1→? 가 걸린다).
    #   중간 표식을 거쳐 충돌을 없앤다.
    def stage1_row(m: re.Match) -> str:
        return f"{m.group(1)}\x00{old2new[int(m.group(2))]}\x00{m.group(3)}"

    def stage1_ref(m: re.Match) -> str:
        o = int(m.group(1))
        return f"#\x00{old2new[o]}\x00" if o in old2new else m.group(0)

    s, e = _span(text)
    out = text[:s] + ROW.sub(stage1_row, text[s:e]) + text[e:]
    out = REF.sub(stage1_ref, out)          # 참조는 문서 전체에서 따라간다
    out = out.replace("\x00", "")

    after = _rows(out)
    if after != list(range(1, len(nums) + 1)):
        sys.exit(f"★ 결과가 1..N 이 아니다: {after[:10]}. 되돌린다.")

    PLAN.write_text(out, encoding="utf-8")
    print(f"\n✓ {len(nums)}행을 1..{len(nums)} 로 당겼다")
    print("다음 — uv run python tools/render_workflow.py; uv run python -m pytest tests/ -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
