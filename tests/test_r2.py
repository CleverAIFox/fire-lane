"""R2 — 옛 구간 → 새 구간 전이표. 합성 기하(EPSG:5186 미터). (DECISIONS §187)"""
from __future__ import annotations

import geopandas as gpd
from shapely.geometry import LineString

from firelane import transition as X


def gdf(lines, **cols):
    return gpd.GeoDataFrame(cols, geometry=lines, crs=5186)


def segs(lines, uids, verdicts=None, roads=None):
    n = len(lines)
    return gdf(lines, seg_uid=uids,
               verdict=verdicts or ["clear"] * n,
               road_name=roads or ["가길"] * n)


A = LineString([(0, 0), (100, 0)])
B = LineString([(100, 0), (100, 80)])
C = LineString([(300, 0), (360, 0)])


def test_identity_is_all_one_to_one():
    """같은 산출물끼리는 전부 1:1 · 소멸 0 · 신설 0. 이게 깨지면 R3 전후 비교에 못 쓴다."""
    a = segs([A, B, C], ["A", "B", "C"], ["clear", "blocked", "unknown"])
    t = X.build(a, a)
    s = X.summarize(t, 3, 3)
    assert s["cardinality"] == {"1:1": 3} and s["gone"] == 0 and s["added"] == 0
    assert s["same_uid"] == 3 and s["len_matched_m"] == s["len_old_m"]


def test_shared_node_does_not_leak_a_vote_to_the_neighbour():
    """★ 끝점 카나리아 — 표본이 칸 **가운데**여야 한다(transition.shares).

    이어지는 두 구간은 노드를 공유한다. 양끝을 찍으면 거리 0 · 방향 0 이라 이웃이 한 표를 받고,
    같은 산출물끼리 대조해도 1:1 이 깨진다 — 2026-09-18 실측에서 1,281 중 348 이 그 모양이었다.
    """
    a1, a2 = LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)])
    a = segs([a1, a2], ["A1", "A2"], ["clear", "blocked"])
    t = X.build(a, a)
    assert X.summarize(t, 2, 2)["cardinality"] == {"1:1": 2}
    assert set(t.loc[t.old_uid == "A1", "new_uid"]) == {"A1"}, "끝 표본이 이웃 구간으로 샜다"
    # 3m 짜리 토막에서도 — 짧을수록 한 표의 비중이 커서 MIN_SHARE 로는 못 거른다
    b1, b2 = LineString([(0, 0), (3, 0)]), LineString([(3, 0), (6, 0)])
    b = segs([b1, b2], ["B1", "B2"])
    assert X.summarize(X.build(b, b), 2, 2)["cardinality"] == {"1:1": 2}


def test_split_is_one_to_n_and_conserves_length():
    old = segs([A], ["A"], ["clear"])
    new = segs([LineString([(0, 0), (40, 0)]), LineString([(40, 0), (100, 0)])],
               ["A1", "A2"], ["clear", "needs_cv"])
    t = X.build(old, new)
    assert X.cardinality(t).to_dict() == {"A": "1:N"}
    assert abs(t.share.sum() - 1.0) < 0.05
    assert abs(t.len_share_m.sum() - 100.0) < 5.0
    f = X.verdict_flow(t)
    assert f.loc["clear", "clear"] > 30 and f.loc["clear", "needs_cv"] > 50, f.to_string()
    assert abs(f.loc["clear"].sum() - 100) <= 2, "판정 전이가 옛 총연장을 안 지킨다"


def test_merge_is_n_to_one_and_disappearance_is_counted():
    old = segs([LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)]), C],
               ["A1", "A2", "C"], ["clear", "needs_cv", "blocked"])
    new = segs([A], ["M"], ["clear"])
    t = X.build(old, new)
    card = X.cardinality(t).to_dict()
    assert card["A1"] == "N:1" and card["A2"] == "N:1" and card["C"] == "소멸"
    assert X.summarize(t, 3, 1)["gone"] == 1
    assert X.verdict_flow(t).loc["blocked", "소멸"] == 60


def test_new_segment_with_no_old_counterpart_is_added():
    t = X.build(segs([A], ["A"]), segs([A, C], ["A", "NEW"]))
    assert X.summarize(t, 1, 2)["added"] == 1
    assert set(t.loc[t.match == "신설", "new_uid"]) == {"NEW"}


def test_midpoint_fallback_only_when_direction_match_fails():
    """방향이 어긋나 표가 0 이면 중점 최근접 15m 로 한 번 더 본다. 붙었다는 증거가 약하므로 칸에 적는다."""
    old = segs([A], ["A"], ["clear"])
    crossing = segs([LineString([(50, -30), (50, 30)])], ["X"], ["blocked"])
    t = X.build(old, crossing)
    assert t.iloc[0]["match"] == "중점" and t.iloc[0]["new_uid"] == "X"
    far = segs([LineString([(50, -300), (50, -240)])], ["F"], ["blocked"])
    assert X.build(old, far).iloc[0]["match"] == "소멸", "15m 밖을 중점 폴백으로 붙였다"


def test_transition_is_not_wired_into_judgment_code():
    """전이표는 조사 도구다 — 판정 코드가 import 하면 지문이 흔들린다(§187 · §184-5 와 같은 규칙)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("src/firelane/segments.py", "src/firelane/seg/width.py",
                "src/firelane/seg/report.py", "src/firelane/seg/params.py"):
        assert "transition" not in (root / rel).read_text(encoding="utf-8"), f"{rel} 가 transition 을 참조한다"
