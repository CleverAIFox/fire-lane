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
  ㉥ `testpick --run` — 실측으로 고른 시험 묶음(구조 규약 시험 포함 · PLAN #209)
  ㉦ `obligations --new` — 새 파일의 빠진 등재 의무를 이름으로(PLAN #199 · 훅이 아니라 여기 — 훅은 예산이 없다)
  ㉨ **훅 게이트 전부**(시험 묶음 · 도장은 ㉥ · ㉡ 가 더 세게) + `gatefast` 의 `ready` 층(CI **다섯 잡**의 검사 중 훅 예산에 못 든 것 · (열쇠, 인자) 단위) — **글자 그대로** 돈다(PLAN #216 · 병렬 4 · 둘 다 도출이라 사본이 없다 → pushready ≥ 훅)
  ㉧ 로컬이 **로컬에 있는 원격 추적 가지**(`@{u}`)보다 뒤인가 — 뒤면 받을 명령을 댄다(PLAN #211). `fetch` 는 **안 한다**(사람이 정했다: 읽기 전용이 정체성이다)
★ **몇 바퀴 남았나**(PLAN #220): 막는 것 목록 끝에 `forecast` 가 「이번에 치면 다음에 무엇이 또 낡는가」를 말한다 — 되먹임 변 다섯(`EDGES` · 실측 · 서술을 달았다)만으로 **확정 바퀴 · 가능한 바퀴**를 센다.
  모델이다: 고정점을 증명하지 않고, 가능한 자기 루프 때문에 상한(`LAP_CAP`)에서 자른다. 표본은 사람이 돈 다섯 바퀴 한 건이다. 이 도구는 여전히 **아무것도 안 친다**.
순서는 사슬이다 — **받기 → 시험 → 등재 의무 → CI 미러 → 도장 없는 절(㉢) → 래칫(㉠) → 변이 장부(㉤) → 낡은 도장(㉡) → 커밋.** (2026-11-14 · PLAN #220: 사람이 이 순서로 쳐서 확정 바퀴가 2 → 1 로 줄었다 — `㉢` 이 `UNSEALED` 를 조이므로 래칫 **앞**이다) 목록은 그 순서로 낸다(받으면 트리가 바뀌어 뒤의 것이 다 낡으므로 ㉧ 이 맨 앞이다).

부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398 — 아직 어느 관문에도 안 올렸다: 2분이 예산 30초에 안 든다)
IN    `tools/ratchet.py` · `tools/docseal.py` · `tools/mutate.py` 의 출력과 종료 코드 · `git status --porcelain`
OUT   화면 · 종료 코드(가능 0 · 불가 1). 파일은 안 쓴다.
밖    **푸시할 ref 가 무엇인지는 안 본다**(그것은 `.githooks/pre-push` 의 몫) · **원격 상태를 안 본다**(네트워크 없음 — ㉧ 은 마지막 `git fetch` 가 받아 둔 로컬 ref 만 비교한다) ·
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


# ── ㉥ 구조 규약 시험 묶음 ───────────────────────────────────────
def check_tests(root: Path, run: Runner) -> Block | None:
    """`testpick --run` — 실측 장부에서 **계산한** 시험 묶음(PLAN #209). 손 목록이 아니다.

    ★ **바뀐 파일에 닿는 시험을 상한 없이 전부 더한다**(`--no-cap` · PLAN #218 b). 훅은 30초를 지켜 이 연동을 끈다 — 느린 검사는 앞(여기)에, 빠른 그물은 뒤(훅)에 둔다(#216).
    ★ 훅(`--load 60`)보다 큰 묶음이다 — 여기는 남의 일이 없어 `test_layering` 같은 구조 규약 시험이 든다(2026-11-08 에 CI 만 물었다).
    """
    rc, out = run([*_PY, "tools/testpick.py", "--run", "--no-cap"], root)
    if rc == 0:
        return None
    tail = [x for x in out.strip().splitlines() if x.strip()]
    return Block("㉥", "시험 묶음이 빨갛다(또는 장부가 없다)", tail[-8:],
                 [" ".join([*_PY, "tools/testpick.py", "--run", "--no-cap"]) + "   # 빨간 파일을 읽고 고친다 — 고친 뒤 래칫 · 도장을 다시 사슬로"])


# ── ㉦ 새 파일의 등재 의무 ───────────────────────────────────────
def check_obligations(root: Path, run: Runner) -> Block | None:
    """`obligations --new` — 새 파일에 따라붙는 의무(MASTER §22·§23 등재 · 「부류」 · 「밖」) 중 **무엇이** 빠졌는지 이름으로 댄다. (PLAN #199)

    ★ 훅이 아니라 **여기**다 — 등재 누락은 푸시 전에 알아야 하지만 훅은 예산 30초에 겨우 든다(2026-11-08 사람이 정했다).
      새 파일이 없으면 0.1초대로 끝나고, 있으면 약 5초다(세 검사의 판정을 부른다).
    """
    rc, out = run([*_PY, "tools/obligations.py", "--new"], root)
    if rc == 0:
        return None
    tail = [x.rstrip() for x in out.strip().splitlines() if x.strip()]
    return Block("㉦", "새 파일의 등재 의무가 빠졌다", tail[:14] + ([f"… 그리고 {len(tail) - 14}줄 더"] if len(tail) > 14 else []),
                 [" ".join([*_PY, "tools/obligations.py", "--new"]) + "   # 빠진 의무를 이름으로 댄다 — 적은 뒤 다시"])


# ── ㉨ 훅 게이트 전부 + CI 빠른 잡 중 훅에 못 든 것 ───────────────
MIRROR_WORKERS = 4
#: CI 빠른 잡은 **레이크 없이** 돈다 — 이 기계의 `FIRE_LANE_DATA` 가 결과를 바꾸지 않게 같은 조건으로 돈다(`env` 로 비운다 · 55 전부 같은 결과였다).
_LAKELESS = ["env", "FIRE_LANE_DATA=", "FIRE_LANE_RAW=", "bash", "-c"]
#: 훅 게이트 중 ㉨ 가 **안 도는** 것 — 이미 더 센 축이 있다. 키는 `gate_parity.keys` 의 검사기 열쇠, 값은 사유. 훅에서 사라진 열쇠가 여기 남으면 시험이 운다.
HOOK_REPLACED: dict[str, str] = {
    "tools/testpick.py": "㉥ 가 같은 선택 함수로 더 큰 묶음을 돈다(`--no-cap` · 바뀐 파일에 닿는 시험 전부)",
    "tools/docseal.py": "㉡ · ㉢ 가 같은 판정(`docseal check`)을 사람이 칠 명령과 함께 낸다",
}


def mirror_commands() -> tuple[list[tuple[str, str, list[str]]], dict[str, str]]:
    """㉨ 가 돌 것 — (층, 이름, argv 앞머리)와 훅에서 빠진 것(사유). **둘 다 도출한다**: 훅은 `pre-push.gates`, ready 는 CI(`tools/gatefast.py` 의 층 표) — 사본이 없다."""
    import gate_parity as GP
    import gatefast as GF
    out: list[tuple[str, str, list[str]]] = []
    skipped: dict[str, str] = {}
    for name, cmd in GP.gate_commands():
        ks = GP.keys(cmd)
        if ks and ks[0] in HOOK_REPLACED:
            skipped[ks[0]] = HOOK_REPLACED[ks[0]]
            continue
        out.append(("훅", name, ["bash", "-c", cmd]))
    seen: set[str] = set()
    for k, script in GF.ready_commands():       # 한 단계가 열쇠 여럿을 들면(엄격 린트 = owned_paths + ruff) 그 스크립트를 **한 번만** 돈다
        if script not in seen:
            seen.add(script)
            out.append(("ready", GF.fmt_id(k), [*_LAKELESS, script]))
    return out, skipped


def check_ci_mirror(root: Path, run: Runner) -> Block | None:
    """**훅 게이트 전부**(`pre-push.gates` — 시험 묶음 · 도장은 더 센 ㉥ · ㉡ 가 맡는다)와 **CI 빠른 잡 중 훅 예산에 못 든 검사**(`gatefast` 의 `ready` 층)를 **글자 그대로** 돈다. (PLAN #216)

    ★ 이것으로 **pushready ≥ 훅**이다 — 종전에는 훅 24게이트 중 15개를 어느 경로로도 안 봐서 먼저 보는 도구가 나중 도구보다 약했다. 두 목록 모두 도출이라 사본이 없다.
    ★ 층 표가 CI 와 어긋나도(미선언 · 죽은 선언) 여기서 막는다 — 새 CI 검사가 층 없이 들어오면 이 행이 다시 열린다.
    ★ 병렬 `MIRROR_WORKERS` 로 돈다. 읽기 전용 검사만 든다(CI 빠른 잡 45개는 돌고 나서 트리가 안 바뀐 것을 실측했다)."""
    from concurrent.futures import ThreadPoolExecutor

    import gatefast as GF
    rep = GF.layer_report()
    detail = [f"층 선언표가 CI 와 어긋난다 — {k}: {', '.join(GF.fmt_id(x) for x in rep[k][:6])}" for k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름") if rep[k]]
    jobs, _skipped = mirror_commands()
    with ThreadPoolExecutor(max_workers=MIRROR_WORKERS) as ex:
        results = list(ex.map(lambda j: (j, run(j[2], root)), jobs))
    red = [(j, out) for j, (rc, out) in results if rc != 0]
    for (layer, name, _argv), out in red[:10]:
        last = [x for x in out.strip().splitlines() if x.strip()][-1:] or ["(출력 없음)"]
        detail.append(f"[{layer}] {name} — {last[0][:150]}")
    if not detail:
        return None
    n_hook = sum(1 for j in jobs if j[0] == "훅")
    what = f"훅 게이트 · CI 빠른 잡 검사 {len(red)}개가 빨갛다(훅 {n_hook} + ready {len(jobs) - n_hook} 중)" if red else "층 선언표가 CI 와 어긋난다"
    return Block("㉨", what, detail, [*[j[2][-1] for j, _o in red[:6]], "# 층 선언표는 tools/gatefast.py 의 LAYERS — 새 CI 검사는 거기에 층을 적는다"])


# ── ㉧ 로컬이 원격 추적 가지보다 뒤인가 ──────────────────────────
#: ★ 한계를 **출력에 적는다** — 이 축은 네트워크를 안 타므로 마지막 `git fetch` 이후의 일은 못 본다.
BEHIND_LIMIT = "마지막 `git fetch` 이후의 뒤처짐은 못 본다. 정확히 보려면 `git fetch` 를 먼저 쳐라."


def _upstream(root: Path, run: Runner) -> str | None:
    rc, out = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root)
    return out.strip() if rc == 0 and out.strip() else None


def check_behind(root: Path, run: Runner) -> Block | None:
    """`git rev-list --left-right --count HEAD...@{u}` — 로컬이 업스트림보다 **뒤**면 막는다. (PLAN #211)

    2026-11-08 원격만 갱신됐고(main → part/* 동기화 — **사람이 치는** `tools/merge_batch.sh` 의 단계다 · 자동 워크플로는 없다 · PLAN #221) 로컬은 열여섯 커밋을 그 위에 쌓아 푸시가 non-fast-forward 로 거절됐다.
    ★ 읽기 전용이다. `fetch` 를 안 한다 — 네트워크를 타면 `actionpin` 과 같은 사유로 사람 전용이 되어 매번 못 돈다.
    업스트림이 없는 가지는 **막지 않는다**(`notes()` 가 그 사실만 적는다). 읽을 수 없으면 닫힌 쪽(막는다).
    """
    up = _upstream(root, run)
    if up is None:
        return None
    rc, out = run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], root)
    nums = out.split()
    if rc != 0 or len(nums) != 2 or not all(n.isdigit() for n in nums):
        return Block("㉧", f"{up} 와의 앞뒤를 못 읽었다", out.strip().splitlines()[-3:] + [BEHIND_LIMIT], ["git status -sb"])
    ahead, behind = int(nums[0]), int(nums[1])
    if behind == 0:
        return None
    return Block("㉧", f"로컬이 {up} 보다 {behind} 커밋 뒤다(앞 {ahead}) — 푸시가 non-fast-forward 로 거절된다",
                 [BEHIND_LIMIT], [f"git merge {up}   # 받은 뒤 트리가 바뀌므로 아래 사슬을 다시 돈다"])


def notes(root: Path = ROOT, run: Runner = real_run) -> list[str]:
    """막지는 않고 **적기만** 하는 사실."""
    if _upstream(root, run) is None:
        return ["업스트림이 없는 가지다(`@{u}` 없음) — 원격보다 뒤인지는 못 봤다. 막지 않는다."]
    return []


# ── 몇 바퀴 남았나 (PLAN #220) ───────────────────────────────────
#: **되먹임 그래프**(2026-11-11 · `#220` 의 실측). 사슬은 도장 없는 절(㉢) → 래칫(㉠) → 변이 장부(㉤) → 낡은 도장(㉡) 순서다(2026-11-14 — 종전 ㉠ ㉤ ㉡ ㉢ 에서는 ㉢→㉠ 이 뒤로 가는 변이라 확정 2바퀴였다). 그래도 뒤가 앞이 읽는 것을 **쓰는** 변이 있어 위상 정렬이 안 된다.
#: 각 변은 `(from, to, 확정인가, 앞으로 가는가, 사유)` 다. **앞으로 가는 변**(순서에서 to 가 뒤)은 같은 바퀴에서 풀리고, **뒤로 가는 변**은 바퀴를 늘린다.
#: 근거 — `실측`: 감사 훅으로 읽기 · 쓰기를 쟀다(`fix.sh` 를 복사본에서 돌려 래칫이 `data/golden/{mutation,docseal}.json` 을 읽는 것까지) · `서술`: 도구 머리말만 근거다(그 도구는 사람 몫이라 안 돌렸다).
EDGES: list[tuple[str, str, bool, str]] = [
    ("㉠", "㉤", True, "`ratchet --write` 가 도구 소스의 상수를 쓴다 → 그 도구의 변이 지문이 어긋난다(서술 · `mutate.catch_print`)"),
    ("㉠", "㉡", False, "그 도구를 지목한 절이 있으면 도장도 낡는다(서술 — 절마다 다르다)"),
    ("㉤", "㉠", False, "래칫이 `data/golden/mutation.json` 을 읽는다(실측) — 장부가 바뀌면 상수가 움직일 수 있다"),
    ("㉤", "㉤", False, "`mutate` 가 장부를 쓴 뒤 **제 래칫 상수를 맨 끝에 적는다**(`ratchet.py` 머리말 · 서술) — 제 소스가 바뀌어 자기 지문이 또 어긋날 수 있다"),
    ("㉢", "㉠", True, "도장 없는 절이 줄어 `UNSEALED` 가 조여진다 — 래칫이 `data/golden/docseal.json` 을 읽는다(실측) · 조이는 쪽이 생긴다"),
]
ORDER = ["㉢", "㉠", "㉤", "㉡"]       # 사람이 칠 순서(㉣ 커밋은 늘 맨 끝 — 바퀴 밖)
LAP_CAP = 4
#: 표본 — 2026-11-10~11 사람이 돈 바퀴. **한 건이다** · 단계별 기록은 없다. 모델의 확정 바퀴는 이 표본보다 작다 — 되돌아올 수 있는 변이 실제로 밟혔다는 뜻이다.
SAMPLE_LAPS = 5


@dataclass
class Forecast:
    sure: int                  # 확정 변만 밟은 바퀴 수
    most: int                  # 가능한 변까지 밟은 바퀴 수(`LAP_CAP` 에서 자른다)
    capped: bool
    lines: list[str]


def _simulate(start: dict[str, bool], wrote: bool, possible: bool) -> tuple[int, bool, list[str]]:
    """바퀴를 센다. `start` = 지금 막는 칸 → 그 칸이 확정인가. `wrote` = ㉠ 이 상수를 쓰는 칸인가(조이는 쪽이 있는가). `possible` 이면 확정이 아닌 변도 밟는다."""
    need = dict(start)
    entered: set[str] = set()       # 변을 타고 들어온 칸 — 그 칸은 **고쳐 쓰는** 칸이다(처음부터 막던 ㉠ 만 `wrote` 를 따진다)
    laps, notes = 0, []
    while need and laps < LAP_CAP:
        laps += 1
        nxt: dict[str, bool] = {}
        for step in ORDER:
            if step not in need:
                continue
            sure_here = need.pop(step)
            writes = step != "㉠" or wrote or step in entered
            entered.discard(step)
            for a, b, sure_edge, why in EDGES:
                if a != step or not writes:
                    continue
                if not sure_edge and not possible:
                    continue
                sure_to = sure_here and sure_edge
                tgt = need if ORDER.index(b) > ORDER.index(a) else nxt
                tgt[b] = tgt.get(b, False) or sure_to
                entered.add(b)
                if possible and laps == 1:
                    notes.append(f"{a}→{b} {'[확정]' if sure_to else '[가능]'} {why}")
        need = nxt
    return laps, bool(need), notes


def forecast(blocks: list[Block]) -> Forecast:
    """**이번에 사슬을 치면 다음에 무엇이 또 낡는가** — 막는 칸(`blocks`)과 `EDGES` 만으로 바퀴 수를 말한다. **읽기 전용 · 아무것도 안 친다.**

    ★ 모델이다 — 고정점을 증명하지 않는다(`#220`). 확정 변만 밟으면 최소, 가능한 변까지 밟으면 `LAP_CAP` 바퀴에서 자른다(가능한 자기 루프가 있어 끝이 안 난다)."""
    keys = {b.key: b for b in blocks}
    start = {k: True for k in ORDER if k in keys}
    ratchet = keys.get("㉠")
    wrote = bool(ratchet and any(c.lstrip().startswith("uv run python tools/ratchet.py --write") for c in ratchet.cmds))
    sure, _, _ = _simulate(start, wrote, possible=False)
    most, capped, notes = _simulate(start, wrote, possible=True)
    if not start:
        return Forecast(0, 0, False, ["막는 것이 사슬 안에 없다 — 0바퀴(커밋만 남았을 수 있다)"])
    names = {"㉠": "래칫", "㉤": "변이 장부", "㉡": "도장(낡음)", "㉢": "도장(없음)"}
    steps = [f"{names[k]}({k})" for k in ORDER if k in start]
    L = [f"이번에 {' → '.join(steps)} 순으로 치면 **확정 {sure}바퀴**" + (f" · 되돌아올 수 있는 변까지 밟으면 **{LAP_CAP}바퀴 이상**(가능한 자기 루프 — 고정점은 증명 안 됨)" if capped else f" · 가능한 변까지 밟으면 {most}바퀴"),
         *[f"    · {n}" for n in notes]]
    L.append(f"    · 표본: 2026-11-10~11 사람이 **{SAMPLE_LAPS}바퀴**를 돌았다(한 건 · 단계별 기록 없음) — 확정만 센 수는 그보다 작다. 되돌아올 수 있는 변이 실제로 밟혔다는 뜻이다")
    L.append("    · 이 도구는 치지 않았다 — 말하기만 한다. 한 바퀴를 친 뒤 이 명령을 다시 돌리면 남은 바퀴가 줄어든 채 다시 나온다")
    return Forecast(sure, most, capped, L)


#: 사슬 순서 — 도장 없는 절 → 래칫 → 변이 장부 → 낡은 도장 → 커밋(`ORDER` 와 같다 — 시험이 맞춘다). **싼 것을 앞에 두지 않는다**(사람이 칠 순서가 목록 순서다).
CHECKS: list[tuple[str, Callable[[Path, Runner], Block | None]]] = [
    ("㉧", check_behind), ("㉥", check_tests), ("㉦", check_obligations), ("㉨", check_ci_mirror), ("㉢", check_unsealed), ("㉠", check_ratchet), ("㉤", check_mutate),
    ("㉡", check_invalid_seals), ("㉣", check_dirty),
]


#: 앞뒤에 홀로 도는 칸. ㉧ 은 싸고(0초) ㉣ 은 **다른 칸이 다 끝난 뒤의 작업 트리**를 본다 — 가운데와 겹치면 안 된다.
_FIRST, _LAST = ("㉧",), ("㉣",)


def survey(root: Path = ROOT, run: Runner = real_run, *, log: Callable[[str], None] | None = None, parallel: bool = True) -> list[Block]:
    """칸을 모두 잰다. 돌려주는 순서는 **언제나 `CHECKS` 순서**다(사람이 칠 순서가 목록 순서 · 병렬이어도 같다).

    ★ 2026-11-14 (PLAN ㉕ B-③). 종전에는 아홉 칸을 한 줄로 돌았다 — 실측 325초 중 ㉥ 200 · ㉠ 58 · ㉨ 47 · ㉡ 8 · ㉢ 8. 가운데 일곱 칸은 **읽기만 한다**
      (시험은 거울에서 돌고 추적 파일 쓰기는 감사 훅이 문다 — PLAN #219 ①). 그래서 한꺼번에 띄워 가장 긴 하나로 줄인다. `parallel=False` 가 종전 한 줄 순서다.
    ★ 칸 하나가 예외로 죽으면 **전체가 죽는다**(삼키지 않는다) — 죽은 칸을 초록으로 읽는 것이 이 도구가 막는 병이다.
    """
    def one(key: str, fn: Callable[[Path, Runner], Block | None]) -> Block | None:
        t = time.monotonic()
        b = fn(root, run)
        if log:
            log(f"  {key} {'✗' if b else '✓'}  {time.monotonic() - t:5.1f}초")
        return b

    done: dict[str, Block | None] = {}
    middle = [(k, f) for k, f in CHECKS if k not in _FIRST + _LAST]
    for k, f in CHECKS:
        if k in _FIRST:
            done[k] = one(k, f)
    if parallel:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(middle)) as ex:
            futs = {k: ex.submit(one, k, f) for k, f in middle}
            for k, fut in futs.items():
                done[k] = fut.result()          # 예외는 여기서 다시 던져진다
    else:
        for k, f in middle:
            done[k] = one(k, f)
    for k, f in CHECKS:
        if k in _LAST:
            done[k] = one(k, f)
    return [b for k, _ in CHECKS if (b := done[k])]


def render(blocks: list[Block], notes: list[str] | None = None) -> str:
    tail = [f"  · {n}" for n in notes or []]
    if not blocks:
        return "\n".join(["✓ 푸시 가능 — 원격 대비 · 시험 묶음 · 새 파일 등재 · CI 빠른 잡 미러 · 래칫 · 변이 장부 · 도장(낡음 · 없음) · 커밋 여덟 축이 막지 않는다.",
                          "  (전수 pytest 는 안 돌았다 — 이 도구는 그 대신이 아니다.)",
                          f"  ★ {BEHIND_LIMIT}", *tail])
    L = [f"✗ 푸시 불가 — 막는 것 {len(blocks)}가지 (사슬 순서: 받기 → 시험 → 등재 의무 → CI 미러 → 도장 없는 절 → 래칫 → 변이 장부 → 낡은 도장 → 커밋)\n"]
    for b in blocks:
        L.append(f"  {b.key} {b.what}")
        L += [f"      {d}" for d in b.detail]
        L.append("    사람이 칠 명령:")
        L += [f"      {c}" for c in b.cmds]
        L.append("")
    fc = forecast(blocks)
    L.append("  ── 몇 바퀴 남았나 (PLAN #220 · 모델 — 치지 않는다)")
    L += [f"      {x}" for x in fc.lines]
    L.append("")
    L += tail
    L.append("  ★ 이 도구는 읽기만 한다. 도장은 사람이 읽고 찍는다. 찍은 뒤에는 **커밋까지** 한다 — 그리고 다시 이 명령을 돌린다.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv:
        print(__doc__)
        return 2
    blocks = survey(log=lambda s: print(s, file=sys.stderr))
    print(render(blocks, notes()))
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
