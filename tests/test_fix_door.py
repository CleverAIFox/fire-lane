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
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOOR = ROOT / "tools" / "fix.sh"

_spec = importlib.util.spec_from_file_location("fixable", ROOT / "tools" / "fixable.py")
fixable = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = fixable
_spec.loader.exec_module(fixable)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(DOOR), *args], cwd=ROOT, check=False,
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


def test_dry_run_changes_nothing():
    """`--dry` 가 정말 아무것도 안 건드리는가."""
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True, timeout=60, check=True).stdout
    r = _run("--dry")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "아무것도 안 고쳤다" in r.stdout
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True, timeout=60, check=True).stdout
    assert before == after, "`--dry` 가 트리를 건드렸다"


def test_the_door_actually_repairs_an_injected_defect():
    """★ 양성 대조. **생성 블록을 일부러 틀리고** 문이 되돌리는가.

    고르는 자리가 생성 블록인 이유 — 되돌림이 **바이트 단위로 증명된다.**
    정본이 실물이라 고친 뒤의 값이 하나뿐이다.
    """
    master = ROOT / "docs" / "MASTER.md"
    original = master.read_text(encoding="utf-8")
    m = re.search(r"절 ([\d,]+) 전수", original)
    assert m, "MASTER 의 생성 블록 표기가 바뀌었다 — 이 시험을 고쳐라"
    broken = original.replace(m.group(0), "절 9,999 전수", 1)
    assert broken != original

    try:
        master.write_text(broken, encoding="utf-8")
        r = _run()
        assert r.returncode == 0, r.stdout + r.stderr
        assert "9,999" in r.stdout, f"문이 심은 결함을 못 봤다\n{r.stdout}"
        assert master.read_text(encoding="utf-8") == original, (
            "문이 돌았는데 파일이 원래대로 안 돌아왔다")
    finally:
        if master.read_text(encoding="utf-8") != original:
            master.write_text(original, encoding="utf-8")


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
