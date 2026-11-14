#!/usr/bin/env python3
"""
publish_checkpoints.py — **체크포인트(소화전 · CCTV)를 엣지 칸으로 옮긴다.**  (PLAN #72)

    소화전   `hydrant_point_5186.gpkg` → 엣지 `hyd`  (그 엣지에서 HYD_SNAP_M 안의 지점 번호들)
    CCTV     `cctv_5186.gpkg`          → 엣지 `cctv` (그 엣지에서 CCTV_RANGE 안의 지점 번호들)

── 왜 생겼나 ───────────────────────────────────────────────────
소화전 · CCTV 는 지도에 **점**으로만 떠 있었다(`hydrants.geojson` · `cctv.geojson`).
경로가 정해진 뒤 「이 경로상 소화전 몇 개」를 말하려면 화면이 매번 점 전부와 경로
형상의 거리를 다시 재야 했고, 그 일을 하는 코드는 없었다. **엣지에 붙여 두면**
경로(엣지 번호 열)가 나오는 순간 합집합의 크기가 곧 답이다 — `route_checkpoints()`.

── 왜 수가 아니라 **번호 목록**인가 ─────────────────────────────
교차점 곁의 소화전은 **여러 엣지에서 다 가깝다.** 엣지마다 수를 실으면 경로의 합이
같은 소화전을 두 번 세고, 가장 가까운 엣지 하나에만 붙이면 옆 엣지로 지나가는 경로가
그것을 놓친다. 번호 목록이면 둘 다 없다 — 경로의 수는 **합집합의 크기**다.
번호는 최상위 `checkpoints.hyd` · `checkpoints.cctv` (좌표 목록)의 자리다.

── 결측과 0 (`park` · `ecam` 과 같은 규약) ───────────────────────
    null   원천 파일이 없다 — 모른다
    []     원천은 있고 그 엣지 곁에 하나도 없다
★ `[]` 는 「소화전이 없다」가 아니라 **「대장에 실린 것 중에 곁에 없다」**다. 대장에
  없는 소화전 · 고장 난 소화전은 이 발행이 모른다.

★ **판정에 안 닿는다.** `code_closure("firelane.segments")` 가 이 파일을 안 든다 —
  읽기만 하고 `navi_graph.json` 의 새 칸으로만 나간다. 기존 칸은 한 글자도 안 바뀐다.

IN    data/processed/hydrant_point_5186.gpkg · cctv_5186.gpkg
OUT   없다 — 값을 **돌려주기만** 한다. 파일은 `publish_navi` 가 쓴다
PARAM HYD_SNAP_M(호스 1본 15m — `tools/hydrant_reach.py` 의 첫 등급과 같은 수) ·
      CCTV_RANGE(`seg/params.py` — 영상판정이 성립하는 거리. 재선언하지 않는다) · SITE_M
밖    **단속 밀도는 여기 없다** — `park` · `ecam` 은 도로명 단위로 이미 붙어 있다
      (`publish_navi._parking` · `_enforce_cam` · DECISIONS §759). 화면에 띄우는 일은
      내비(`web/navi/src`) 몫이다. 호스가 실제로 깔리는 길 · 소화전의 작동 여부는 안 본다
      (직선거리만 잰다).
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from firelane.paths import PROCESSED
from firelane.seg.params import CCTV_RANGE

P = PROCESSED

#: 소화전을 엣지에 붙이는 거리(m). 호스 1본 — `tools/hydrant_reach.py::TIERS` 의 「1본」.
#: 차를 그 엣지에 세우고 호스 한 본으로 닿는 소화전만 「경로상」으로 센다.
HYD_SNAP_M = 15.0
#: 같은 자리로 볼 간격(m). 대장이 한 지점을 두 행으로 싣는다(소화전 528행 · 498자리).
SITE_M = 0.1

#: 종류 → (원천 파일, 붙이는 거리). 순서가 발행 칸 순서다.
KINDS: dict[str, tuple[str, float]] = {
    "hyd": ("hydrant_point_5186.gpkg", HYD_SNAP_M),
    "cctv": ("cctv_5186.gpkg", CCTV_RANGE),
}


def sites(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """점들을 **자리**로 줄인다 — `SITE_M` 격자에서 같은 칸이면 한 자리. 정렬해 돌려준다(결정적)."""
    seen: dict[tuple[int, int], tuple[float, float]] = {}
    for x, y in points:
        seen.setdefault((round(x / SITE_M), round(y / SITE_M)), (float(x), float(y)))
    return sorted(seen.values())


def attach(lines: Sequence, pts: Sequence[tuple[float, float]], snap_m: float
           ) -> tuple[list[list[int]], list[tuple[float, float]]]:
    """엣지마다 `snap_m` 안의 점 번호 목록 · 어느 엣지에든 붙은 점들(번호 순).

    ★ 어느 엣지에도 안 붙은 점은 **버리고 번호를 다시 매긴다** — 원천은 구 전체이고
      그래프는 그 일부라, 다 실으면 대부분이 아무도 안 가리키는 점이다.
    ★ 한 점이 여러 엣지에 붙을 수 있다(교차점 곁). 그래서 경로의 수는 합이 아니라 합집합이다.
    """
    from shapely import STRtree
    from shapely.geometry import Point

    per: list[list[int]] = [[] for _ in lines]
    if not lines or not pts:
        return per, []
    tree = STRtree(list(lines))
    raw: list[list[int]] = [[] for _ in lines]
    used: list[int] = []
    for k, (x, y) in enumerate(pts):
        p = Point(x, y)
        hit = [int(j) for j in tree.query(p.buffer(snap_m)) if lines[int(j)].distance(p) <= snap_m]
        if hit:
            used.append(k)
            for j in hit:
                raw[j].append(k)
    renum = {k: n for n, k in enumerate(used)}
    for j, ks in enumerate(raw):
        per[j] = sorted(renum[k] for k in ks)
    return per, [pts[k] for k in used]


def checkpoints(m) -> tuple[dict[str, list[list[int]] | None], dict[str, list[tuple[float, float]]], dict]:
    """5186 구간 `m` 의 엣지마다 종류별 번호 목록 · 종류별 점(5186) · 센 것.

    원천이 없는 종류는 엣지 칸이 통째로 `None` 이다(0 으로 채우지 않는다).
    """
    import geopandas as gpd

    lines = [g.geoms[0] if g.geom_type == "MultiLineString" else g for g in m.geometry]
    per: dict[str, list[list[int]] | None] = {}
    pts: dict[str, list[tuple[float, float]]] = {}
    stat: dict[str, dict] = {}
    for kind, (name, snap) in KINDS.items():
        src = P / name
        if not src.exists():
            print(f"  ! {name} 없음 — `{kind}` 를 결측으로 낸다")
            per[kind], pts[kind] = None, []
            stat[kind] = {"src_sites": 0, "sites": 0, "null_edges": len(lines), "zero_edges": 0}
            continue
        g = gpd.read_file(src)
        if g.crs is None or g.crs.to_epsg() != 5186:
            raise SystemExit(f"★ {name} 의 좌표계가 5186 이 아니다 — 거리를 미터로 잴 수 없다")
        allp = sites((p.x, p.y) for p in g.geometry if p is not None and not p.is_empty)
        per[kind], pts[kind] = attach(lines, allp, snap)
        stat[kind] = {"src_sites": len(allp), "sites": len(pts[kind]), "null_edges": 0,
                      "zero_edges": sum(1 for ks in per[kind] if not ks)}
    return per, pts, stat


def route_checkpoints(edges: Sequence[dict], path: Iterable[int]) -> dict:
    """경로(엣지 번호 열) 위의 체크포인트 — **경로 산출 직후** 부르는 순수 함수.

    돌려주는 것  {"hyd": N | None, "hyd_ids": [...], "cctv": N | None, "cctv_ids": [...]}
    ★ 수는 **합집합의 크기**다 — 두 엣지가 같은 소화전을 가리켜도 한 번 센다.
    ★ 경로의 엣지 하나라도 그 칸이 없거나 `null` 이면 수는 `None`(모른다)이다.
      아는 엣지만 세어 수를 내면 「적어도 N」을 「N」이라고 말하게 된다. 번호 목록은
      아는 것만 싣는다.
    ★ 빈 경로는 0 이 아니라 `None` 이다 — 경로가 없으면 셀 것이 없다.
    """
    path = list(path)
    out: dict = {}
    for kind in KINDS:
        ids: set[int] = set()
        known = bool(path)
        for i in path:
            v = edges[i].get(kind)
            if v is None:
                known = False
                continue
            ids.update(v)
        out[kind] = len(ids) if known else None
        out[f"{kind}_ids"] = sorted(ids)
    return out


_LABEL = {"hyd": "소화전", "cctv": "CCTV"}


def route_line(summary: dict, kind: str = "hyd") -> str:
    """「이 경로상 소화전 N개」 한 줄. 모르면 모른다고 적는다 — 0 이라고 적지 않는다."""
    n = summary.get(kind)
    if n is None:
        return f"이 경로상 {_LABEL[kind]} 수를 모른다"
    return f"이 경로상 {_LABEL[kind]} {n}개"
