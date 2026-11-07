#!/usr/bin/env python3
"""
test_fix_door.py — **수리 문이 실제로 고치는가.** (DECISIONS §362)

★ 문이 있다는 것과 문이 열린다는 것은 다르다. 이 저장소가 반복해 당한 형태가
  바로 그것이다(`§96` — 「목록에 있는 것과 도는 것은 다르다」).

★ **합성 결함을 심고 민다.** 실제 저장소에서 「0건이니 통과」는 아무것도
  증명하지 않는다 — 깨끗한 트리에서는 안 고치는 문도 통과한다(`deadcheck`
  머리말이 적는 그 병).

IN    tools/fix.sh · tools/fixable.py
OUT   없음 (검사)
밖    **문이 고르는 목록이 옳은가는 안 본다** — 그것은 `fixable.py` 의
      세 갈래가 들고, 사유는 `HUMAN_FIRST` · `NO_REPAIR` 에 있다.
      **문이 전부를 고치는가도 안 본다.** 고칠 수 있는 것만 고치는 것이 뜻이다.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOOR = ROOT / "tools" / "fix.sh"

_spec = importlib.util.spec_from_file_location("fixable", ROOT / "tools" / "fixable.py")
fixable = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = fixable
_spec.loader.exec_module(fixable)


@pytest.fixture
def tree(tmp_path: Path):
    """**격리된 작업 트리** — 문이 쓰는 곳이 이 저장소가 아니라 여기다. (Zm39 · DECISIONS §580)

    ★ 종전에는 `_run` 이 **실제 트리**에서 `tools/fix.sh` 를 통째로 돌렸다. 문은 기획서 표지 날짜(`build_proposal --touch-today`)와
      래칫 상수(`ratchet.py --write`)까지 고치는데 시험은 `MASTER.md` 하나만 되돌렸다 — 트리가 문과 어긋나 있으면 **시험이 그것을
      고쳐 놓았다**(2026-10-25 에 `docs/proposal.md` · `web/proposal.html` · `tools/sealcov.py` 가 그렇게 바뀌었다).
      `git worktree` 는 HEAD 의 추적 파일을 새 디렉터리에 낸다 — `.git` 이 이어져 있어 날짜 유도(git 이력)가 그대로 돈다.
    """
    wt = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), "HEAD"], cwd=ROOT, check=True, capture_output=True, timeout=120)
    try:
        yield wt
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, check=False, capture_output=True, timeout=120)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, check=False, capture_output=True, timeout=60)


def _run(wt: Path, *args: str) -> subprocess.CompletedProcess:
    """문을 **복사본에서** 돈다. 가상환경은 이 저장소 것을 쓰되(`UV_NO_SYNC` — 동기화하면 편집 설치가 복사본으로 옮겨 간다)
    `firelane` · `tools` 는 복사본 것이 먼저 잡히게 한다 — 안 그러면 `paths` 가 이 저장소 루트를 읽어 문이 **여기에 쓴다.**"""
    env = {**os.environ, "UV_NO_SYNC": "1", "UV_PROJECT_ENVIRONMENT": sys.prefix,
           "PYTHONPATH": os.pathsep.join([str(wt / "src"), str(wt / "tools"), os.environ.get("PYTHONPATH", "")])}
    return subprocess.run(["bash", str(wt / "tools" / "fix.sh"), *args], cwd=wt, check=False, env=env,
                          capture_output=True, text=True, timeout=900)


def test_the_door_exists_and_declares_what_it_does_not_do():
    """문이 제 `밖` 칸을 적는가 — 안 적으면 범위가 이름보다 좁은 줄 모른다(§226)."""
    src = DOOR.read_text(encoding="utf-8")
    assert "\n# 밖 " in src or "\n#       " in src, "`밖` 칸이 없다"
    assert "재지 않는다" in src, (
        "문이 **자기가 고친 것을 자기가 재지 않는다**는 선언이 없다 — "
        "그 선언이 이 문과 `verify.sh` 를 가르는 전부다")


def test_the_door_does_not_call_a_judgment_tool():
    """★ 판단이 필요한 도구를 **부르지 않는가.** 부르면 봉인·골든이 죽는다."""
    src = DOOR.read_text(encoding="utf-8")
    called = set(re.findall(r"(tools/[\w/]+\.(?:py|sh))", src))
    bad = sorted(called & set(fixable.HUMAN_FIRST))
    assert not bad, (
        f"문이 사람 판단이 먼저인 도구를 부른다: {bad}\n"
        "  `docseal stamp` 를 기계가 찍으면 그 도장은 아무것도 안 뜻하고,\n"
        "  `golden lock` 을 기계가 찍으면 움직인 판정이 그대로 정답이 된다.")


def test_the_door_does_not_call_a_dead_flag():
    """폐지된 깃발을 부르지 않는가 — 부르면 매번 빨강 하나가 상수로 선다."""
    src = DOOR.read_text(encoding="utf-8")
    for tool in fixable.NO_REPAIR:
        for ln in src.splitlines():
            if ln.lstrip().startswith("#"):
                continue
            assert tool not in ln, f"{tool} 은 수리 경로가 없다 — 부르지 마라"


def test_dry_run_changes_nothing(tree: Path):
    """`--dry` 가 정말 아무것도 안 건드리는가. (복사본의 `git status` 로 잰다)"""
    before = subprocess.run(["git", "status", "--porcelain"], cwd=tree, capture_output=True, text=True, timeout=60, check=True).stdout
    r = _run(tree, "--dry")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "아무것도 안 고쳤다" in r.stdout
    after = subprocess.run(["git", "status", "--porcelain"], cwd=tree, capture_output=True, text=True, timeout=60, check=True).stdout
    assert before == after, "`--dry` 가 트리를 건드렸다"


def test_the_door_actually_repairs_an_injected_defect(tree: Path):
    """★ 양성 대조. **생성 블록을 일부러 틀리고** 문이 되돌리는가.

    고르는 자리가 생성 블록인 이유 — 되돌림이 **바이트 단위로 증명된다.** 정본이 실물이라 고친 뒤의 값이 하나뿐이다.
    심는 곳은 **복사본의** `MASTER.md` 다 — 이 저장소의 것은 건드리지 않는다(`tests/tracked_guard.py` 가 세션 끝에 그것을 잰다).
    """
    master = tree / "docs" / "MASTER.md"
    original = master.read_text(encoding="utf-8")
    m = re.search(r"절 ([\d,]+) 전수", original)
    assert m, "MASTER 의 생성 블록 표기가 바뀌었다 — 이 시험을 고쳐라"
    broken = original.replace(m.group(0), "절 9,999 전수", 1)
    assert broken != original

    master.write_text(broken, encoding="utf-8")
    r = _run(tree)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "9,999" in r.stdout, f"문이 심은 결함을 못 봤다\n{r.stdout}"
    assert master.read_text(encoding="utf-8") == original, "문이 돌았는데 파일이 원래대로 안 돌아왔다"


def test_every_mechanical_step_is_behind_the_door():
    """`fixable` 의 래칫과 같은 물음 — 여기서는 **CI 가** 묻는다."""
    assert fixable.ratchet_values()["UNDOORED"] == fixable.UNDOORED, (
        "기계가 고칠 수 있는데 문에 안 걸린 단계가 래칫과 다르다:\n  "
        + "\n  ".join(f"{n} — {t}" for n, t in fixable.undoored()))


def test_the_human_table_states_a_reason():
    """면제는 **사유가 본체다.** 한 줄짜리 사유는 사유가 아니다."""
    thin = {t: w for t, w in fixable.HUMAN_FIRST.items() if len(w) < 40}
    assert not thin, f"사유가 너무 짧다 — 왜 기계가 못 하는가: {list(thin)}"
    thin2 = {t: w for t, w in fixable.NO_REPAIR.items() if len(w) < 40}
    assert not thin2, f"사유가 너무 짧다: {list(thin2)}"


def test_the_door_declares_the_gates_it_cannot_cover():
    """★ **문이 돌았는데도 안 덮이는 자리가 적혀 있는가.** (DECISIONS §374)

    실기(2026-10-03). 합본 배치를 만들고 `fix.sh` 를 다 돌려 「빨강 0」을 본 뒤
    보냈다. 전수 verify 를 돌리니 **「죽은 강제자 참조」가 빨갰다** — §367 의
    강제자 칸이 §370 의 개명을 안 따라온 것이었다.

    원인은 문이 없는 것이 **아니었다.** `fix.sh` 는 `dms.py --apply` 를 부르고
    관문은 `dms.py verify` 다 — **같은 도구의 다른 모드**다. 문이 그 자리를
    볼 수 없다는 사실이 **어디에도 안 적혀 있었다**(3족 · 관문이 갈림).

    ★ 이 시험이 미는 것은 「모드를 맞춰라」가 아니다. 맞출 수 없는 자리가 있다 —
      「`_oneway` 가 어디로 갔나」는 답이 하나가 아니다. 미는 것은
      **「안 덮인다는 사실이 적혀 있는가」**이고, 적히면 `fix.sh` 가 찍는다.
    """
    assert fixable.mode_gaps() == [], (
        "문이 안 덮는 관문 모드에 사유가 없다\n"
        + "\n".join(f"  · {t}  관문 모드 `{g}`" for t, g in fixable.mode_gaps())
        + "\n\n  `fixable.MODE_SPLIT` 에 **사유와 함께** 적어라.")

    # ★ 빈 그물 — 표가 비면 이 시험이 아무것도 안 지킨다
    assert fixable.MODE_SPLIT, (
        "`MODE_SPLIT` 이 비었다 — 실측에서 `dms.py` 셋이 있었다. "
        "정말 0 이 됐으면 이 단언을 지우고 그 사유를 적어라")

    # ★ 사유가 짧으면 사유가 아니다
    thin = [k for k, v in fixable.MODE_SPLIT.items() if len(v) < 40]
    assert not thin, f"사유가 40자 미만 — {thin}"

    # ★ `fix.sh` 가 **실제로 찍는가.** 표만 있고 안 찍으면 사람은 여전히 모른다
    sh = (ROOT / "tools" / "fix.sh").read_text(encoding="utf-8")
    assert "split_rows" in sh, (
        "`fix.sh` 가 `split_rows()` 를 안 부른다 — 표가 있어도 사람이 못 본다")


def test_the_mode_split_table_is_not_dead():
    """★ 반대 방향 — 문이 **실은 덮는** 모드를 「안 덮는다」고 적으면 거짓이다."""
    doors = fixable._subs((ROOT / "tools" / "fix.sh").read_text(encoding="utf-8"), "fix")
    covered = [k for k in fixable.MODE_SPLIT
               if k.split("::")[1] in doors.get(k.split("::")[0], set())]
    assert not covered, f"문이 덮는 모드를 든다 — {covered}. 줄을 지워라"

    gates = fixable._subs((ROOT / "tools" / "verify.sh").read_text(encoding="utf-8"), "step")
    unreal = [k for k in fixable.MODE_SPLIT
              if k.split("::")[1] not in gates.get(k.split("::")[0], set())]
    assert not unreal, (
        f"관문이 안 부르는 모드를 든다 — {unreal}. 그 단계가 사라졌으면 줄을 지워라")
