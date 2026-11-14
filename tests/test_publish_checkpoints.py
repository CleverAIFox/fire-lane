#!/usr/bin/env python3
"""
test_publish_checkpoints.py — 소화전 · CCTV 가 **엣지 칸**으로 실리고 「이 경로상 소화전 N개」가 경로 산출 직후 나오는가.  (PLAN #72 · #1)

① 붙이는 규칙 — 거리 안의 엣지 전부에 붙는다(교차점 곁은 여러 엣지) · 아무 데도 안 붙은 점은 빠지고 번호가 다시 매겨진다 · 문턱은 닫힌 경계
② 경로의 수는 **합집합**이다 — 두 엣지가 같은 소화전을 가리켜도 한 번 · 모르는 엣지가 하나라도 있으면 수는 `None`(0 이 아니다) · 빈 경로도 `None`
③ 원천이 없으면 칸이 통째로 `null` 이다(0 으로 안 채운다) · 좌표계가 5186 이 아니면 죽는다
④ 발행물(`web/data/navi_graph.json`) — 엣지마다 `hyd` · `cctv` 칸이 **있고** 번호가 `checkpoints` 안이며 `counts` 가 실물과 같다 · 기하로 다시 재도 같다
⑤ 발행 그래프에서 **실제 최단경로를 뽑은 직후** `route_checkpoints` 가 수를 내고, 그 수가 경로 형상에서 독립으로 잰 수와 같다
⑥ (#1) 사람이 확인한 방향 표의 「적용」 행이 발행 그래프의 `ow` 로 **읽힌다**(좌표로 대조) · 「보류(충돌)」 행은 안 읽힌다 · 「적용」인데 `ow=2` 가 아닌 행은 안 덮되 **센다**

IN    합성 선 · 합성 점 · `web/data/navi_graph.json` · `data/field/oneway_direction_2611.csv`
OUT   통과/실패
PARAM `publish_checkpoints.HYD_SNAP_M` · `seg.params.CCTV_RANGE` · EPS_M(발행 좌표 6자리 반올림의 여유)
밖    **소화전이 작동하는가 · 호스가 실제로 깔리는가는 안 본다**(직선거리) · 화면이 그 한 줄을 띄우는가는 내비(`web/navi`) 시험의 몫이다 ·
      표의 방향이 옳은가는 안 본다(사람이 양방향 대조한 값 — `test_oneway_field.py`) · 경로 비용(역주행 배수)은 `rules.ts` 와 그 시험의 몫이다
"""
from __future__ import annotations

import csv
import heapq
import json
from pathlib import Path

import pytest

pytest.importorskip("geopandas", reason="환경skip(도구) — 레이크 없이도 도는 검사지만 geopandas 가 필요하다")

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from firelane import publish_checkpoints as PC
from firelane import publish_rules as PR

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "web" / "data" / "navi_graph.json"
TABLE = ROOT / "data" / "field" / "oneway_direction_2611.csv"
CRS = "EPSG:5186"
EPS_M = 0.3            # 발행 좌표는 6자리(약 0.11m)로 반올림된다 — 문턱 바로 위 · 아래의 점은 어느 쪽으로도 볼 수 있다

# ── ① 붙이는 규칙 ────────────────────────────────────────────────
A = LineString([(0, 0), (100, 0)])          # 동서
B = LineString([(100, 0), (100, 100)])      # 남북 — (100,0) 에서 A 와 만난다
C = LineString([(0, 500), (100, 500)])      # 멀리 떨어진 길


def test_a_point_by_the_junction_attaches_to_every_edge_within_reach():
    per, kept = PC.attach([A, B, C], [(95, 5)], 15.0)
    assert per == [[0], [0], []] and kept == [(95, 5)], "교차점 곁의 점은 두 엣지에 다 붙는다 — 한쪽에만 붙이면 옆 엣지로 지나가는 경로가 놓친다"


def test_points_no_edge_reaches_are_dropped_and_the_rest_renumbered():
    per, kept = PC.attach([A, C], [(50, 200), (50, 510), (50, 5)], 15.0)
    assert kept == [(50, 510), (50, 5)], "어느 엣지에도 안 붙은 첫 점은 안 싣는다"
    assert per == [[1], [0]], "번호는 실린 점의 자리다 — 원천의 자리(1 · 2)가 아니다"


