#!/usr/bin/env python3
"""
test_tile_zoom_agreement.py — **굽는 줌과 읽는 줌이 같은가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §13 W9-2 · DECISIONS §205). 항공정사영상 타일의 줌 범위가
**세 곳**에 손으로 적혀 있고 셋이 갈려 있었다.

    src/firelane/ortho.py   TILE_Z = (15, 16, 17, 18, 19)     ← 굽는 쪽
    web/js/map.js           minzoom:15, maxzoom:18            ← 읽는 쪽 (2026-09-22 철거)
    tools/desk_check.py     Z = 18   # ortho.py TILE_Z 의 최대값   ← 세 번째 사본

MapLibre 는 소스 `maxzoom` 위로 타일을 요청하지 않는다. 그래서 z19 **1,035장
16.4MB** 가 저장소에 실려 커밋되고 배포되지만 **소비자가 0명**이다.
`web/data` 상한이 40MB 인데 현재 33.0MB 이고 그 **49.7%** 가 아무도 안 받는 타일이다.

★ 그리고 `desk_check.py` 의 주석이 **틀렸다** — 「`ortho.py TILE_Z` 의 최대값」
  이라고 적는데 그 최대값은 19 다. **손사본은 반드시 낡는다.** 대장 감사에서
  이 세 번째 사본은 등재조차 안 돼 있었다(행은 둘만 들었다).

★ **이 검사는 셋을 합치지 않는다.** 파이썬 둘과 JS 하나라 합칠 수가 없다 —
  **같은지를 강제한다.** 값을 고치는 것은 인스턴스고 이 검사가 족이다.

★ 2026-09-22. 옛 지도(web/js)를 걷어냈다. 읽는 쪽은 이제 관제 화면
  `web/navi/src/components/OpsMap.tsx` 의 ortho 소스다. 파일만 바뀌고 물음은 같다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. `OpsMap.tsx` 의 ortho 소스 줌 범위가 `TILE_Z` 와 같은가
    2. `desk_check.Z` 가 `TILE_Z` 의 최대값과 같은가 (주석이 약속하는 것)
    3. 실제로 구운 타일 폴더가 `TILE_Z` 와 같은가 (발행물이 있을 때만)

★ 3 은 **발행물이 있을 때만** 본다. 신선한 클론에도 `web/data/ortho` 는
  커밋돼 있지만, 없으면 건너뛰는 것이 아니라 **건너뛴다고 말한다** —
  조용히 통과하면 그것이 이 저장소가 세는 빈 그물이다.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORTHO = ROOT / "src" / "firelane" / "ortho.py"
MAP_JS = ROOT / "web" / "navi" / "src" / "components" / "OpsMap.tsx"
DESK = ROOT / "tools" / "desk_check.py"
TILES = ROOT / "web" / "data" / "ortho"


def _tile_z() -> tuple[int, ...]:
    """`ortho.py` 의 `TILE_Z` — 굽는 쪽이 정본이다."""
    tree = ast.parse(ORTHO.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and node.targets
                and getattr(node.targets[0], "id", None) == "TILE_Z"):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("`ortho.py` 에서 `TILE_Z` 를 못 찾았다 — 이 검사가 빈 그물이 됐다")


def _map_ortho_zooms() -> tuple[int, int]:
    """관제 화면 `OpsMap.tsx` 의 ortho 소스 `minzoom`·`maxzoom`."""
    src = MAP_JS.read_text(encoding="utf-8")
    m = re.search(r"\bortho\s*:\s*\{", src)
    assert m, "`OpsMap.tsx` 에 ortho 소스 선언이 없다"
    i = m.start()
    # ★ `{...}` 를 정규식으로 닫지 않는다. 타일 URL 이 `{z}/{x}/{y}` 라
    #   비탐욕 매칭이 **그 중괄호에서 먼저 닫힌다.** 2026-09-20 에 그렇게
    #   짰다가 「minzoom/maxzoom 이 없다」로 걸렸다 — 빈 그물 검사가 잡았다.
    body = src[i:i + 320]
    lo = re.search(r"minzoom\s*:\s*(\d+)", body)
    hi = re.search(r"maxzoom\s*:\s*(\d+)", body)
    assert lo and hi, f"ortho 소스에 minzoom/maxzoom 이 없다 — {body[:80]}"
    return int(lo.group(1)), int(hi.group(1))


def test_the_probes_are_not_empty_nets():
    """셋을 다 읽어내는가. 하나라도 못 읽으면 아래가 조용히 통과한다."""
    z = _tile_z()
    assert len(z) >= 2, f"`TILE_Z` 가 {z} 다 — 너무 짧다. 추출기를 의심하라"
    lo, hi = _map_ortho_zooms()
    assert 0 < lo <= hi <= 22, f"OpsMap.tsx 줌이 이상하다 — {lo}..{hi}"
    assert re.search(r"^Z\s*=\s*\d+", DESK.read_text(encoding="utf-8"), re.M), \
        "`desk_check.py` 에서 `Z = ` 를 못 찾았다"


def test_browser_reads_every_zoom_that_is_baked():
    """굽는데 안 읽는 줌이 있는가. **있으면 그 타일은 소비자가 0명이다.**"""
    z = _tile_z()
    lo, hi = _map_ortho_zooms()
    unread = [x for x in z if x > hi or x < lo]
    assert not unread, (
        f"`ortho.py` 가 줌 {sorted(z)} 를 굽는데 `OpsMap.tsx` 는 {lo}..{hi} 만 읽는다.\n"
        f"  안 읽는 줌: {unread}\n"
        "  MapLibre 는 소스 `maxzoom` 위로 타일을 **요청하지 않는다** —\n"
        "  그 줌의 타일은 커밋되고 배포되지만 아무도 안 받는다.\n"
        "  (2026-09-20 실측: z19 1,035장 16.4MB = `web/data` 의 49.7%)\n"
        "  둘 중 하나다 — 읽는 줌을 올리거나, 굽는 줌을 내리고 타일을 지운다.")


def test_desk_check_copy_matches_its_own_comment():
    """`desk_check.Z` 가 스스로 약속한 값과 같은가.

    ★ 주석이 「`ortho.py TILE_Z` 의 최대값」이라고 적는다. 그러면 그래야 한다.
      2026-09-20 에 그것이 18 이었고 실제 최대값은 19 였다 — **주석이 거짓인
      상수**는 다음 사람을 정확히 틀린 방향으로 보낸다.
    """
    src = DESK.read_text(encoding="utf-8")
    m = re.search(r"^Z\s*=\s*(\d+)\s*(#.*)?$", src, re.M)
    assert m, "`desk_check.py` 의 `Z = ` 를 못 찾았다"
    got, note = int(m.group(1)), (m.group(2) or "")
    # ★ 2026-09-20. 여기 `if "TILE_Z" not in note: return` 이 있었고
    #   `deadcheck ③`(조용한 통과)이 **그것을 잡았다.** 주석이 사라지면 검사가
    #   조용히 통과하는데, 주석이 사라지는 것 자체가 사본이 풀렸다는 뜻이다.
    #   **약속이 없어지는 것도 결함이다.**
    assert "TILE_Z" in note, (
        f"`desk_check.py` 의 `Z = {got}` 에서 「TILE_Z 의 최대값」이라는 주석이 사라졌다.\n"
        "  그 주석이 이 상수를 `ortho.py` 에 묶는 **유일한 끈**이다.\n"
        "  다른 뜻이 됐으면 이름을 바꾸고 이 검사도 같이 옮겨라.")
    assert got == max(_tile_z()), (
        f"`desk_check.py` 의 `Z = {got}` 인데 주석은 「TILE_Z 의 최대값」이라 적는다.\n"
        f"  실제 최대값은 {max(_tile_z())} 다. 손사본이 낡았다 —\n"
        "  값을 맞추거나, 주석이 약속하는 것을 좁혀라.")


def test_baked_folders_match_the_declaration():
    """실제로 구운 폴더가 선언과 같은가. 발행물이 있을 때만 본다."""
    if not TILES.is_dir():
        # ★ 조용히 통과하지 않는다. 못 봤다는 것을 말한다.
        import pytest
        pytest.skip(f"{TILES} 가 없다 — 굽힌 줌을 실물로 대조하지 못했다")
    baked = sorted(int(d.name) for d in TILES.iterdir()
                   if d.is_dir() and d.name.isdigit())
    assert baked == sorted(_tile_z()), (
        f"구운 폴더 {baked} 와 `TILE_Z` {sorted(_tile_z())} 가 다르다.\n"
        "  선언을 고쳤으면 타일도 다시 굽거나 지워라 — 둘이 갈리면\n"
        "  용량 게이트가 빨개졌을 때 정작 줄일 곳을 못 찾는다.")
