"""2차 경로가 **막힌 길을 안 쓰는가** — 소스 문자열이 아니라 산출물로 본다.

★ 2026-09-25 (PLAN §1 #127 · DECISIONS §250). 종전 강제자는
  `tests/test_guards.py` 에서 `segments.py` 를 **글자로 읽고** 넷을 찾았다 —

      "P.remove_edges_from" in body
      'd["blocked"]]' in body
      "reachable" in body
      'd["a"] in reach and d["b"] in reach' in body

  그것은 검사가 아니라 **표절 대조**다. 지역변수 `P` 를 `G` 로 바꾸면 빨개지고
  (행동은 그대로인데), 부등호를 뒤집거나 `and` 를 `or` 로 바꿔도 초록이다
  (행동이 뒤집혔는데). 이 저장소가 반복해 배운 형태의 극단이다 —
  **선언이 검사보다 넓으면 거짓 초록이 된다**(§243).

  이음매가 없어서 그랬다. `_write_route` 가 `PROCESSED` 에 직접 썼으므로
  시험이 결과를 볼 방법이 없었다. `dst` 인자 하나로 그것이 열린다.

★ 이 함수가 무엇을 지켜야 하는가 — 2026-08-24 실측이 정한 것이다.
  처음엔 막힌 엣지에 `BIG` 을 주고 그래프에 남겼고, 그러면 **다른 길이 없을 때
  Dijkstra 가 그것을 쓴다.** 통행 불가 416인데 경로에 996구간이 쓰이는 결과가
  나왔다. 「막힌 길로라도 도달」은 답이 아니다.

IN    합성 GeoDataFrame (레이크 불필요) · `sources.yaml`(차량 제원)
OUT   tmp_path 의 CSV
PARAM 없음
밖    ① 0.02m 접합 사고(2026-08-24)는 **여기서 못 본다.** 시험을 써 보고 지웠다 —
         안전센터가 둘이라 합성 그래프에서 지산이 **떨어져 나간 쪽에 직접 붙는다.**
         그러면 노드가 갈려도 `reachable` 이 1 이라 늘 초록이다. 거짓 초록을
         남기느니 없는 편이 낫다. 그 경계는
         `tests/test_snap_groups.py::test_a_two_centimetre_gap_still_joins` 가 든다.
      ② 경로가 **최적인지**는 안 본다 — 그것은 비용함수(`vehicle.edge_cost`)가
      정하고 `PLAN §1 #2` 가 든다. 여기서 보는 것은 「막힌 길을 쓰는가」와
      「못 가는 곳을 갈 수 있다고 하는가」 둘이다. 둘 다 **미탐 방향**이라
      소방차를 잘못 보낸다.
"""
from __future__ import annotations

import csv
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from firelane import segments
from firelane.seg import graph as seg_graph

ROOT = Path(__file__).resolve().parent.parent

CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"


def _station_xy() -> tuple[float, float]:
    """대인119안전센터를 5186 으로. 합성 길을 **안전센터 옆에** 놓아야 닿는다."""
    lon, lat = seg_graph.STATIONS["대인119안전센터"]
    p = gpd.GeoSeries([Point(lon, lat)], crs=CRS_W).to_crs(CRS_M).iloc[0]
    return p.x, p.y


def _seg(uid: str, sid: str, x0, y0, x1, y1, *, w, verdict) -> dict:
    return {
        "seg_uid": uid, "seg_id": sid,
        "length_m": round(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 3),
        "width_min_m": w, "verdict": verdict,
        "geometry": LineString([(x0, y0), (x1, y1)]),
    }


@pytest.fixture
def lane(tmp_path) -> dict[str, dict]:
    """합성 길. 안전센터에서 뻗은 사슬 하나 + 막힌 가지 + 떨어진 섬.

          station ──A── n1 ──B── n2          A · B  통행 가능
                            └──C── n3        C      막힘 (폭 0.4m)
          (멀리)     n8 ──D── n9             D      섬 — 어디서도 못 닿는다
    """
    sx, sy = _station_xy()
    rows = [
        _seg("U-A", "S-A", sx, sy, sx + 40, sy, w=6.0, verdict="clear"),
        _seg("U-B", "S-B", sx + 40, sy, sx + 80, sy, w=6.0, verdict="clear"),
        _seg("U-C", "S-C", sx + 40, sy, sx + 40, sy + 40, w=0.4, verdict="blocked"),
        _seg("U-D", "S-D", sx + 9000, sy + 9000, sx + 9040, sy + 9000,
             w=6.0, verdict="clear"),
    ]
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs=5186)
    dst = tmp_path / "route_vehicle.csv"
    segments._write_route(g, dst)
    assert dst.exists(), "산출물이 아예 안 나왔다 — 차량 제원을 못 읽었을 수 있다"
    with dst.open(encoding="utf-8-sig") as f:
        return {r["seg_uid"]: r for r in csv.DictReader(f)}


