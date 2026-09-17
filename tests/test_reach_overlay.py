#!/usr/bin/env python3
"""
test_reach_overlay.py — 도달 불가 오버레이가 **실제로 무엇을 그리는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-16. `route_vehicle.json` 은 발행만 되고 지도가 안 읽었다. 1,101 구간 중
413 이 거점에서 차량 경로로 닿지 않는데 화면에 없었다(DECISIONS §166).

★ 오버레이는 조용히 틀린다. 조인 키가 어긋나면 `reachable` 이 전부 null 이 되고
  점선이 **하나도 안 그려지는데** 부팅은 멀쩡하다. 그래서 키 정합과 "0 이 아닌 수" 를
  둘 다 본다. 빗나간 조인을 0 으로 채우면 반대로 거짓 경고가 그려진다 — 그것도 본다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "web"


def _load():
    seg = json.loads((W / "data/segments.geojson").read_text(encoding="utf-8"))
    route = json.loads((W / "data/route_vehicle.json").read_text(encoding="utf-8"))
    return seg, route


def test_join_key_is_one_to_one():
    seg, route = _load()
    uids = [f["properties"]["seg_uid"] for f in seg["features"]]
    assert len(uids) == len(set(uids)), "segments.geojson 의 seg_uid 가 겹친다"
    miss = sorted(set(uids) - set(route))
    extra = sorted(set(route) - set(uids))
    assert not miss, f"route_vehicle 에 없는 구간 {len(miss)}: {miss[:5]} — 오버레이가 조용히 빠진다"
    assert not extra, f"segments 에 없는 route 키 {len(extra)}: {extra[:5]}"
    bad = [k for k, v in route.items() if v.get("reachable") not in (0, 1)]
    assert not bad, f"reachable 이 0/1 이 아니다: {bad[:5]}"


def test_overlay_has_something_to_draw():
    """★ 카나리아. 도달 불가가 0 이면 점선 레이어는 살아 있어도 아무것도 안 그린다."""
    _, route = _load()
    n = sum(1 for v in route.values() if v["reachable"] == 0)
    assert 0 < n < len(route), f"도달 불가 {n}/{len(route)} — 0 이면 오버레이가 죽은 것이다"


@pytest.mark.skipif(shutil.which("node") is None, reason="환경skip(도구) — node 없음")
def test_join_leaves_unmatched_as_null_not_zero(tmp_path):
    """빗나간 조인을 0 으로 채우면 '도달 불가' 거짓 점선이 그려진다."""
    probe = tmp_path / "probe.mjs"
    probe.write_text(
        f'import {{ joinReach }} from "{(W / "js/reach.js").as_uri()}";\n'
        'const fs = [{properties:{seg_uid:"A"}},{properties:{seg_uid:"B"}},'
        '{properties:{seg_uid:"C"}},{properties:{seg_uid:"D"}}];\n'
        'const r = joinReach(fs, {A:{reachable:0}, B:{reachable:1}, D:{reachable:7}});\n'
        'console.log(JSON.stringify({r, p: fs.map(f => f.properties.reachable)}));\n',
        encoding="utf-8")
    out = subprocess.run(["node", str(probe)], capture_output=True, text=True, check=True).stdout
    got = json.loads(out)
    assert got["p"] == [0, 1, None, None], got
    assert got["r"] == {"unreach": 1, "missing": 2, "total": 4}, got


def test_overlay_is_wired():
    main = (W / "js/main.js").read_text(encoding="utf-8")
    assert "joinReach(D.segments.features, D.route)" in main
    assert "addUnreachable();" in main
    boot = (ROOT / "tools/web_boot_check.mjs").read_text(encoding="utf-8")
    assert '"seg-unreach"' in boot, "부팅 스모크가 오버레이 레이어를 필수로 안 본다"
