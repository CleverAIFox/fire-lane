"""조사 도구 셋이 **불리고**, 사용법을 낸다.  (Zm36 · DECISIONS §579)

IN    tools/carve_survey.py · tools/dm_audit.py · tools/segid_audit.py
OUT   없음 (검사)
밖    **조사의 수가 옳은가는 안 본다** — 돌리지 않는다(각각 오래 걸리거나 이력을 읽는다). `--help` 만 부른다.

★ 이 셋은 답이 나오면 끝나는 조사 도구라 `verify.sh` 에 걸지 않는다. 그렇다고 `tests/test_tools_are_wired.py` 의 면제 표에 사유를 늘리지도 않는다 —
  면제는 사각지대다. 시험이 **불러서** 문다: `argparse` 가 살아 있어야 모르는 깃발을 거절한다(`test_cli_surface`).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from firelane import ledger

ROOT = Path(__file__).resolve().parents[1]


def _investigation_tools() -> list[str]:
    """대장에서 **유도한다** — 소비자가 없는 산출물을 내는 도구 중 `argparse` 로 사용법을 내는 것. 손으로 든 목록은 도구가 늘어도 안 따라간다(deadcheck ②)."""
    out: dict = ledger.load()["outputs"]
    tools = {v["produced_by"] for v in out.values()
             if isinstance(v, dict) and str(v.get("produced_by", "")).startswith("tools/") and not v.get("consumers")}
    return sorted(t for t in tools if (ROOT / t).exists() and "argparse" in (ROOT / t).read_text(encoding="utf-8"))


TOOLS = _investigation_tools()


def test_the_derivation_finds_the_three_tools() -> None:
    assert {"tools/carve_survey.py", "tools/dm_audit.py", "tools/segid_audit.py"} <= set(TOOLS), TOOLS


@pytest.mark.parametrize("tool", TOOLS)
def test_the_tool_prints_usage_without_starting_work(tool: str) -> None:
    r = subprocess.run([sys.executable, str(ROOT / tool), "--help"], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    assert r.returncode == 0, r.stderr
    assert r.stdout.lstrip().startswith("usage:"), r.stdout[:200]
