#!/usr/bin/env python3
"""
test_reach_overlay.py — 도달 불가 오버레이가 **실제로 무엇을 그리는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-16. `route_vehicle.json` 은 발행만 되고 지도가 안 읽었다. 1,101 구간 중
413 이 거점에서 차량 경로로 닿지 않는데 화면에 없었다(DECISIONS §166).

★ 오버레이는 조용히 틀린다. 조인 키가 어긋나면 `reachable` 이 전부 null 이 되고
  점선이 **하나도 안 그려지는데** 부팅은 멀쩡하다. 그래서 키 정합과 "0 이 아닌 수" 를
  둘 다 본다. 빗나간 조인을 0 으로 채우면 반대로 거짓 경고가 그려진다 — 그것도 본다.

★ 2026-09-22. 옛 지도(web/js/reach.js · main.js)를 걷어냈다. 그 조인을 node 로 돌리던 시험과
  배선 시험은 대상이 사라져 지웠다. 조인은 이제 관제 화면(web/navi)이 하고 그쪽 vitest 가 든다.
  여기 남는 둘은 **발행물** 쪽 — 키가 일대일인가 · 그릴 것이 있는가 — 이라 소비자와 무관하다.
"""
from __future__ import annotations

import json
from pathlib import Path

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
