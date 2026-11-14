"""
test_firstscreen.py — 첫 화면 gzip 전송량 래칫이 **경계에서** 우는가.  (DECISIONS §787-H · PLAN #245)

IN    tools/firstscreen.py (순수 함수 `summarize` · `verdict`)
OUT   없음
밖    **브라우저를 안 띄운다** — 실측은 CI 의 `contract-smoke` 와 `verify.sh` 가 돈다(`gatefast` 층표: ci).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("firstscreen_t", ROOT / "tools" / "firstscreen.py")
FS = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = FS
spec.loader.exec_module(FS)


def test_both_views_are_declared():
    assert set(FS.FIRST_SCREEN_KB) == set(FS.VIEWS) == {"navi", "ops"}
    assert all(v > 0 for v in FS.FIRST_SCREEN_KB.values()), "안 적은 래칫은 래칫이 아니다"


def test_verdict_bites_only_above_the_declaration():
    d = {"navi": 100, "ops": 100}
    assert FS.verdict("navi", 100, d) == [], "선언과 같은데 운다 — 래칫은 「늘지 않는다」다"
    assert FS.verdict("navi", 0, d) == [], "줄었는데 운다"
    assert len(FS.verdict("navi", 100.5, d)) == 1, "경계에서 안 문다"
    assert len(FS.verdict("ops", 1, {"navi": 100})) == 1, "선언이 없는 화면을 통과시킨다"


def test_tiles_are_reported_but_not_gated():
    log = [{"p": "/fire-lane/data/ortho/19/1/1.jpg", "wire": 10240, "t0": 0, "t1": 1},
           {"p": "/fire-lane/data/terrain/15/1/1.png", "wire": 10240, "t0": 0, "t1": 1},
           {"p": "/fire-lane/data/buildings.geojson", "wire": 1024, "t0": 0, "t1": 2}]
    s = FS.summarize(log)
    assert s["gated_kb"] == 1.0 and s["tiles_kb"] == 20.0 and s["total_kb"] == 21.0
    assert s["buildings_kb"] == 1.0 and s["sources_done_s"] == 2