def test_the_threshold_is_a_closed_bound():
    assert PC.attach([A], [(50, 15.0)], 15.0)[0] == [[0]]
    assert PC.attach([A], [(50, 15.01)], 15.0)[0] == [[]]
    assert PC.attach([], [(0, 0)], 15.0) == ([], []) and PC.attach([A], [], 15.0) == ([[]], [])


def test_rows_at_the_same_spot_are_one_site_and_the_order_is_fixed():
    assert PC.sites([(5.0, 5.0), (1.0, 1.0), (5.02, 5.0), (1.0, 1.0)]) == [(1.0, 1.0), (5.0, 5.0)]


def test_the_hydrant_reach_is_the_one_hose_tier_and_the_cctv_reach_is_not_redeclared():
    from firelane.seg.params import CCTV_RANGE
    assert PC.KINDS["cctv"][1] == CCTV_RANGE, "CCTV 거리의 정본은 seg/params.py 하나다"
    src = (ROOT / "tools" / "hydrant_reach.py").read_text(encoding="utf-8")
    assert f'("1본", {PC.HYD_SNAP_M})' in src, "소화전 거리는 hydrant_reach 의 「1본」 등급과 같은 수다 — 한쪽만 바뀌었다"


# ── ② 경로의 수 ──────────────────────────────────────────────────
EDGES = [{"hyd": [0], "cctv": []}, {"hyd": [0, 1], "cctv": [2]}, {"hyd": [], "cctv": [2]},
         {"hyd": None, "cctv": [3]}, {"cctv": []}]


def test_the_route_count_is_a_union_not_a_sum():
    s = PC.route_checkpoints(EDGES, [0, 1, 2])
    assert (s["hyd"], s["hyd_ids"], s["cctv"], s["cctv_ids"]) == (2, [0, 1], 1, [2]), "합이면 소화전 3 · CCTV 2 로 부푼다"
    assert PC.route_line(s) == "이 경로상 소화전 2개" and PC.route_line(s, "cctv") == "이 경로상 CCTV 1개"


def test_zero_is_said_only_when_every_edge_is_known():
    assert PC.route_checkpoints(EDGES, [2])["hyd"] == 0 and PC.route_line(PC.route_checkpoints(EDGES, [2])) == "이 경로상 소화전 0개"
    for path in ([0, 3], [0, 4], []):          # null 칸 · 칸이 없는 옛 발행물 · 빈 경로
        s = PC.route_checkpoints(EDGES, path)
        assert s["hyd"] is None, f"모르는 엣지가 섞였는데 수를 냈다 — {path}"
        assert PC.route_line(s) == "이 경로상 소화전 수를 모른다", "모르는 것을 0개라고 말하지 않는다"
    assert PC.route_checkpoints(EDGES, [0, 3])["hyd_ids"] == [0] and PC.route_checkpoints(EDGES, [0, 3])["cctv"] == 1


# ── ③ 원천 ───────────────────────────────────────────────────────
def _m(lines):
    return gpd.GeoDataFrame({"geometry": lines}, crs=CRS)


def test_a_missing_source_is_null_not_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "P", tmp_path)
    gpd.GeoDataFrame({"geometry": [Point(50, 5), Point(50, 5), Point(50, 300)]}, crs=CRS).to_file(tmp_path / "hydrant_point_5186.gpkg", driver="GPKG")
    per, pts, stat = PC.checkpoints(_m([A, C]))
    assert per["hyd"] == [[0], []] and pts["hyd"] == [(50.0, 5.0)]
    assert stat["hyd"] == {"src_sites": 2, "sites": 1, "null_edges": 0, "zero_edges": 1}, "같은 자리 두 행은 한 자리다"
    assert per["cctv"] is None and stat["cctv"]["null_edges"] == 2, "원천이 없는 종류는 칸이 통째로 null 이다"


def test_a_source_in_degrees_stops_the_publish(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "P", tmp_path)
    gpd.GeoDataFrame({"geometry": [Point(126.9, 35.1)]}, crs="EPSG:4326").to_file(tmp_path / "hydrant_point_5186.gpkg", driver="GPKG")
    with pytest.raises(SystemExit, match="5186"):
        PC.checkpoints(_m([A]))