# ── 막힌 길 ─────────────────────────────────────────────────────
def test_a_blocked_edge_is_never_used_by_a_route(lane):
    """**막힌 구간을 경로가 지나가지 않는다.** 2026-08-24 의 사고가 이것이다."""
    assert lane["U-C"]["passable"] == "0", "폭 0.4m 인데 통행 가능으로 낸다"
    assert lane["U-C"]["route_vehicle"] == "0", (
        "막힌 구간이 경로에 쓰였다 — 그래프에서 **빼지 않고** 큰 비용만 준 것이다.\n"
        "  다른 길이 없으면 Dijkstra 가 그것을 고른다. 「막힌 길로라도 도달」은\n"
        "  답이 아니다 — 못 가면 못 간다고 해야 소방차를 안 보낸다.")


def test_the_open_chain_is_actually_used(lane):
    """카나리아 — 전부 0이면 위 검사가 **아무것도 증명하지 않는다.**"""
    used = sum(int(r["route_vehicle"]) for r in lane.values())
    assert used > 0, (
        f"어느 구간도 경로에 안 쓰였다(합 {used}) — 그래프가 안 섰거나 안전센터가\n"
        "  합성 길에서 멀다. 이 상태에서는 막힘 검사가 늘 초록이다.")
    assert int(lane["U-A"]["route_vehicle"]) > 0, "안전센터에 붙은 구간이 안 쓰였다"


# ── 도달 ────────────────────────────────────────────────────────
def test_an_edge_with_one_unreachable_end_is_not_reachable(lane):
    """**한쪽 끝만 닿으면 그 구간에는 못 들어간다.**

    `U-C` 의 한 끝(n1)은 안전센터에서 닿고 다른 끝(n3)은 안 닿는다 — 자기 자신이
    막혀 있으므로. `and` 를 `or` 로 바꾸면 여기서 운다. 종전 문자열 단언은
    그 한 글자를 못 봤다.
    """
    assert lane["U-C"]["reachable"] == "0", (
        "한쪽 끝만 닿는 구간을 도달 가능으로 낸다 — `and` 가 `or` 가 됐는지 봐라.\n"
        "  그 구간에 들어가려면 **양쪽 끝**이 다 닿아야 한다.")


def test_a_disconnected_island_is_not_reachable(lane):
    """떨어진 섬은 도달 불가다. 스스로는 멀쩡해도 갈 길이 없다."""
    assert lane["U-D"]["passable"] == "1", "섬 자체는 통행 가능해야 한다(폭 6m)"
    assert lane["U-D"]["reachable"] == "0", (
        "안전센터와 9km 떨어져 이어지지 않은 구간을 도달 가능으로 낸다.")
    assert lane["U-D"]["route_vehicle"] == "0", "닿지도 않는 구간이 경로에 쓰였다"


def test_the_reachable_chain_is_reachable(lane):
    """카나리아 — 전부 0이면 위 둘이 **거짓 초록**이다."""
    assert lane["U-A"]["reachable"] == "1", (
        "안전센터에 직접 붙은 구간이 도달 불가로 나온다 — 도달 판정이 통째로 죽었다.")
    assert lane["U-B"]["reachable"] == "1", "한 칸 건너도 닿아야 한다"


# ── 계약 ────────────────────────────────────────────────────────
def test_the_columns_are_what_the_consumers_read(lane):
    """칸 이름이 바뀌면 읽는 쪽이 조용히 빈 값을 먹는다."""
    want = {"seg_uid", "seg_id", "route_vehicle", "cost", "passable", "reachable"}
    got = set(next(iter(lane.values())))
    assert got == want, f"칸이 달라졌다\n  났다 {sorted(got)}\n  기대 {sorted(want)}"


def test_the_seam_does_not_leak_into_the_real_output(tmp_path):
    """이음매가 **기본값에서는** 종전 자리를 그대로 쓰는가.

    ★ `dst` 를 안 넘기면 `PROCESSED / "route_vehicle.csv"` 여야 한다. 기본값이
      바뀌면 파이프라인이 엉뚱한 데 쓰고 `publish` 가 지난 실행 것을 읽는다.
    """
    import inspect

    src = inspect.getsource(segments._write_route)
    assert 'dst = dst or PROCESSED / "route_vehicle.csv"' in src, (
        "기본 산출 경로가 바뀌었다 — 이음매는 **시험용**이고 기본은 종전 그대로여야 한다.")
    sig = inspect.signature(segments._write_route)
    assert sig.parameters["dst"].default is None, "이음매의 기본값은 None 이다"
