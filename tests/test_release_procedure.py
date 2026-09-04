#!/usr/bin/env python3
"""
test_release_procedure.py — 릴리즈 절차가 룰셋과 어긋나지 않는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-02. `MASTER §12-8b` 3·4단계가 `git push origin dev` ·
`git push origin part/*` 였다. 세 룰셋 전부 `pull_request` 필수인데(§12-1)
`bypass_actors` 가 살아 있어 통과했다. **09-03 회수 후에는 막힌다.**
규약은 있고 강제자가 없었다(§17). DECISIONS §90.

IN    docs/MASTER.md §12-8b
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# ★ 실행 줄만 본다. 산문에서 그 명령을 인용하는 것은 위반이 아니다 —
#   금지 사유를 적으려면 금지된 명령을 적어야 한다.
BAD = re.compile(r"^git push origin (dev|part/)")


def _s12_8b() -> str:
    t = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8").splitlines()
    s = next(i for i, l in enumerate(t) if l.startswith("### 12-8b."))
    e = next(i for i in range(s + 1, len(t)) if t[i].startswith("### 12-8c."))
    return "\n".join(t[s:e])


def test_release_steps_are_not_direct_pushes():
    """보호 브랜치에 직푸시하는 절차를 적지 않는다."""
    bad = [l for l in _s12_8b().splitlines() if BAD.search(l.strip())]
    assert not bad, (
        "MASTER §12-8b 가 보호 브랜치 직푸시를 적는다 — 룰셋이 막는다(§12-1).\n"
        + "\n".join(f"  {l.strip()}" for l in bad)
        + "\n  PR 로 적어라. 승인 0 이라 비용은 CI 대기뿐이다(DECISIONS §90).")


def test_release_step1_waits_for_merge():
    """1단계 머지 완료를 확인한 뒤 태그를 붙인다."""
    s = _s12_8b()
    assert "머지 완료를 확인한 뒤" in s, (
        "MASTER §12-8b 에 '1단계 머지를 기다린다' 가 없다.\n"
        "  스크립트로 연달아 치면 v0.3 자리에 태그가 붙는다(DECISIONS §90).")