# ── ④ 발행물 ─────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def graph():
    return json.loads(GRAPH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def metric(graph):
    """발행 그래프의 엣지 선 · 체크포인트 점을 5186 미터로."""
    tf = Transformer.from_crs(4326, 5186, always_xy=True)
    lines = [LineString([tf.transform(x, y) for x, y in e["coords"]]) for e in graph["edges"]]
    pts = {k: [Point(tf.transform(x, y)) for x, y in graph["checkpoints"][k]] for k in PC.KINDS}
    return lines, pts, tf


def test_every_published_edge_carries_both_cells_and_the_counts_match(graph):
    c, cp = graph["counts"], graph["checkpoints"]
    for kind in PC.KINDS:
        cells = [e[kind] for e in graph["edges"]]          # 칸이 **없으면** KeyError — 0 을 빼고 싣던 옛 결함의 자리다
        assert all(v is None or isinstance(v, list) for v in cells)
        assert c[f"{kind}_null"] == sum(v is None for v in cells) and c[f"{kind}_zero"] == sum(v == [] for v in cells)
        used = {i for v in cells if v for i in v}
        assert used == set(range(len(cp[kind]))) and c[f"{kind}_sites"] == len(cp[kind]), "아무 엣지도 안 가리키는 점이 실렸거나 번호가 범위 밖이다"
        assert c[f"{kind}_src_sites"] >= c[f"{kind}_sites"] > 0, f"`{kind}` 가 하나도 안 붙었다 — 원천을 못 읽었거나 좌표계가 갈렸다"
        assert cp["snap_m"][kind] == PC.KINDS[kind][1]
    assert sum(1 for e in graph["edges"] if e["hyd"]) >= 100, "소화전이 붙은 엣지가 너무 적다 — 붙이는 거리가 줄었거나 원천이 바뀌었다"


def test_the_published_cells_agree_with_the_geometry(graph, metric):
    lines, pts, _ = metric
    for kind, (_, snap) in PC.KINDS.items():
        for j, e in enumerate(graph["edges"]):
            if e[kind] is None:
                continue
            have = set(e[kind])
            for i, p in enumerate(pts[kind]):
                d = lines[j].distance(p) if abs(lines[j].centroid.x - p.x) < 2000 else 1e9
                if d <= snap - EPS_M:
                    assert i in have, f"{kind} {i} 가 엣지 {j} 에서 {d:.1f}m 인데 안 붙었다"
                if d > snap + EPS_M:
                    assert i not in have, f"{kind} {i} 가 엣지 {j} 에서 {d:.1f}m 인데 붙었다"


# ── ⑤ 경로 산출 직후 ─────────────────────────────────────────────
def _shortest(graph, src: int, dst: int | None = None):
    """발행 그래프의 길이 최단경로(다익스트라) — 엣지 번호 열. `dst` 가 없으면 가장 먼 노드까지."""
    adj: dict[int, list[tuple[int, int, float]]] = {}
    for i, e in enumerate(graph["edges"]):
        if e["a"] != e["b"]:
            adj.setdefault(e["a"], []).append((e["b"], i, e["length_m"]))
            adj.setdefault(e["b"], []).append((e["a"], i, e["length_m"]))
    dist, via, pq = {src: 0.0}, {}, [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, i, w in adj.get(u, ()):
            if d + w < dist.get(v, 1e18):
                dist[v], via[v] = d + w, (u, i)
                heapq.heappush(pq, (d + w, v))
    dst = max(dist, key=lambda n: (dist[n], n)) if dst is None else dst
    path = []
    while dst != src:
        dst, i = via[dst]
        path.append(i)
    return path[::-1]


def test_the_hydrant_count_comes_out_right_after_a_route_is_solved(graph, metric):
    lines, pts, _ = metric
    seen_nonzero = 0
    for src in (0, len(graph["nodes"]) // 3, len(graph["nodes"]) // 2):
        if not any(src in (e["a"], e["b"]) for e in graph["edges"]):
            continue
        path = _shortest(graph, src)
        assert len(path) >= 5, "경로가 너무 짧다 — 이 시험이 빈 그물이다"
        s = PC.route_checkpoints(graph["edges"], path)        # ← 경로 산출 직후 — 엣지 번호 열만으로
        route = unary_union([lines[i] for i in path])
        for kind, (_, snap) in PC.KINDS.items():
            lo = sum(1 for p in pts[kind] if route.distance(p) <= snap - EPS_M)
            hi = sum(1 for p in pts[kind] if route.distance(p) <= snap + EPS_M)
            assert lo <= s[kind] <= hi, f"{kind}: 엣지 칸으로 센 {s[kind]} 가 경로 형상에서 잰 {lo}~{hi} 밖이다(출발 노드 {src})"
            assert s[kind] <= sum(len(graph["edges"][i][kind]) for i in path), "합집합이 합보다 클 수 없다"
        assert PC.route_line(s) == f"이 경로상 소화전 {s['hyd']}개"
        seen_nonzero += s["hyd"] > 0
    assert seen_nonzero, "세 경로 모두 소화전 0개 — 칸이 비었거나 시험 경로가 소화전을 피해 간다(빈 그물)"


# ── ⑥ #1 — 방향 표가 발행 그래프에서 읽히는가 ────────────────────
def _table_rows():
    with TABLE.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_applied_table_rows_are_readable_as_ow_in_the_published_graph(graph, metric):
    lines, _, _ = metric
    by = {e["seg_uid"]: (e, lines[i]) for i, e in enumerate(graph["edges"])}
    rows = _table_rows()
    applied = [r for r in rows if r["use"] == "적용"]
    assert applied, "「적용」 행이 0 이면 이 시험이 빈 그물이다"
    for r in applied:
        e, L = by[r["seg_uid"]]
        sign = PR._field_sign(L, r, tol=1.0)       # 발행 좌표는 6자리 반올림 — NODE_TOL 보다 넉넉히 댄다
        assert sign in (1, -1) and e.get("ow") == sign, f"{r['seg_uid']} — 표의 방향 {sign} 이 발행 `ow` {e.get('ow')} 로 안 읽힌다"
    for r in rows:
        if r["use"] == "보류(충돌)":
            assert by[r["seg_uid"]][0].get("ow", 0) == 0, f"{r['seg_uid']} — 보류(충돌) 행이 발행에 방향을 썼다(우선순위는 사람이 정한다 · PLAN #1 (d))"
    c = graph["counts"]
    assert c["oneway_dir_field"] == len(applied), "표가 정한 수가 「적용」 행 수와 다르다 — 낡은 표이거나 안 덮은 행이 있다"
    assert c["oneway_dir_known"] == sum(1 for e in graph["edges"] if e.get("ow") in (1, -1))
    assert c["oneway"] - c["oneway_dir_known"] == sum(c["oneway_nl"].values()) == sum(1 for e in graph["edges"] if e.get("ow") == 2)


def test_an_applied_row_on_a_segment_that_is_not_unknown_is_counted_not_silently_skipped(tmp_path, monkeypatch):
    """사람이 후보 행을 「적용」으로 더했는데 그 구간이 `ow=2` 가 아니면 — 안 덮되(§653) **센다**."""
    monkeypatch.setattr(PR, "P", tmp_path)
    one, two = LineString([(0, 0), (200, 0)]), LineString([(0, 100), (200, 100)])
    gpd.GeoDataFrame({"일방통행": ["일방통행"], "geometry": [one]}, crs=CRS).to_file(tmp_path / "ngii1k_center_5186.gpkg", driver="GPKG")
    t = tmp_path / "t.csv"
    with t.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["seg_uid", "use", "from_x", "from_y", "to_x", "to_y"])
        w.writeheader()
        w.writerow(dict(seg_uid="U1", use="적용", from_x=0, from_y=0, to_x=200, to_y=0))
        w.writerow(dict(seg_uid="U2", use="적용", from_x=0, from_y=100, to_x=200, to_y=100))      # U2 는 일방통행 표지가 없다(ow=0)
        w.writerow(dict(seg_uid="U2", use="보류(충돌)", from_x=0, from_y=100, to_x=200, to_y=100))
    out, s = PR.oneway(gpd.GeoDataFrame({"seg_uid": ["U1", "U2"], "geometry": [one, two]}, crs=CRS), field_path=t)
    assert out == [1, 0], "양방향(0)은 표가 안 덮는다"
    assert (s["dir_field"], s["dir_field_refused"]) == (1, 1), f"안 덮은 「적용」 행을 안 셌다 — {s}"
