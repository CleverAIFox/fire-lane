#!/usr/bin/env python3
"""
plan_renumber.py — `PLAN §1` 행 번호의 **정합 검사기.** 더는 당기지 않는다.

    uv run python tools/plan_renumber.py       검사 (유일 · 오름차순 · 외부 인용)

★ **2026-09-20 — 재배번 기능을 지웠다**(DECISIONS §205). 옛 머리말은
  「PLAN §1 표 번호를 1..N 으로 당긴다. **참조도 따라간다.**」였다.
  실측하면 **참조를 안 따라간다** — 이 파일이 여는 것은 `docs/PLAN.md` 하나뿐이고,
  §1 행을 가리키는 인용은 밖에 **83곳** 있다:

      docs/DECISIONS.md   70곳      ← append-only 역사다. 고칠 수 없다
      docs/MASTER.md       7곳
      sources.yaml         6곳

  즉 `--apply` 를 한 번 돌리면 그 83곳이 **조용히 다른 행을 가리킨다.**
  아래쪽 주석이 그 사고를 이미 적고 있었다 — 「`§1 #16`(지워진 norm 계층
  이관)이 재배번 뒤 다른 항목을 가리키게 됐다 — **죽은 참조보다 나쁘다.
  조용히 틀린다.**」 그 방어가 **PLAN 안의 참조만** 봤기 때문에 밖의 83곳에는
  안 걸렸다. 범위가 이름보다 좁고 그것이 선언돼 있지 않았다.

★ **그래서 규약을 뒤집었다: 결번을 허용한다.** 행 번호가 **영구 식별자**가 된다.
  닫힌 행을 지우면 그 번호는 비고 **다시 쓰지 않는다.** 그러면 83곳이 영원히
  유효하고, 무엇보다 **§1 이 줄어들 수 있다** — 지금까지 닫힌 행이 목록에
  그대로 앉아 있던 이유가 「지우면 뒤가 당겨진다」였다.
  종전 규약(2026-09-13 「슬롯을 안 남기기로 했으므로 당기는 것이 맞다」)은
  **인용이 PLAN 안에만 있다는 전제**에서 나왔고 그 전제가 틀렸다.

★ 지워진 번호를 가리키는 인용은 **고치지 않는다.** 그것은 역사이고,
  가리키던 행이 무엇이었는지는 `DECISIONS §N` 이 안다. 이 도구는 세기만 한다 —
  모르는 것을 아는 척하지 않는다(HANDOFF 원칙 ⑥).

IN    docs/PLAN.md · docs/DECISIONS.md · docs/MASTER.md · sources.yaml
OUT   없다 (검사 전용)
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


def _foreign(text: str) -> list[tuple[int, int]]:
    """자기 번호 표(`| # |`)를 가진 §1 밖 절의 범위.

    ★ 2026-09-17 (DECISIONS §180 · G-13). §12 산문의 `(#6 · #11 · #12)` 는 §12 표의 번호였다. 이 도구가
      그것을 §1 행 참조로 읽어 재배번을 멈췄고, 멈추지 않았다면 두 참조가 조용히 다른 행을 가리켰다.
      그런 절 안에서는 **`§1 #N` 으로 소속을 적은 것만** §1 참조로 본다.
    """
    heads = [(m.start(), m.group(1)) for m in re.finditer(r"^## (\d+)\. ", text, re.M)]
    out = []
    for k, (pos, num) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(text)
        if num != "1" and re.search(r"^\| # \|", text[pos:end], re.M):
            out.append((pos, end))
    return out


def _is_plan_ref(text: str, m: re.Match, spans: list[tuple[int, int]]) -> bool:
    if not any(a <= m.start() < b for a, b in spans):
        return True
    return text[max(0, m.start() - 3):m.start()] == "§1 "


# ★ `### 8-7. 저장소 위생 → §1 #100 · #103` 꼴의 **산 길잡이.**
#   `→ §1 ` 뒤에 붙은 `#N · #M` 런만 잡는다. 제목 안의 다른 `#N` 은 남의
#   것일 수 있으므로 런 밖은 안 본다(`§1 #3 (… MASTER §19-5)` 처럼 뒤에
#   다른 문서가 따라붙는 꼴이 실제로 있다).
GUIDE = re.compile(r"→ §1 ((?:#\d+(?: · )?)+)")


def _guides(text: str) -> list[tuple[int, str, list[int]]]:
    """`### ` 제목이 **지금 보라고 가리키는** §1 행 번호. (줄번호 · 원문 · 번호들)

    ★ 두 꼴을 **가른다.** 둘 다 PLAN 안에서 `#N` 을 쓰지만 성질이 반대다 —

        `→ **§1 로 접었다**(#96 … #103)`   묘비다. 그 절이 **무엇이 됐는지**의
                                           영구 기록이고, 행이 닫혀 지워져도
                                           기록은 그대로 맞다
        `### 8-7. … → §1 #100 · #103`      **길잡이**다. 「지금 이것을 보라」고
                                           말한다. 가리키는 행이 없으면 읽는
                                           사람이 빈손으로 돌아온다

      그래서 이 함수는 `### ` 로 시작하는 줄만 본다. 묘비는 밖이다.
    """
    out: list[tuple[int, str, list[int]]] = []
    for i, ln in enumerate(text.splitlines(), 1):
        if not ln.startswith("### "):
            continue
        m = GUIDE.search(ln)
        if m:
            out.append((i, ln.strip(), [int(x) for x in re.findall(r"#(\d+)", m.group(1))]))
    return out


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
    doc = "## 1. 남은 일\n\n| # | 항목 |\n| 6 | a |\n\n## 12. 기획서\n\n| # | 서술 |\n| 6 | b |\n본문 #6 · §1 #6\n"
    sp = _foreign(doc)
    got = [m.group(1) for m in REF.finditer(doc) if _is_plan_ref(doc, m, sp)]
    if got != ["6"]:
        sys.exit(f"★ 남의 표 번호를 가리는 프로브가 죽었다 — {got}(기대 ['6'] · `§1 #6` 하나).")

    # ── 길잡이 프로브. **묘비와 길잡이를 가르는가** ──────────────
    g = (
        "## 8. 데이터\n\n"
        "→ **§1 로 접었다**(#96 · #103).\n\n"
        "### 8-7. 저장소 위생 → §1 #100 · #103\n"
        "### 8-9. 딴 것 → §1 #4 (정본은 MASTER §19-5)\n"
    )
    got2 = [(ln, ns) for ln, _raw, ns in _guides(g)]
    if got2 != [(5, [100, 103]), (6, [4])]:
        sys.exit("★ 길잡이 프로브가 죽었다 — 합성 문자열에서 "
                 f"{got2} 를 찾았다(기대 [(5, [100, 103]), (6, [4])]).\n"
                 "  묘비(`§1 로 접었다`)를 같이 집으면 역사를 고치라고 운다.\n"
                 "  길잡이를 못 집으면 **닫은 행을 가리키는 제목이 영원히 산다.**")


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
    # ★ `--apply` 를 받되 **거부한다.** 조용히 빼면 손에 익은 사람이 옛 명령을
    #   치고 아무 일도 안 일어난 것으로 읽는다. 왜 없어졌는지를 화면이 말해야 한다.
    ap.add_argument("--apply", action="store_true", help="(폐지됨 — 사유를 출력한다)")
    a = ap.parse_args()

    _canary()
    text = PLAN.read_text(encoding="utf-8")
    nums = _rows(text)
    if not nums:
        sys.exit("★ PLAN 에서 표 행을 못 찾았다 — 프로브를 의심하라")

    if a.apply:
        print("★ `--apply` 는 폐지됐다(2026-09-20 · DECISIONS §205).")
        print("  §1 행을 가리키는 인용이 이 문서 **밖에 83곳** 있고, 이 도구는")
        print("  `docs/PLAN.md` 하나만 연다. 당기면 그 83곳이 조용히 다른 행을 가리킨다.")
        print("  그중 70곳은 `docs/DECISIONS.md` 이고 그것은 append-only 역사다.")
        print("")
        print("  이제 **결번이 정상이다.** 닫힌 행은 그냥 지워라 — 번호는 안 당긴다.")
        return 1

    bad = []
    dup = sorted({n for n in nums if nums.count(n) > 1})
    if dup:
        bad.append(f"중복 번호 {dup} — 같은 번호가 두 행이면 인용이 어느 쪽인지 모른다")
    if nums != sorted(nums):
        bad.append("번호가 오름차순이 아니다 — 표를 눈으로 훑을 수 없다")
    if bad:
        print("★ PLAN §1 번호가 어긋났다\n")
        for b in bad:
            print(f"  ✗ {b}")
        return 1

    # ★ 2026-09-27 (DECISIONS §271). 종전에는 `max(nums)` 까지만 셌다. 그러면 **꼬리
    #   번호를 닫은 날 그 번호를 결번으로 못 적는다** — 구멍이 아니라 끝이 되기
    #   때문이다. 그런데 다음 행은 `맨 끝 + 1` 을 쓰므로 그 번호를 **조용히
    #   재사용한다.** 결번 대장이 막으려던 바로 그것이다(#139 를 닫으며 드러났다).
    #   수위(high-water)는 **선언된 결번까지 포함한 최댓값**이다. 한 번 쓴 번호는
    #   행이 사라져도 수위를 내리지 않는다.
    _said0 = [int(x) for x in re.findall(r"#(\d+)", (
        re.search(r"^결번 — (.+)$", text, re.M) or type("", (), {"group": lambda *_: ""})()
    ).group(1))]
    _hi = max([*nums, *_said0])
    gaps = sorted(set(range(1, _hi + 1)) - set(nums))

    # ── 결번 대장 — **번호 재사용을 막는다** (2026-09-23 · DECISIONS §222-4) ──
    # ★ §205 가 「결번을 허용한다」로 규약을 뒤집었지만, **재사용을 막는 것은 없었다.**
    #   결번이 난 자리에 새 행이 들어오면 이 도구는 아무 말도 안 한다 — 중복도 아니고
    #   오름차순도 깨지지 않기 때문이다. 그런데 밖의 인용 83곳은 그 순간 **다른 행**을
    #   가리키게 된다. 그래서 비운 번호를 PLAN §1 머리에 **선언**하고 여기서 대조한다.
    #   재사용하면 선언된 결번 하나가 실물에서 사라지므로 운다.
    m = re.search(r"^결번 — (.+)$", text, re.M)
    if not m:
        print("★ PLAN §1 머리에 `결번 — …` 줄이 없다 — 번호 재사용을 막을 근거가 사라진다")
        return 1
    said = sorted(int(x) for x in re.findall(r"#(\d+)", m.group(1)))
    if said != gaps:
        back = sorted(set(said) - set(gaps))
        lost = sorted(set(gaps) - set(said))
        print("★ 결번 대장이 실물과 다르다\n")
        if back:
            shown = ", ".join(f"#{n}" for n in back)
            print(f"  ✗ **재사용됐다**: {shown}")
            print("    그 번호를 가리키는 밖의 인용이 조용히 다른 행을 가리킨다.")
            print("    새 행은 **맨 끝 번호 + 1** 을 쓴다. 비운 자리를 채우지 않는다.")
        if lost:
            shown = ", ".join(f"#{n}" for n in lost)
            print(f"  ✗ 선언에 없는 결번: {shown} — 머리 줄에 더해라")
        return 1

    # ── PLAN **안**의 산 길잡이 — 여기는 빨강이다 ──────────────
    # ★ 밖의 죽은 인용(아래)과 **성질이 다르다.** 밖은 역사라 고치면 역사를
    #   고치게 되지만, `### 8-7. … → §1 #103` 은 역사가 아니라 **지금 보라는
    #   안내**다. #103 이 닫혀 지워졌으면 그 제목은 읽는 사람을 빈 자리로
    #   보낸다. 그리고 PLAN 은 append-only 가 아니다 — 고칠 수 있고, 줄어야
    #   한다. 2026-10-03 실측: §8-7 하나가 그 꼴이었고 #103 은 2026-09-28 에
    #   닫혔다(DECISIONS §278-9 가 닫은 넷 중 하나). 닫은 날 제목을 안 고쳤고
    #   어떤 검사도 안 울었다 — **밖만 보는 검사가 안을 사각지대로 남겼다.**
    live = set(nums)
    lame = [(ln, raw, [n for n in ns if n not in live]) for ln, raw, ns in _guides(text)]
    lame = [x for x in lame if x[2]]
    if lame:
        print("★ PLAN 안의 길잡이가 **없는 행**을 가리킨다\n")
        for ln, raw, dead in lame:
            shown = ", ".join(f"#{n}" for n in dead)
            print(f"  ✗ PLAN:{ln}  {shown} — §1 에 없다")
            print(f"      {raw[:96]}")
        print("")
        print("  그 번호가 닫혀 지워졌으면 **제목에서 뺀다.** 번호가 다 빠지면")
        print("  그 하위 절은 들 것이 없으므로 절째로 지운다 — 무엇이었는지는")
        print("  그 절의 `→ **§1 로 접었다**(…)` 묘비가 영구히 든다.")
        print("  ★ 번호를 **다른 산 행으로 갈아 끼우지 마라.** 가리키던 것이")
        print("    무엇이었는지부터 `DECISIONS` 에서 찾아라(W3-9 와 같은 병).")
        return 1

    # ── 밖에서 §1 을 가리키는 인용 ───────────────────────────
    # ★ 죽은 인용은 **빨간불이 아니다.** 가리키던 행이 닫혀서 지워진 것이고
    #   그것이 정상 경로다. 세어서 말하기만 한다 — 고치라고 하면 역사를 고치게 된다.
    outside: dict[str, list[int]] = {}
    for rel in ("docs/DECISIONS.md", "docs/MASTER.md", "sources.yaml"):
        q = ROOT / rel
        if not q.is_file():
            continue
        cites = [int(n) for n in re.findall(r"PLAN[^\n]{0,14}?#(\d+)\b",
                                            q.read_text(encoding="utf-8"))]
        outside[rel] = sorted({n for n in cites if n not in live})

    print(f"✓ 행 {len(nums)}개 · 번호 {min(nums)}..{max(nums)} · 중복 0 · 오름차순")
    if gaps:
        head = ", ".join("#" + str(g) for g in gaps[:12])
        more = f" … {len(gaps) - 12}개 더" if len(gaps) > 12 else ""
        print(f"  결번 {len(gaps)}개 — {head}{more}")
        print("    ★ 결번은 정상이다. 번호는 영구 식별자이고 다시 쓰지 않는다.")
    tot = sum(len(v) for v in outside.values())
    if tot:
        print(f"  밖에서 지워진 행을 가리키는 인용 {tot}곳 — **안 고친다**(역사다)")
        for rel, ns in outside.items():
            if ns:
                print(f"    {rel:20} {', '.join('#' + str(n) for n in ns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
