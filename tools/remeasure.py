#!/usr/bin/env python3
"""
remeasure.py — 판정이 움직인 배치의 **재생성 사슬.** 순서가 이 도구의 내용물이다.

    uv run python tools/remeasure.py --tag ""          움직였는가만 본다 (안 고친다)
    uv run python tools/remeasure.py --tag v0.48       움직였으면 사슬을 돌리고 그 태그로 봉인
    uv run python tools/remeasure.py --selftest        ★ 순서가 선언과 같은가

── 왜 생겼나 (DECISIONS §319) ──────────────────────────────────
`tools/fl.sh` 의 4b 는 판정 **산출물**이 움직이면 멈춘다. 멈추는 것은 옳다 —
그것은 배선 배치가 아니라 측정 배치이고 §13-5 규칙 2 가 「사람이 판단한다」고
적었다. 그런데 **멈춘 다음에 할 일이 어디에도 없었다.**

2026-09-30 실기 — 사람이 손으로 여섯 도구를 돌렸고 순서가 하나 틀렸다
(`baseline freeze` 를 하고 **그 뒤에** `evalgen` 을 돌렸다). 봉인은 그 자리의
산출물을 지문으로 굳히는 일이라, 굳힌 뒤에 지표를 다시 내면 **봉인이 그 순간
거짓이 된다.** 전수 verify 가 여덟 단계 빨갰고 여덟이 다 같은 뿌리였다 —
문서 숫자 대조 · 기획서 대조 · 그림↔정본 · 기획서 그림 · 평가지표 산출.

★ 그래서 **판단과 받아적기를 가른다.** 판단은 하나다 — 「이 움직임을
  받아들이는가」이고, 그 답이 태그다(`--tag v0.48`). 나머지는 전부 순서이고
  순서는 기계가 지킨다. §309 가 래칫에서 한 것과 같은 가르기다.

★ 순서를 **셸 분기에 안 적는다.** 적으면 시험이 못 들고, 못 드는 순서는
  다음에 또 틀린다. 여기 `CHAIN` 이 정본이고 `--selftest` 가 그것을 문다.

IN    data/processed/{segments.geojson,seg_uid_map.csv} (git 과 대조)
OUT   판정 이동 한 쌍 · 그리고 사슬이 고치는 것들(지문 · 지표 · 문서 · 그림 · 봉인)
PARAM CHAIN (사슬과 그 순서) · WATCH (무엇이 움직이면 측정 배치인가)
밖    **판정을 안 내린다.** 움직임을 받아들일지는 사람이 태그로 답한다 —
      태그가 없으면 이 도구는 **아무것도 안 고치고** 멈춘다.
      **파이프라인을 안 돌린다.** 산출물을 만드는 것은 `fire-lane` 이고
      `fl.sh` 가 이 도구 **앞에서** 그것을 이미 돌렸다. 여기는 그 뒤를 잇는다.
      **커밋하지 않는다.** 앉히는 것은 `fl.sh` 4b 의 일이다 — 훅이 죽였는지를
      HEAD 로 재는 판별식이 거기 있고(§295-1), 그것을 두 집에 두지 않는다.
      **산문을 안 고친다.** 생성 블록 밖의 문장은 사람이 쓴 것이다(§319).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 이것이 움직이면 **측정 배치**다. 지문 파일이 아니라 파이프라인이 실제로
#: 쓰는 추적 산출물을 본다 — 지문은 `golden.py lock` 만 쓰므로 그것을 대 보면
#: 언제나 깨끗하다(`fl.sh` 4b 주석이 적은 빈 그물).
WATCH = ("data/processed/segments.geojson", "data/processed/seg_uid_map.csv")

#: 재생성 사슬. **순서가 내용물이다.** `{tag}` 는 사람이 준 태그.
#:
#:   지문 → 지표 → 문서 → 그림 → 봉인
#:
#: ★ 봉인이 **마지막**이다. 봉인은 그 자리의 산출물을 지문으로 굳히므로,
#:   굳힌 뒤에 무엇이든 다시 내면 봉인이 그 순간 거짓이 된다(09-30 실기).
#: ★ 래칫은 봉인 **앞**이다. 래칫 상수는 코드이고 코드는 지문에 든다.
CHAIN: tuple[tuple[str, list[str]], ...] = (
    ("판정 지문 재잠금", ["tools/golden.py", "lock"]),
    ("지표 재산출", ["tools/evalgen.py"]),
    ("문서 생성 블록", ["tools/docgen.py"]),
    ("기획서 그림", ["tools/docx_figs.py", "--sync"]),
    ("래칫 조임", ["tools/ratchet.py", "--write"]),
    ("봉인", ["tools/baseline.py", "freeze", "{tag}"]),
)

#: 사슬이 끝난 뒤 **무는 것.** 고치는 것이 아니라 판정한다.
AFTER: tuple[tuple[str, list[str]], ...] = (
    ("문서 숫자 대조", ["tools/docnum_check.py"]),
)


def _run(argv: list[str]) -> int:
    return subprocess.run([sys.executable, *argv], cwd=ROOT,  # noqa: S603 — 트리 안의 도구다
                          timeout=1800, check=False).returncode


def moved() -> list[str]:
    """`WATCH` 중 git 과 다른 것. 비면 배선 배치다."""
    r = subprocess.run(["git", "diff", "--name-only", "--", *WATCH],  # noqa: S603,S607
                       cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    return [x for x in r.stdout.split() if x]


def tally(ref: str | None) -> str:
    """판정 네 수 한 줄. `ref` 가 None 이면 작업 트리.

    ★ 세는 일은 `tools/verdict_tally.py` 하나가 한다 — 여기서 또 세면
      전후를 **다른 셈**으로 재게 되고, 그러면 이동표가 거짓일 수 있다.
    """
    seg = WATCH[0]
    tool = str(ROOT / "tools" / "verdict_tally.py")
    if ref is None:
        r = subprocess.run([sys.executable, tool, seg], cwd=ROOT,  # noqa: S603
                           capture_output=True, text=True, timeout=300, check=False)
        return r.stdout.strip() or "?"
    blob = subprocess.run(["git", "show", f"{ref}:{seg}"],  # noqa: S603,S607
                          cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=False)
    if blob.returncode != 0:
        return "?"
    r = subprocess.run([sys.executable, tool, "-"], cwd=ROOT,  # noqa: S603
                       input=blob.stdout, capture_output=True, text=True,
                       timeout=300, check=False)
    return r.stdout.strip() or "?"


def advise() -> None:
    """태그가 없을 때. **아무것도 안 고치고** 무엇을 할지만 적는다."""
    print("\n★ 판정 산출물이 움직였다 — 이 배치는 배선이 아니라 **측정**이다"
          "(PLAN §13-5 규칙 2).")
    for f in moved():
        print(f"    움직임  {f}")
    print(f"    전  {tally('HEAD')}")
    print(f"    후  {tally(None)}")
    print("\n  ★ 이 움직임을 **받아들이는가**가 사람의 판단이고, 그 답이 태그다.")
    print("    받아들이겠다면 `--measured=<태그>` 를 주고 다시 돌려라. 그러면")
    print("    아래 사슬을 **순서대로** 기계가 돌린다 —")
    for name, _ in CHAIN:
        print(f"      · {name}")
    print("\n  ★ 받아들일 수 없으면 여기서 멈추는 것이 맞다. 무엇이 왜 움직였는지부터")
    print("    본다:  uv run python tools/golden.py check --allow-stale")


def run(tag: str) -> int:
    got = moved()
    if not got:
        if tag:
            print(f"~ 판정 산출물이 안 움직였다 — `--measured={tag}` 는 필요 없었다."
                  " 사슬을 안 돌린다.")
        return 0
    if not tag:
        advise()
        return 1

    before = tally("HEAD")
    for name, argv in CHAIN:
        cmd = [a.replace("{tag}", tag) for a in argv]
        print(f"\n── {name}  ({' '.join(cmd)})")
        if _run(cmd) != 0:
            print(f"\n✗ 사슬이 「{name}」에서 멈췄다. **뒤를 안 돌린다** — 순서가"
                  " 이 도구의 내용물이고, 건너뛰면 봉인이 거짓이 된다.")
            return 1
    print(f"\n판정 이동 — PR 본문에 그대로 적어라\n    전  {before}\n    후  {tally(None)}\n")

    rc = 0
    for name, argv in AFTER:
        print(f"── {name}")
        if _run(argv) != 0:
            print(f"\n✗ 「{name}」이 빨갛다. 생성 블록 **밖의 산문**은 이 도구가 안"
                  " 고친다 — 위에 줄 번호가 있다. 사람이 고친 뒤 이어라.")
            rc = 1
    return rc


def selftest() -> int:
    """★ **순서가 선언과 같은가.** 09-30 에 틀린 것이 순서 하나였다."""
    fails = []
    names = [n for n, _ in CHAIN]
    tools = [a[0] for _n, a in CHAIN]
    if names[-1] != "봉인":
        fails.append("봉인이 사슬의 끝이 아니다 — 굳힌 뒤에 무엇을 내면 봉인이 거짓이 된다")
    if tools.index("tools/evalgen.py") > tools.index("tools/baseline.py"):
        fails.append("지표를 봉인 뒤에 낸다 — 09-30 에 실제로 그랬고 여덟 단계가 빨갰다")
    if tools.index("tools/golden.py") != 0:
        fails.append("지문 재잠금이 첫째가 아니다")
    if tools.index("tools/ratchet.py") > tools.index("tools/baseline.py"):
        fails.append("래칫 상수는 코드이고 코드는 지문에 든다 — 봉인 앞이어야 한다")
    if not all((ROOT / t).exists() for t in tools):
        fails.append(f"사슬이 없는 도구를 부른다 — {[t for t in tools if not (ROOT / t).exists()]}")
    if "{tag}" not in [a for _n, argv in CHAIN for a in argv]:
        fails.append("태그를 쓰는 자리가 없다 — 사람의 판단이 사슬에 안 들어간다")
    # ★ 반대 방향. 태그가 없으면 **아무것도 고치지 않는다.**
    src = Path(__file__).read_text(encoding="utf-8")
    if "advise()" not in src or "if not tag:" not in src:
        fails.append("태그 없는 갈래가 없다 — 판단 없이 사슬이 돈다")
    for f in fails:
        print(f"  ✗ {f}")
    print("✓ 자기검사 통과" if not fails else f"✗ {len(fails)}건")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    ap.add_argument("--tag", default="",
                    help="사람이 받아들인 봉인 태그. 비면 보기만 하고 멈춘다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    return selftest() if a.selftest else run(a.tag.strip())


if __name__ == "__main__":
    sys.exit(main())
