"""
test_themecheck.py — 「화면에서 구분된다」를 무는 검사가 **실제로 우는가**.  (DECISIONS §775)

IN    tools/themecheck.py · 합성 입력 · 변경 전 소스(`git show`)
밖    색이 예쁜가는 안 본다. WebGL 렌더는 브라우저 스모크 소관이다.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("themecheck_t", ROOT / "tools" / "themecheck.py")
TC = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = TC
_spec.loader.exec_module(TC)

BG = "rgb(232,228,218)"
OK_LAND = {k: "#c8d9b9" for k in TC.LAND_KEYS}
VERDICT = {"clear": "rgb(74,209,143)", "needs_cv": "rgb(255,171,46)", "blocked": "rgb(255,77,61)", "unknown": "rgb(90,98,114)"}


def test_the_tool_passes_its_own_selftest():
    assert TC.selftest() == 0


def test_the_real_tree_is_quiet():
    assert TC.faults() == []


def test_land_equal_to_background_cries_in_both_themes():
    assert TC.land_faults("밝", BG, dict(OK_LAND, landDaeji=BG), 6)
    assert TC.land_faults("어두", "#0b1220", dict(OK_LAND, landGreen="#0b1220"), 6)


def test_a_land_that_kills_the_verdict_cries():
    near = {k: "#ffb43a" for k in TC.LAND_KEYS}      # 주황 판정과 휘도가 같다
    assert TC.verdict_faults("밝", BG, near, VERDICT, TC.VERDICT_RETAIN_PCT)


def test_one_theme_missing_a_class_cries():
    assert TC.land_faults("어두", "#0b1220", {k: "#182235" for k in TC.LAND_KEYS if k != "landFarm"}, 6)


def test_ops_without_the_land_layers_cries():
    assert TC.wiring_faults("")


def test_an_undeclared_label_layer_cries_and_a_declared_one_does_not():
    assert TC.role_faults({"lbl-new"}, set(TC.ROLES), TC.ROLES)
    assert not TC.role_faults({"lbl-road"}, {"lbl-bldg", "lbl-poi"}, TC.ROLES)


def test_the_defect_of_2026_11_13_would_have_been_caught():
    """고치기 전 소스에서 밝은 화면의 바탕 면 넷이 구분 안 되고, 관제에는 층이 없었다 — 이 검사가 그때 있었다면 울었다."""
    def show(path: str) -> str:
        r = subprocess.run(["git", "show", f"16c6a5a9^:{path}"], capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=30)
        return r.stdout
    tk, ops = show("web/navi/src/ui/tokens.ts"), show("web/navi/src/components/OpsMap.tsx")
    if not tk or not ops:                          # 얕은 클론 — 못 읽으면 못 쟀다고 말하고 건너뛴다(조용히 통과하지 않는다)
        import pytest
        pytest.skip("환경skip(산출물) — 16c6a5a9^ 가 없다(얕은 클론 · git 이력이 없어 결함 전 소스를 못 읽는다)")
    bg, land = TC.light_palette(tk)
    assert len(TC.land_faults("밝", bg, land, TC.LAND_DE_MIN)) >= 3
    assert TC.wiring_faults(ops)


def test_a_land_stacked_above_buildings_or_extruded_cries():
    ids = ["bg", "sidewalk", "road-area", "bldg"]
    assert not TC.stack_faults(ids, "bg", ["fill", "line"])
    assert TC.stack_faults(ids, "bldg", ["fill"]), "바탕 면을 건물 위에 놓았는데 안 운다"
    assert TC.stack_faults(ids, "bg", ["fill-extrusion"]), "바탕 면이 3D 돌출인데 안 운다"


def test_the_real_land_sits_right_after_the_background():
    base, after, types = TC.land_stack()
    assert after == "bg" and base[0] == "bg" and not TC.stack_faults(base, after, types)


def test_the_dark_floor_is_declared_apart_from_the_light_one():
    assert TC.LAND_DE_MIN_DARK > TC.LAND_DE_MIN, "어두운 화면 하한이 밝은 화면보다 높아야 한다(같은 ΔE 가 어두운 바탕에서 덜 보인다)"
