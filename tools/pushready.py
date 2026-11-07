#!/usr/bin/env python3
"""
pushready.py — 「푸시해도 되는가」 **한 명령.**  (PLAN #207)

    uv run python tools/pushready.py        rc 0 = 푸시 가능 · rc 1 = 막는 것이 있다(목록과 사람이 칠 명령)

★ **읽기만 한다.** 아무것도 안 쓰고 아무것도 안 찍는다 — 도장 · 래칫 · 변이 장부는 이 도구가 고치지 않는다.
  막는 것마다 **사람이 칠 명령**을 적는다.

── 왜 있나 ────────────────────────────────────────────────────
2026-11-08 한 배치에서 도장 상태를 **셋으로 따로** 물었다. 그때마다 「됐다」고 판단했고, 다음 관문에서 막혔다.
    `docseal check --invalid-list`   도장이 **낡았다**
    `UNSEALED`(래칫)                  도장이 **아예 없다**
    `test_fix_door`                  **커밋된 트리**의 도장 — `git worktree add HEAD` 로 복사해 돈다
`ratchet` 의 「낡음 0」 은 푸시 가능을 뜻하지 않는다. 도장만 찍고 커밋을 안 하면 래칫과 docseal 은 둘 다
초록이고 그 시험만 빨갛다 — **두 번** 물렸다. 또 `pre-push` 23게이트에는 `ratchet.py` 전수가 없어서
(suppress 55→56 · testsizetable 885→909) 로컬에서 아무도 안 물었고 CI 가 13분 뒤에 물었다.

── 무엇을 보나 ────────────────────────────────────────────────
  ㉠ `ratchet.py` 전수 — 낡음 · 조이는 쪽 · 느슨해진 쪽 · 못 재는 것. (UNSEALED · 변이 장부는 ㉢ · ㉤ 이 맡는다)
  ㉡ `docseal check --invalid-list` — 낡은 도장
  ㉢ `docseal` 의 `UNSEALED` — 도장 없는 절(선언 `docseal.UNSEALED` 보다 많으면 막는다)
  ㉣ `git status` — **커밋 안 된 추적 파일 변경.** `test_fix_door` 는 커밋된 트리를 쓴다.
  ㉤ `mutate` — 변이 장부가 낡았는가(`ratchet_values()` 가 죽는가)
순서는 사슬이다 — **래칫 → 변이 장부 → 문서 도장 → 커밋.** 목록은 그 순서로 낸다.

부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398 — 아직 어느 관문에도 안 올렸다: 2분이 예산 30초에 안 든다)
IN    `tools/ratchet.py` · `tools/docseal.py` · `tools/mutate.py` 의 출력과 종료 코드 · `git status --porcelain`
OUT   화면 · 종료 코드(가능 0 · 불가 1). 파일은 안 쓴다.
밖    **푸시할 ref 가 무엇인지는 안 본다**(그것은 `.githooks/pre-push` 의 몫) · **원격 상태를 안 본다**(네트워크 없음) ·
      **CI 가 도는 시험 전체를 안 돈다** — 전수 `pytest` 는 25분이고 이 도구는 그 대신이 아니다. 이 도구가 「가능」이라고
      한 것은 **도장 · 래칫 · 변이 장부 · 커밋** 네 축이 푸시를 막지 않는다는 뜻이다.
      ★ **느리다** — `ratchet.py` 전수가 2분이다. 그래서 `pre-push` 30초 예산에 못 올렸다(PLAN #207).
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: `(argv, cwd) → (rc, 출력)`. 시험이 합성 출력을 먹이려고 갈아 끼운다.
Runner = Callable[[list[str], Path], tuple[int, str]]

_PY = ["uv", "run", "python"]
#: 도장 상태가 담긴 파일 — 이것만 고쳐진 채 커밋이 안 됐으면 `test_fix_door` 가 빨갛다.
SEAL_FILE = "data/golden/docseal.json"


@dataclass
class Block:
    """막는 것 하나. `cmds` 는 **사람이 칠** 명령이다."""

    key: str                    # ㉠~㉤
    what: str
    detail: list[str] = field(default_factory=list)
    cmds: list[str] = field(default_factory=list)


def real_run(argv: list[str], cwd: Path) -> tuple[int, str]:
    # ★ 시한을 둔다 — 시한 없는 기다림은 빨강을 무한 대기로 바꾼다(`test_no_unbounded_waits`). 래칫 전수가 2분이라 넉넉히 잡는다.
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ── ㉠ 래칫 ─────────────────────────────────────────────────────
_ITEM = re.compile(r"^\s+([✗·~]) (\S+) · (\S+)")
_SUMMARY = re.compile(r"래칫 (\d+)개 · 낡음 (\d+)")


def check_ratchet(root: Path, run: Runner) -> Block | None:
    """`ratchet.py` 전수. UNSEALED(㉢) 와 변이 장부(㉤) 항목은 그쪽이 맡으므로 여기서 세지 않는다.

    ★ **닫힌 쪽으로 실패한다** — rc 가 0 이 아닌데 읽을 항목이 하나도 없으면 「원인 불명」으로 막는다.
    """
    rc, out = run([*_PY, "tools/ratchet.py"], root)
    if rc == 0:
        return None
    loose, tight = [], []
    for ln in out.splitlines():
        m = _ITEM.match(ln)
        if not m:
            continue
        mark, tool, name = m.groups()
        if (tool == "docseal.py" and name == "UNSEALED") or tool == "mutate.py":
            continue
        if mark == "·":
            tight.append(ln.strip())
        elif mark == "✗":
            loose.append(ln.strip())
    s = _SUMMARY.search(out)
    if not (loose or tight):
        if s is None and "래칫" not in out:
            return Block("㉠", "래칫 — 읽을 수 없는 출력으로 실패했다(원인 불명)",
                         out.strip().splitlines()[-5:],
                         [" ".join([*_PY, "tools/ratchet.py"]) + "   # 전문을 읽는다"])
        return None         # UNSEALED · 변이 장부만 울었다 — ㉢ · ㉤ 이 맡는다
    b = Block("㉠", f"래칫이 실측과 다르다 — 느슨해진 쪽·못 재는 것 {len(loose)} · 조이는 쪽 {len(tight)}")
    b.detail = [*loose, *tight]
    if tight:
        b.cmds.append(" ".join([*_PY, "tools/ratchet.py", "--write"]) + "   # 조이는 쪽만 쓴다")
    if loose:
        b.cmds.append("# 느슨해진 쪽은 `--write` 가 안 받는다 — 그 도구가 왜 우는지 읽고 손으로 고친다(결함이다)")
    return b


# ── ㉡ 낡은 도장 ─────────────────────────────────────────────────
def check_invalid_seals(root: Path, run: Runner) -> Block | None:
    rc, out = run([*_PY, "tools/docseal.py", "check", "--invalid-list"], root)
    if rc != 0:
        return Block("㉡", "도장 검사가 죽었다(rc≠0)", out.strip().splitlines()[-5:],
                     [" ".join([*_PY, "tools/docseal.py", "check"])])
    names = [x.strip() for x in out.splitlines() if x.strip() and "/" in x]
    if not names:
        return None
    return Block("㉡", f"도장이 낡았다 — {len(names)}절", names[:12] + ([f"… 그리고 {len(names) - 12}절 더"] if len(names) > 12 else []),
                 ["# 절과 코드를 같이 읽은 뒤(사람이 찍는다) —",
                  "mapfile -t S < <(uv run python tools/docseal.py check --invalid-list)",
                  'A=(); for s in "${S[@]}"; do A+=(--only "$s"); done',
                  'uv run python tools/docseal.py stamp "${A[@]}"'])


# ── ㉢ 도장 없는 절 ──────────────────────────────────────────────
# ★ 자리를 **`cwd`(= tools/)로** 준다 — `python -c` 는 cwd 를 먼저 본다. `sys.path` 를 코드 문자열에 적으면
#   `test_layering::test_sys_path_해킹이_없다` 가 그 글자를 센다(`mutate_guard` 가 같은 길을 쓴다).
_UNSEALED_PROBE = (
    "import docseal as d; "
    "now, was, _ = d.survey(); "
    "print('DECLARED', d.UNSEALED); "
    "[print('UNSEALED', k) for k in sorted(now) if k not in was]"
)


def check_unsealed(root: Path, run: Runner) -> Block | None:
    rc, out = run([*_PY, "-c", _UNSEALED_PROBE], root / "tools")
    declared = next((int(x.split()[1]) for x in out.splitlines() if x.startswith("DECLARED ")), None)
    if rc != 0 or declared is None:
        return Block("㉢", "도장 없는 절을 못 셌다(탐침이 죽었다)", out.strip().splitlines()[-5:],
                     [" ".join([*_PY, "tools/docseal.py", "status"])])
    names = [x.split(" ", 1)[1] for x in out.splitlines() if x.startswith("UNSEALED ")]
    if len(names) <= declared:
        return None
    return Block("㉢", f"도장이 아예 없는 절 {len(names)}개 — 선언 {declared} 보다 많다(`UNSEALED` 는 늘 수 없다)",
                 names[:12] + ([f"… 그리고 {len(names) - 12}절 더"] if len(names) > 12 else []),
                 ["# 새 절을 읽은 뒤(사람이 찍는다) —",
                  "uv run python tools/docseal.py stamp " + " ".join(f"--only {n}" for n in names[:3])
                  + (f"   # … {len(names) - 3}절 더" if len(names) > 3 else "")])


# ── ㉣ 커밋 안 된 변경 ───────────────────────────────────────────
def check_dirty(root: Path, run: Runner) -> Block | None:
    """★★ 2026-11-08 에 두 번 물린 자리. `test_fix_door` 는 `git worktree add HEAD` 로 **커밋된 트리**를 복사해 돈다.

    도장을 찍고 커밋을 안 하면 그 시험이 빨갛고 래칫 · docseal 은 둘 다 초록이다.
    추적 안 된 새 파일(`??`)은 막지 않고 **적기만 한다** — 그 파일에 기대는 시험이 있으면 CI 가 본다.
    """
    rc, out = run(["git", "status", "--porcelain=v1"], root)
    if rc != 0:
        return Block("㉣", "git status 가 죽었다", out.strip().splitlines()[-3:], ["git status"])
    tracked = [ln for ln in out.splitlines() if ln and not ln.startswith("??")]
    if not tracked:
        return None
    files = [ln[3:] for ln in tracked]
    detail = [ln for ln in tracked[:15]] + ([f"… 그리고 {len(tracked) - 15}개 더"] if len(tracked) > 15 else [])
    if SEAL_FILE in files:
        detail.insert(0, f"★ {SEAL_FILE} 가 커밋 안 됐다 — 도장만 찍고 커밋을 안 한 꼴이다. "
                         "`test_fix_door` 는 커밋된 트리를 복사해 돌므로 래칫 · docseal 이 초록이어도 빨갛다")
    return Block("㉣", f"커밋 안 된 추적 파일 변경 {len(tracked)}개", detail,
                 ["git add <고친 파일들>   # 도장 파일(data/golden/docseal.json)을 빼먹지 않는다",
                  "git commit"])


# ── ㉤ 변이 장부 ─────────────────────────────────────────────────
_MUTATE_PROBE = "import mutate; mutate.ratchet_values()"


def check_mutate(root: Path, run: Runner) -> Block | None:
    rc, out = run([*_PY, "-c", _MUTATE_PROBE], root / "tools")
    if rc == 0:
        return None
    last = [x for x in out.strip().splitlines() if x.strip()][-2:]
    return Block("㉤", "변이 장부가 낡았다(또는 못 읽는다)", last,
                 [" ".join([*_PY, "tools/mutate.py", "--write", "--stale"]) + "   # 느리다 · 고친 도구의 과녁만 다시 잰다"])


#: 사슬 순서 — 래칫 → 변이 장부 → 문서 도장 → 커밋. **싼 것을 앞에 두지 않는다**(사람이 칠 순서가 목록 순서다).
CHECKS: list[tuple[str, Callable[[Path, Runner], Block | None]]] = [
    ("㉠", check_ratchet), ("㉤", check_mutate), ("㉡", check_invalid_seals),
    ("㉢", check_unsealed), ("㉣", check_dirty),
]


def survey(root: Path = ROOT, run: Runner = real_run, *, log: Callable[[str], None] | None = None) -> list[Block]:
    out: list[Block] = []
    for key, fn in CHECKS:
        t = time.monotonic()
        b = fn(root, run)
        if log:
            log(f"  {key} {'✗' if b else '✓'}  {time.monotonic() - t:5.1f}초")
        if b:
            out.append(b)
    return out


def render(blocks: list[Block]) -> str:
    if not blocks:
        return ("✓ 푸시 가능 — 래칫 · 변이 장부 · 도장(낡음 · 없음) · 커밋 네 축이 막지 않는다.\n"
                "  (전수 pytest 는 안 돌았다 — 이 도구는 그 대신이 아니다.)")
    L = [f"✗ 푸시 불가 — 막는 것 {len(blocks)}가지 (사슬 순서: 래칫 → 변이 장부 → 문서 도장 → 커밋)\n"]
    for b in blocks:
        L.append(f"  {b.key} {b.what}")
        L += [f"      {d}" for d in b.detail]
        L.append("    사람이 칠 명령:")
        L += [f"      {c}" for c in b.cmds]
        L.append("")
    L.append("  ★ 이 도구는 읽기만 한다. 도장은 사람이 읽고 찍는다. 찍은 뒤에는 **커밋까지** 한다 — 그리고 다시 이 명령을 돌린다.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv:
        print(__doc__)
        return 2
    blocks = survey(log=lambda s: print(s, file=sys.stderr))
    print(render(blocks))
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
