#!/usr/bin/env python3
"""
dmstree.py — **git 트리에 대한 물음 둘.** 봉인의 조상과 작업 트리의 내용 지문.

사용은 `dms.py tree` 하나다(깃발은 이 파일의 `cmd_tree` 가 읽는다) —
    tree                                  지금 트리의 지문
    tree 의 forget 깃발                    verify 시작 — 옛 도장을 치우고 지문을 낸다
    tree 의 stamp 깃발 + 시작 지문          verify 초록 — 그 사이 안 바뀌었으면 도장
    tree 의 check 깃발                     fl.sh 전수 초록 직후 — 도장 뒤에 트리가 바뀌었나
자기검사는 `dms.py --selftest` 가 끌어온다(`selftest()`).

── 왜 생겼나 (PLAN #173 · 2026-11-02 · DECISIONS §600) ─────────────
`verify.sh` 가 「통과 108 · 실패 0」만 내고 **무엇을 보고 찍었나**를 안 적었다.
머리말의 `HEAD <해시> +미커밋` 은 한 비트다 — 이미 더러운 트리에서 초록을 받고
파일을 더 고쳐도 같은 줄이다. 2026-10-14 에 생성 블록의 `sections` 값이 **틀린
채** 그렇게 커밋됐다(DECISIONS §525).

★ 지문은 **트리 객체**다. 임시 인덱스에 `HEAD` 를 읽고 추적 파일의 작업본을
  `git add -u` 로 얹어 `git write-tree` 한다. 깨끗하면 `HEAD^{tree}` 와 같다 —
  `fl.sh` 가 `.git/fl-green-trees` 에 적는 값과 **같은 값**이다(사본이 아니다).
  스쿼시는 commit 을 바꾸고 tree 는 안 바꾼다(`dms.py` `_green_skip` 이 적은 이유).
★ 생성물(`GENERATED` = `firelane.generated` 의 `seal` 역할)은 지문에서 **뺀다**
  — 임시 인덱스에서 `HEAD` 본으로 둔다. verify 가 돌며 다시 쓰고, 커밋 시점이
  따로인 것들이다. `src` · `tools` · `docs` 는 그대로 센다.
★ 못 재면 `None` 이다. 빈 문자열이 아니다 — 못 잰 것을 「같다」로 읽지 않는다.

── `ancestry` 는 `dms.py` 에서 옮겨 왔다 (동작 변경 0) ────────────
`dms.py` 가 상한(1,824줄)에 붙어 있어 새 덩이를 넣을 자리가 없었다. 예외를
올리지 않고 **독립적인 덩이를 뺐다**(`seg/walkcarve.py` 와 같은 방식 — DECISIONS
§523). 몸통은 한 글자도 안 바꿨다. 다만 `SEAL` 상수를 `dms.py` 가 들고 있어
인자(`seal_name`)로 받는다 — 이 파일이 `dms` 를 부르면 순환이다.

부류  몸통   진입점이 **아니다.** `dms.py` 가 부른다 — 부류는 거기서 물려받는다  (DECISIONS §398)

IN    git (`rev-parse` · `read-tree` · `add -u` · `write-tree` · `diff-tree`) · `.git/verify-tree`
OUT   트리 지문(40자) · `.git/verify-tree` · 거절 문구
PARAM 없음 (생성물 경로는 부르는 쪽이 넘긴다)
밖    **지문이 옳은 트리인가는 안 본다.** 같은 내용이면 같고 다르면 다르다는 것뿐이다.
      untracked 파일은 안 센다 — verify 가 보는 것도 추적 파일이다(`fl.sh` 1단계와 같다).
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import tempfile
from pathlib import Path

from firelane import gitq
from firelane.paths import env as _env

STAMP = "verify-tree"                                  # .git/ 아래 — 추적 파일이 아니다
_LINE = re.compile(r"^TREE\s+([0-9a-f]{40})\b")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def ancestry(root: Path, seal_name: str) -> tuple[int, str]:
    """**봉인이 가리키는 커밋이 이 트리의 조상인가.** (rc, 사유)

    ★ 2026-09-21 (PLAN §13 W11-1 · DECISIONS §204 · §207 · §210). 봉인이
      `2130b14` 를 가리켰는데 그 커밋은 `refs/pull/108/head` 에만 살아 있었다.
      feat 가지 위에서 찍고 그 가지를 스쿼시했기 때문이다. `git clone` 만 한
      사람에게는 **없는 커밋**이었고 `delta` 는 「전수 재검사다」만 찍고 rc=0 이었다
      — 이틀 동안 아무것도 안 울었다.

    ★ 물음은 「`main` 의 조상인가」가 아니라 **「봉인 파일을 싣고 있는 이 트리의
      조상인가」**다. 봉인 파일은 제가 실린 트리의 역사를 가리켜야 한다. feat 가지에서
      물어도, part/infra 에서 물어도, main 에서 물어도 같은 답이 나와야 옳다.

    ★ 판정 셋 — 전부 **실패**다. 못 잰 것을 통과로 치지 않는다.
        얕은 클론     조상을 잴 역사가 없다 (CI 기본 `fetch-depth: 1`)
        없는 커밋     이 저장소가 모르는 해시다 — `2130b14` 의 모양
        조상 아님     있기는 한데 이 트리의 역사 밖이다
    """
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=root, capture_output=True,
                              text=True, check=False, stdin=subprocess.DEVNULL)

    seal = root / "data" / "dms" / seal_name
    if not seal.is_file():
        return 1, f"봉인이 없다 — {seal.relative_to(root)}"
    try:
        c = json.loads(seal.read_text(encoding="utf-8")).get("commit") or ""
    except json.JSONDecodeError as e:
        return 1, f"봉인을 못 읽었다 — {e}"
    if not re.fullmatch(r"[0-9a-f]{7,40}", c):
        return 1, f"봉인의 `commit` 이 해시 꼴이 아니다 — {c!r}"
    sh = git("rev-parse", "--is-shallow-repository")
    if sh.returncode != 0:
        return 1, "git 저장소가 아니다 — 조상을 잴 수 없다"
    if sh.stdout.strip() == "true":
        return 1, ("얕은 클론이다 — 조상을 잴 역사가 없다. "
                   "`git fetch --unshallow` 뒤 다시 돌려라")
    if git("cat-file", "-e", f"{c}^{{commit}}").returncode != 0:
        return 1, (f"봉인이 가리키는 `{c}` 가 이 저장소에 없다 — "
                   "스쿼시로 사라진 커밋이다(DECISIONS §204 의 `2130b14` 모양)")
    if git("merge-base", "--is-ancestor", c, "HEAD").returncode != 0:
        return 1, (f"봉인이 가리키는 `{c}` 가 HEAD 의 조상이 아니다 — "
                   "다른 가지에서 찍었거나 그 가지가 스쿼시됐다")
    return 0, f"봉인 `{c}` 는 HEAD 의 조상이다"


def _git_dir(root: Path) -> Path | None:
    gd = gitq.ask(["rev-parse", "--git-dir"], cwd=root)
    if not gd or not gd.strip():
        return None
    p = Path(gd.strip())
    return p if p.is_absolute() else root / p


def _base_env() -> dict[str, str]:
    """git 이 돌 최소 환경. `os.environ` 은 paths.py 만 읽는다(env_check)."""
    return {k: v for k in ("PATH", "HOME", "SYSTEMROOT") if (v := _env(k))}


def tree_print(root: Path, gen: tuple[str, ...]) -> str | None:
    """작업 트리(추적 파일 · 생성물 뺌)의 트리 객체 해시. 못 재면 `None`."""
    if gitq.ask(["rev-parse", "--verify", "-q", "HEAD"], cwd=root) is None:
        return None
    with tempfile.TemporaryDirectory() as td:
        env = {**_base_env(), "GIT_INDEX_FILE": str(Path(td) / "index")}

        def run(*a: str) -> str | None:
            try:
                r = subprocess.run(["git", *a], cwd=root, env=env, capture_output=True,
                                   text=True, check=False, timeout=120,
                                   stdin=subprocess.DEVNULL)
            except (OSError, subprocess.TimeoutExpired):
                return None
            return r.stdout if r.returncode == 0 else None

        if run("read-tree", "HEAD") is None:
            return None
        if run("add", "-u", "--", ".", *(f":(exclude){g.rstrip('/')}" for g in gen)) is None:
            return None
        out = run("write-tree")
    return out.strip() if out and out.strip() else None


def _diff(root: Path, old: str, new: str) -> list[str]:
    """`old` 트리와 `new` 트리 사이에서 바뀐 파일. 화면에는 `--stat` 을 찍는다."""
    names = gitq.ask(["diff-tree", "-r", "--name-only", old, new], cwd=root)
    if names is None:
        print(f"  (로그의 트리 {old[:12]} 가 이 저장소에 없다 — 가지치기로 사라졌다. 다시 돌리면 된다)")
        return []
    print(f"  git diff-tree --stat {old[:12]} {new[:12]}")
    stat = gitq.ask(["diff-tree", "-r", "--stat", old, new], cwd=root) or ""
    for ln in stat.rstrip("\n").split("\n")[:12]:
        print("    " + ln)
    return [n for n in names.split("\n") if n]


def log_stale(log: Path, root: Path, gen: tuple[str, ...]) -> list[str] | None:
    """verify 로그의 `TREE` 줄과 지금 트리를 대조한다. 줄이 없으면 `None`(옛 로그 — 부르는 쪽이 HEAD 로 본다).

    같으면 `[]`, 다르면 바뀐 파일 목록, 못 쟀으면 사유 한 줄.
    """
    got = None
    for ln in log.read_text(encoding="utf-8", errors="replace").split("\n"):
        if m := _LINE.match(_ANSI.sub("", ln)):
            got = m.group(1)
    if got is None:
        return None
    now = tree_print(root, gen)
    if now is None:
        return ["git 이 지금 트리의 지문을 못 줬다 — 로그가 맞는지 알 수 없다"]
    return [] if now == got else (_diff(root, got, now) or [f"TREE {got[:12]} ↔ 지금 {now[:12]}"])


def cmd_tree(root: Path, gen: tuple[str, ...], args: list[str]) -> int:
    gd = _git_dir(root)
    stamp = gd / STAMP if gd else None
    now = tree_print(root, gen)
    if not args or args == ["--forget"]:
        if args and stamp is not None:
            stamp.unlink(missing_ok=True)
        print(now or "")
        return 0 if now else 1
    if args[0] == "--stamp":
        t0 = args[1] if len(args) > 1 else ""
        opt = dict(zip(args[2::2], args[3::2], strict=False))
        if not t0 or stamp is None or now is None:
            print("✗ 도장을 못 찍었다 — 시작 지문이 없거나 git 이 못 답했다. 이 실행은 증표가 아니다.")
            return 1
        if now != t0:
            print(f"✗ verify 가 도는 동안 트리가 바뀌었다 — 시작 {t0[:12]} · 끝 {now[:12]}. 이 초록은 어느 트리의 것도 아니다.")
            _diff(root, t0, now)
            print("  ★ 도는 동안 파일을 건드리지 않았나 본다 — 다시 돌려라:  bash tools/verify.sh")
            return 1
        stamp.write_text(t0 + "\n", encoding="utf-8")
        print(f"TREE    {t0}  단계 {opt.get('--steps', '?')} · 생략 {opt.get('--skipped', '?')}")
        return 0
    if args == ["--check"]:
        want = stamp.read_text(encoding="utf-8").strip() if stamp is not None and stamp.is_file() else ""
        if not re.fullmatch(r"[0-9a-f]{40}", want):
            print("✗ verify 가 도장(`.git/verify-tree`)을 안 남겼다 — 전수 초록이 아니다.")
            print("  다시 돌려라:  bash tools/verify.sh")
            return 1
        if now == want:
            print(f"✓ 트리가 도장과 같다 — {want[:12]}")
            return 0
        print(f"✗ 전수 초록 뒤에 트리가 바뀌었다 — 도장 {want[:12]} · 지금 {(now or '못 잼')[:12]}")
        if now:
            _diff(root, want, now)
        print("  ★ 초록은 도장의 트리에 대한 것이다. 바뀐 파일을 되돌리거나, 커밋할 것이면 다시 돌려라 —\n"
              "    bash tools/verify.sh")
        return 1
    print("tree [--forget | --stamp <지문> --steps N --skipped N | --check]")
    return 2


def selftest() -> int:
    """깨끗하면 HEAD^{tree} · 추적 파일을 고치면 달라짐 · 생성물만 고치면 같음 · 도장 뒤 수정은 거절."""
    bad: list[str] = []
    env = _base_env()
    gen = ("web/data/",)
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)

        def sh(*a: str) -> str:
            return subprocess.run(["git", *a], cwd=r, env=env, capture_output=True, text=True,
                                  check=True, stdin=subprocess.DEVNULL).stdout.strip()

        sh("init", "-q")
        (r / "web" / "data").mkdir(parents=True)
        (r / "a.txt").write_text("a\n", encoding="utf-8")
        (r / "web" / "data" / "g.json").write_text("{}\n", encoding="utf-8")
        sh("add", "-A")
        sh("-c", "commit.gpgsign=false", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c")
        head = sh("rev-parse", "HEAD^{tree}")
        if tree_print(r, gen) != head:
            bad.append("깨끗한 트리의 지문이 HEAD^{tree} 와 다르다 — fl-green-trees 와 못 만난다")
        (r / "web" / "data" / "g.json").write_text('{"x":1}\n', encoding="utf-8")
        (r / "new.txt").write_text("untracked\n", encoding="utf-8")
        if tree_print(r, gen) != head:
            bad.append("생성물만 바뀌었는데 지문이 달라졌다 — 정상 verify 가 거절당한다")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc_stamp = cmd_tree(r, gen, ["--stamp", head, "--steps", "3", "--skipped", "0"])
            rc_ok = cmd_tree(r, gen, ["--check"])
        if rc_stamp or rc_ok or not buf.getvalue().startswith("TREE    " + head):
            bad.append("생성물만 바뀐 트리가 도장·대조를 못 넘는다")
        (r / "a.txt").write_text("edited after the stamp\n", encoding="utf-8")
        if tree_print(r, gen) == head:
            bad.append("추적 파일을 고쳤는데 지문이 그대로다 — 이것이 #173 의 구멍이다")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc_bad = cmd_tree(r, gen, ["--check"])
        out = buf.getvalue()
        if rc_bad != 1 or "git diff-tree --stat" not in out or "bash tools/verify.sh" not in out:
            bad.append("도장 뒤 수정을 거절하지 않거나, 거절 문구에 diff-tree · 다시 돌릴 명령이 없다")
        log = r / "v.log"
        log.write_text(f"x\n\x1b[32mTREE    {head}\x1b[0m  단계 3\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            stale = log_stale(log, r, gen)
        if not stale or "a.txt" not in stale:
            bad.append("로그의 TREE 가 지금 트리와 다른데 낡았다고 안 한다")
        log.write_text("옛 로그 — TREE 줄이 없다\n", encoding="utf-8")
        if log_stale(log, r, gen) is not None:
            bad.append("TREE 줄이 없는 옛 로그를 None 으로 안 돌려준다 — HEAD 판으로 못 떨어진다")
        sh("checkout", "--", "a.txt")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_tree(r, gen, ["--forget"])
            rc_gone = cmd_tree(r, gen, ["--check"])
        if rc_gone != 1:
            bad.append("--forget 뒤에도 옛 도장이 남아 있다 — 실패한 실행이 옛 초록을 물려받는다")
    for line in bad:
        print(f"  {line}")
    print("selftest " + ("빨강" if bad else "초록"))
    return len(bad)
