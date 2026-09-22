"""
test_workflow_static.py — 워크플로가 퇴역 예정 런타임 · 떠다니는 러너에 서 있지 않은가.

2026-09-22 (DECISIONS §218-4 · 토트 `check_static.py` 모범). 막는 목록과 알리는 장치는 짝이다 —
dependabot 봇 PR 이 알리고(청소만 하고 전부 닫지 않는다), 이 시험이 막는다. 종전엔 봇 PR 을 배치마다
전부 닫아서 `setup-node@v4` · `setup-uv@v3`(Node 20 런타임)가 알림 없이 남아 있었다.

  ① Node 20 런타임 액션 판을 쓰지 않는다 — GitHub 가 Node 20 을 퇴역시키면 워크플로가 죽는다
  ② 러너는 판을 고정한다 — `ubuntu-latest` 는 이미지가 바뀌는 날 로컬 · CI 가 조용히 갈린다
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GH = ROOT / ".github"

#: 액션 → Node 20 을 쓰는 마지막 주판. 이 판 이하를 쓰면 운다.
NODE20_LAST = {
    "actions/checkout": 4, "actions/setup-python": 5, "actions/setup-node": 4,
    "astral-sh/setup-uv": 6, "actions/upload-artifact": 4, "actions/download-artifact": 4,
    "actions/configure-pages": 5, "actions/deploy-pages": 4,
}


def _yamls():
    return sorted(p for p in GH.rglob("*.yml") if "dependabot" not in p.name)


def test_no_node20_actions():
    bad = []
    for p in _yamls():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r"uses:\s*([\w.-]+/[\w.-]+)@v(\d+)", line)
            if m and m.group(1) in NODE20_LAST and int(m.group(2)) <= NODE20_LAST[m.group(1)]:
                bad.append(f"{p.relative_to(ROOT)}:{i}  {m.group(1)}@v{m.group(2)}")
    assert not bad, "Node 20 런타임 액션 판이다 — 올린다:\n  " + "\n  ".join(bad)


def test_runners_are_pinned():
    bad = [f"{p.relative_to(ROOT)}:{i}" for p in _yamls()
           for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
           if re.search(r"runs-on:\s*\S*-latest", line)]
    assert not bad, "러너가 -latest 다 — 판을 고정한다:\n  " + "\n  ".join(bad)


def test_the_guard_bites():
    line = "      - uses: actions/setup-node@v4"
    m = re.search(r"uses:\s*([\w.-]+/[\w.-]+)@v(\d+)", line)
    assert m and int(m.group(2)) <= NODE20_LAST[m.group(1)], "옛 판을 못 알아본다 — 빈 그물이다"
