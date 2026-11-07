"""tools/pushready.py — 「푸시해도 되는가」 한 명령. 다섯 축을 **하나씩 망가뜨려** 각각 걸리는지 본다. (PLAN #207)

★ 양성 대조다. 초록 하나(`_green`)에서 시작해 ㉠~㉤ 를 하나씩만 깨고, **그 축만** 걸리는지 본다.
  ㉣ 는 합성이 아니라 **실제 git 저장소**로 한다 — 도장 파일만 고치고 커밋을 안 한 꼴(2026-11-08 에 두 번 물렸다).

밖    **실제 `ratchet.py` · `docseal.py` · `mutate.py` 를 안 돈다** — 합성 출력으로 「그 출력을 어떻게 읽는가」만 본다(실물은 2분이다).
      그 도구들이 옳게 우는가는 각자의 시험이 든다. 여기서는 **각 축이 막는가**와 **닫힌 쪽으로 실패하는가**만 본다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pushready as P  # noqa: E402 — `sys.path` 를 먼저 깔아야 import 가 된다

GREEN = {
    "ratchet": (0, "래칫 83개 · 낡음 0 (조이는 쪽 0 · 느슨해진 쪽 0)\n✓ 래칫이 전부 실측과 같다\n"),
    "mutate": (0, ""),
    "invalid": (0, ""),
    "unsealed": (0, "DECLARED 0\n"),
    "git": (0, ""),
}


def _runner(**over):
    """argv 를 보고 합성 출력을 낸다. `over` 로 한 축만 갈아 끼운다."""
    table = {**GREEN, **over}

    def run(argv: list[str], cwd: Path) -> tuple[int, str]:
        s = " ".join(argv)
        if "ratchet.py" in s:
            return table["ratchet"]
        if "import mutate" in s:
            return table["mutate"]
        if "--invalid-list" in s:
            return table["invalid"]
        if "import docseal" in s:
            return table["unsealed"]
        if argv[0] == "git":
            return table["git"]
        raise AssertionError(f"모르는 명령 {argv}")
    return run


def _keys(**over):
    return [b.key for b in P.survey(ROOT, _runner(**over))]


def test_all_green_is_pushable_and_exit_zero():
    assert P.survey(ROOT, _runner()) == []
    assert "푸시 가능" in P.render([])


def test_ratchet_loose_and_tight_are_caught_with_the_right_command():
    loose = (1, "래칫 83개 · 낡음 1 (조이는 쪽 0 · 느슨해진 쪽 1)\n"
                "\n  ✗ suppress.py · SUPPRESS — **느슨해지는 쪽**이다  선언 55 → 실측 56 (down)\n")
    b = P.survey(ROOT, _runner(ratchet=loose))
    assert [x.key for x in b] == ["㉠"] and "손으로" in " ".join(b[0].cmds) and "ratchet.py --write" not in " ".join(b[0].cmds)
    tight = (1, "래칫 83개 · 낡음 1 (조이는 쪽 1 · 느슨해진 쪽 0)\n  · planwork.py · PLAN_HISTORY  393 → 392  (--write 로 고친다)\n")
    b = P.survey(ROOT, _runner(ratchet=tight))
    assert [x.key for x in b] == ["㉠"] and any("ratchet.py --write" in c for c in b[0].cmds)


def test_ratchet_failing_with_unreadable_output_fails_closed():
    assert _keys(ratchet=(1, "Traceback ...\nboom\n")) == ["㉠"]


def test_ratchet_items_owned_by_other_axes_are_not_double_counted():
    only_seal = (1, "래칫 83개 · 낡음 1\n  ✗ docseal.py · UNSEALED — **느슨해지는 쪽**이다  선언 0 → 실측 1 (down)\n"
                    "  ✗ mutate.py · — — `ratchet_values()` 가 죽었다\n")
    assert _keys(ratchet=only_seal) == []      # ㉢ · ㉤ 이 맡는다 — 그 둘이 초록이면 여기서 막지 않는다


def test_invalid_seals_are_caught():
    b = P.survey(ROOT, _runner(invalid=(0, "DECISIONS/190-5\nPLAN/10-5\n")))
    assert [x.key for x in b] == ["㉡"] and "2절" in b[0].what and any("stamp" in c for c in b[0].cmds)


def test_unsealed_above_the_declared_count_is_caught():
    b = P.survey(ROOT, _runner(unsealed=(0, "DECLARED 0\nUNSEALED DECISIONS/661\n")))
    assert [x.key for x in b] == ["㉢"] and "DECISIONS/661" in " ".join(b[0].detail)
    # 선언과 같으면 통과한다(선언이 1 이면 1 은 허용)
    assert _keys(unsealed=(0, "DECLARED 1\nUNSEALED DECISIONS/661\n")) == []


def test_stale_mutation_ledger_is_caught():
    b = P.survey(ROOT, _runner(mutate=(1, "RuntimeError: 2개가 잰 뒤로 바뀌었다 — sizecheck, srccov.")))
    assert [x.key for x in b] == ["㉤"] and any("mutate.py --write --stale" in c for c in b[0].cmds)


def _git(cwd: Path, *a: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd, check=True, capture_output=True)


def test_a_stamp_without_a_commit_is_caught_in_a_real_repo(tmp_path: Path):
    """★★ 도장만 찍고 커밋 안 한 상태. 나머지 네 축은 초록이어도 ㉣ 가 막는다."""
    _git(tmp_path, "init", "-q")
    seal = tmp_path / P.SEAL_FILE
    seal.parent.mkdir(parents=True)
    seal.write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    assert P.check_dirty(tmp_path, P.real_run) is None            # 깨끗하면 통과
    (tmp_path / "new_untracked.txt").write_text("x", encoding="utf-8")
    assert P.check_dirty(tmp_path, P.real_run) is None            # 추적 안 된 새 파일은 막지 않는다
    seal.write_text('{"stamped": 1}\n', encoding="utf-8")         # 도장만 찍고 커밋 안 함
    b = P.check_dirty(tmp_path, P.real_run)
    assert b is not None and b.key == "㉣"
    assert "test_fix_door" in " ".join(b.detail) and "git commit" in b.cmds
    _git(tmp_path, "add", "-A")                                   # 스테이징만 해도 아직 커밋이 아니다
    assert P.check_dirty(tmp_path, P.real_run) is not None
    _git(tmp_path, "commit", "-q", "-m", "stamp")
    assert P.check_dirty(tmp_path, P.real_run) is None            # 커밋하면 풀린다


def test_every_blocker_prints_a_command_and_exit_code_follows(capsys, monkeypatch):
    blocks = P.survey(ROOT, _runner(invalid=(0, "A/1\n"), git=(0, " M data/golden/docseal.json\n"),
                                    mutate=(1, "x")))
    assert [b.key for b in blocks] == ["㉤", "㉡", "㉣"]       # 사슬 순서 — 변이 장부 → 도장 → 커밋
    text = P.render(blocks)
    assert text.count("사람이 칠 명령") == 3 and "푸시 불가" in text
    monkeypatch.setattr(P, "survey", lambda *a, **k: blocks)
    assert P.main([]) == 1
    monkeypatch.setattr(P, "survey", lambda *a, **k: [])
    assert P.main([]) == 0
    assert P.main(["--write"]) == 2          # 쓰기 옵션은 없다 — 읽기 전용
