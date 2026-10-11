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
        pytest.skip(f"환경skip(산출물) — {TILES} 가 없다. 굽힌 줌을 실물로 못 댔다")
    baked = sorted(int(d.name) for d in TILES.iterdir()
                   if d.is_dir() and d.name.isdigit())
    assert baked == sorted(_tile_z()), (
        f"구운 폴더 {baked} 와 `TILE_Z` {sorted(_tile_z())} 가 다르다.\n"
        "  선언을 고쳤으면 타일도 다시 굽거나 지워라 — 둘이 갈리면\n"
        "  용량 게이트가 빨개졌을 때 정작 줄일 곳을 못 찾는다.")


# ── 2026-10-12 (DECISIONS §490) ────────────────────────────────────
#   §489 가 분모를 바로잡은 뒤 이 파일이 빚에 남았다. 줌 **수**가 갈리는가는
#   밀면서, 그 줌으로 **픽셀을 내는 식 둘**(`deg2px` · `mpp`)을 민 자리가
#   없었다 — 수가 맞아도 식이 틀리면 책상검사 그림의 축척이 거짓이 된다.

def _desk():
    """`tools/desk_check.py` 를 모듈로 들인다. **그림을 안 굽는다.**"""
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location(
        "_desk_probe", ROOT / "tools" / "desk_check.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def test_the_pixel_projection_matches_the_web_mercator_definition():
    """★ 아는 값으로 민다 — z0 에서 세계가 타일 한 장이고 원점이 그 가운데다."""
    d = _desk()
    assert d.deg2px(0, 0, 0) == (d.TILE / 2, d.TILE / 2)
    assert d.deg2px(180, 0, 0)[0] == float(d.TILE)
    assert d.deg2px(-180, 0, 0)[0] == 0.0
    # 줌이 하나 오르면 픽셀이 두 배다
    assert d.deg2px(90, 0, 1)[0] == 2 * d.deg2px(90, 0, 0)[0]


def test_the_metres_per_pixel_halves_each_zoom():
    d = _desk()
    assert abs(d.mpp(0, 0) - 156543.03392) < 1e-6
    for z in range(15, 20):
        assert abs(d.mpp(35.151, z + 1) * 2 - d.mpp(35.151, z)) < 1e-9, z
    # 위도가 높아지면 한 픽셀이 덮는 거리가 줄어든다
    assert d.mpp(60, 19) < d.mpp(35.151, 19) < d.mpp(0, 19)


def test_the_two_formulas_agree_on_a_hundred_metres():
    """★ **같은 것을 두 식이 말한다.** 어긋나면 그림의 축척이 거짓이 된다 —
    `stitch` 는 `deg2px` 로 자르고, 눈금은 `mpp` 로 적는다."""
    import math
    d = _desk()
    lat = 35.151
    dlon = 100.0 / (111_320 * math.cos(math.radians(lat)))
    x0, _ = d.deg2px(126.9266, lat, d.Z)
    x1, _ = d.deg2px(126.9266 + dlon, lat, d.Z)
    by_px = x1 - x0
    by_mpp = 100.0 / d.mpp(lat, d.Z)
    # 두 식의 차가 0.01% 안이다 — 그 밖이면 한쪽이 다른 반지름을 쓴다
    assert abs(by_px - by_mpp) / by_mpp < 1e-4, (by_px, by_mpp)


def test_the_pad_is_a_distance_not_a_pixel_count():
    """★ 여백이 **미터**다. 픽셀로 적으면 줌을 바꾼 날 여백이 따라 변한다."""
    d = _desk()
    assert d.PAD_M > 0
    # 그 미터가 지금 줌에서 백 픽셀 단위로 나온다 — 0 픽셀이면 여백이 없다
    assert d.PAD_M / d.mpp(35.151, d.Z) > 1


# ── 지형 업샘플 — 시험이 이름을 안 부르고 있었다 (§495) ───────
# ★ `terrain.upsample` 은 **DEM 을 타일 격자에 올리는 자**다. 색인이 한 칸
#   밀리면 음영기복이 그만큼 밀리고, 밀린 음영은 **그럴듯해 보인다** —
#   언덕이 거기 있나 없나를 눈으로 아는 사람이 없다.
#   `tools/srccov.py` 가 「시험이 이름으로도 안 부른다」로 셌다(§493).
def test_upsample_keeps_the_corner_values():
    """★ 본체. 네 꼭짓값은 **그대로** 남는다 — 이중선형의 정의다."""
    import numpy as np

    from firelane.terrain import upsample

    a = np.array([[0.0, 1.0], [2.0, 3.0]])
    u = upsample(a, 2)
    assert u.shape == (4, 4), u.shape
    assert u[0, 0] == 0.0 and u[0, -1] == 1.0
    assert u[-1, 0] == 2.0 and u[-1, -1] == 3.0


def test_upsample_by_one_is_the_array_itself():
    """★ k=1 이 항등이다. 아니면 1배로 부르는 자리가 조용히 값을 바꾼다."""
    import numpy as np

    from firelane.terrain import upsample

    a = np.array([[0.0, 1.0], [2.0, 3.0]])
    assert np.array_equal(upsample(a, 1), a)


def test_upsample_of_a_ramp_stays_a_ramp():
    """★ 선형 입력은 **선형**으로 나온다 — 계단이 남으면 보간이 안 된 것이다."""
    import numpy as np

    from firelane.terrain import upsample

    u = upsample(np.arange(4, dtype=float).reshape(1, 4), 2)[0]
    d = np.diff(u)
    assert np.allclose(d, d[0]), u
    assert u[0] == 0.0 and u[-1] == 3.0


def test_upsample_never_invents_a_value_outside_the_input_range():
    """★ 지형 고도가 입력 범위를 넘으면 **없는 언덕**이 생긴다."""
    import numpy as np

    rng = np.random.default_rng(0)
    from firelane.terrain import upsample

    a = rng.normal(size=(7, 5)) * 30
    u = upsample(a, 4)
    assert u.min() >= a.min() - 1e-9 and u.max() <= a.max() + 1e-9
    assert u.shape == (28, 20)


def test_upsample_of_a_flat_field_is_flat():
    """★ 음성 — 평지에 기복을 만들지 않는다."""
    import numpy as np

    from firelane.terrain import upsample

    a = np.full((5, 6), 42.0)
    assert np.allclose(upsample(a, 3), 42.0)
