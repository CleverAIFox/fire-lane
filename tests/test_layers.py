#!/usr/bin/env python3
"""
test_layers.py — MASTER §18-1 계층 선언과 코드를 대조한다.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. §18-1 이 계층을 선언하는데 `interim` 은 `paths.py` 에 **선언
조차 없었다.** 그래서 탐색 도구가 갈 곳이 없어 프로젝트 루트에 떨궜다.

    jijeok_probe._side()  →  RAW.parent.parent   (프로젝트 루트)
    결과: jijeok_scope.gpkg 10.5MB · jijeok_width.gpkg · jijeok_join.gpkg
          check27.csv · check27.html · check42.csv

**계층이 없으면 파일은 아무 데나 떨어진다.** 규율이 아니라 구조의 문제다.
문서가 "여섯 계층" 이라고 적어놓고 코드가 넷만 알면, 나머지 둘을 쓰려던
도구는 매번 자기 자리를 발명한다.

IN    src/firelane/paths.py · docs/MASTER.md · tools/*.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

from firelane import paths

ROOT = Path(__file__).resolve().parent.parent

# MASTER §18-1 이 선언하는 계층. 여기와 문서가 어긋나면 한쪽이 낡은 것이다.
DECLARED = ["LANDING", "RAW", "NORM", "INTERIM",
            "PROCESSED", "FIELD", "QUARANTINE", "WEB"]


def test_every_declared_layer_exists_in_paths():
    missing = [n for n in DECLARED if not hasattr(paths, n)]
    assert not missing, (
        "MASTER §18-1 이 선언한 계층이 paths.py 에 없다: "
        + ", ".join(missing)
        + "\n  선언만 있고 코드가 모르면, 그 계층을 쓰려던 도구는\n"
        "  매번 자기 자리를 발명한다(2026-08-24 SSD 루트 오염).")


def test_master_layer_table_matches_paths():
    """문서 표의 계층 이름이 paths.py 에 전부 있는가."""
    txt = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    sec = txt.split("## 18-1. 계층", 1)
    if len(sec) < 2:
        return
    body = sec[1].split("## 18-2", 1)[0]
    named = set(re.findall(r"^\| `(\w+)` \|", body, re.M))
    known = {n.lower() for n in DECLARED}
    unknown = sorted(n for n in named if n.lower() not in known)
    assert not unknown, (
        f"문서 §18-1 이 적은 계층을 paths.py 가 모른다: {unknown}\n"
        "  둘 중 하나가 낡았다. 코드가 정본이고 문서를 고친다(§17).")


def test_no_tool_writes_outside_declared_layers():
    """★ 저장소 밖 임의 위치에 쓰지 않는다.

    `RAW.parent` · `RAW.parent.parent` 는 계층이 아니다. 거기 쓰면
    대장에도 gitignore 에도 안 잡히고 백업 대상도 아니다 — 사실상
    소실 대기 파일이 된다.
    """
    bad = []
    for p in sorted((ROOT / "tools").rglob("*.py")) + \
             sorted((ROOT / "src").rglob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            # ★ 사유를 적으려면 그 이름을 써야 한다. 주석·독스트링은 뺀다.
            #   test_sys_path_해킹이_없다 가 같은 함정을 이미 겪었다.
            if code.lstrip().startswith(("★", '"', "'")) or "종전" in code:
                continue
            if re.search(r"RAW\.parent(\.parent)?", code):
                bad.append(f"{p.relative_to(ROOT)}:{i}  {line.strip()[:70]}")
    assert not bad, (
        "계층 밖(raw 상위)을 작업 위치로 쓴다:\n  " + "\n  ".join(bad)
        + "\n  paths.INTERIM 을 써라. 2026-08-24 에 이것으로 SSD 루트가"
        " 오염됐다.")


def test_interim_is_not_committed():
    """interim 은 재생성 가능하다. 저장소에 들어오면 안 된다(R2)."""
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\s*/?data/interim/?", gi, re.M), \
        ".gitignore 에 data/interim 이 없다. 재생성 가능한 것은 커밋하지 않는다."
