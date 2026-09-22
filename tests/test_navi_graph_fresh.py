#!/usr/bin/env python3
"""
test_navi_graph_fresh.py — 내비 그래프가 **지금 판정과 같은 구간**을 싣는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-16. `publish_navi` 를 부르는 곳이 없었다. 흡수-2 전량으로 판정이 1,101 → 1,281 이 됐는데
`navi_graph.json` 은 엣지 1,101 그대로였다. 부팅 스모크 · 타입 검사 · golden 이 전부 초록이었다 —
그래프가 **옛 것인지**는 아무도 대조하지 않았다. 내비는 옛 구간으로 경로를 짰다(DECISIONS §170-5).

★ 둘을 본다 — ① 커밋된 그래프의 seg_uid 집합이 커밋된 판정과 같은가(낡음)
  ② publish 가 publish_navi 를 부르는가(배선). ①만 보면 손으로 한 번 맞춰 두면 다시 낡는다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"


def _uids(p: Path, key: str) -> set[str]:
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = d["features"] if key == "features" else d["edges"]
    return {(r["properties"] if key == "features" else r)["seg_uid"] for r in rows}


def test_navi_graph_matches_published_segments():
    seg, nav = _uids(WEB / "segments.geojson", "features"), _uids(WEB / "navi_graph.json", "edges")
    assert seg == nav, (
        f"navi_graph.json 이 판정과 다른 구간을 싣는다 — 판정 {len(seg)} · 내비 {len(nav)} · "
        f"내비에만 {len(nav - seg)} · 판정에만 {len(seg - nav)}\n"
        "  uv run fire-lane --from publish  로 다시 낸다. 내비가 옛 구간으로 경로를 짠다.")


def test_publish_calls_publish_navi():
    src = (ROOT / "src" / "firelane" / "publish_web.py").read_text(encoding="utf-8")
    assert "publish_navi" in src and "_navi.main()" in src, (
        "publish_web 이 publish_navi 를 안 부른다 — 파이프라인이 내비 그래프를 다시 안 낸다(§170-5).")


def test_navi_graph_carries_traffic_rules():
    """일방통행 · 회전 금지가 실렸고 모양이 맞는가 (DECISIONS §215-1).

    ★ 2026-09-22. 그래프가 모든 구간을 양방향으로 실어 내비가 역주행 경로를 아무 말 없이
      냈다. 규칙이 **빠진 채** 다시 발행돼도 부팅 · 타입 · golden 은 초록이다 — 여기서 센다.
    """
    g = json.loads((WEB / "navi_graph.json").read_text(encoding="utf-8"))
    ow = [e.get("ow", 0) for e in g["edges"]]
    assert set(ow) <= {0, 1, -1, 2}, f"ow 에 모르는 값 {sorted(set(ow) - {0, 1, -1, 2})}"
    n_ow = sum(1 for x in ow if x)
    assert n_ow == g["counts"]["oneway"], "counts.oneway 가 실물과 다르다"
    assert n_ow >= 20, f"일방통행 {n_ow}구간 — 입력(ngii1k_center)을 못 읽었거나 대조가 죽었다"
    turns = g.get("turns", [])
    assert turns, "회전 금지 0건 — TURNINFO ↔ 그래프 대응이 죽었다"
    for i, n, o, t in turns:
        ei, eo = g["edges"][i], g["edges"][o]
        assert n in (ei["a"], ei["b"]) and n in (eo["a"], eo["b"]), f"회전 금지 {i},{n},{o} 가 노드에 안 닿는다"
        assert t in (3, 101, 102, 103), f"금지가 아닌 TURN_TYPE {t} 가 실렸다 — 허용 규칙은 안 싣는다"
