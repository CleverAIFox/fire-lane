"""
test_branch_tidy_green.py — `tools/branch_tidy.sh` 5절: 낡은 `refs/green/*` 를 가르는 자리.  (PLAN §13 W13-20)

── 이 시험이 무는 것 ──────────────────────────────────────────
① `green_stale` — 커밋 시각이 N일보다 오래된 ref 만 낸다. 경계 · 시각을 못 읽은 줄(「?」) · 빈 입력.
② **지우는 명령은 `--prune-green` 뒤에만 있다** — 인자 없이(`--auto --close-bots` 포함) 돌면 원격 ref 를 지울 길이 코드에 없다.
IN    tools/branch_tidy.sh
OUT   없음
밖    실제 원격 · `gh` 호출은 안 본다(함수와 조건만 문다).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

SH = Path(__file__).resolve().parents[1] / "tools" / "branch_tidy.sh"
NOW = 2_000_000_000
DAY = 86400


def _stale(days: int, lines: list[str]) -> list[str]:
    out = subprocess.run(["bash", "-c", f'BRANCH_TIDY_LIB=1 source "{SH}"; green_stale {days} {NOW}'], input="\n".join(lines) + "\n",
                         text=True, capture_output=True, check=True, timeout=30).stdout
    return out.split()


def test_only_refs_older_than_the_limit_are_stale():
    old, edge, fresh = f"refs/green/old\t{NOW - 31 * DAY}", f"refs/green/edge\t{NOW - 30 * DAY}", f"refs/green/fresh\t{NOW - 2 * DAY}"
    assert _stale(30, [old, edge, fresh]) == ["refs/green/old"], "정확히 30일은 둔다(넘은 것만 지운다)"
    assert _stale(1, [old, edge, fresh]) == ["refs/green/old", "refs/green/edge", "refs/green/fresh"]
    assert _stale(30, []) == []


def test_an_unreadable_date_is_kept_not_deleted():
    """합성 결함: 날짜 칸이 `?`(gh 가 못 읽음) · 빈칸 — 모를 때는 둔다."""
    assert _stale(30, ["refs/green/q\t?", "refs/green/e\t", f"refs/green/old\t{NOW - 99 * DAY}"]) == ["refs/green/old"]


def test_the_delete_command_exists_only_behind_the_explicit_flag():
    src = SH.read_text(encoding="utf-8")
    sec5 = src[src.index("# ── 5. refs/green/*"):src.index('say "끝"')]
    deletes = [ln for ln in sec5.splitlines() if "push -q origin --delete" in ln]
    assert len(deletes) == 1
    guard = sec5[:sec5.index(deletes[0])]
    assert re.search(r'if \[ "\$PRUNE_GREEN" = 1 \]; then\s*$', guard), "삭제는 `PRUNE_GREEN=1` 분기 안에만 있어야 한다"
    assert "PRUNE_GREEN=0" in src.split("while [ $# -gt 0 ]")[0], "기본값은 지우지 않는다"
    assert "--auto) AUTO=1; shift ;;" in src and "AUTO=1; PRUNE_GREEN" not in src, "--auto 가 지우기를 켜면 안 된다"
