#!/usr/bin/env python3
"""
publish_navi.py — 내비가 먹을 그래프 하나를 낸다.  (PLAN #63 / #61)

IN    data/processed/segments.geojson · web/config.js
OUT   web/data/navi_graph.json
PARAM 노드접합 NODE_TOL(seg/params.py) · 좌표 정밀도 PREC · 크기 상한 SIZE_MAX

── 왜 새 파일인가 ────────────────────────────────────────────────
`segments.geojson` 에 컬럼을 더하지 않는다. 그것은 지도가 읽는 파일이고
golden 지문이 걸려 있다. **새 파일로 내면 기존 열여섯은 한 바이트도 안
바뀐다** — `route_vehicle.csv` 를 별 파일로 뺀 것과 같은 수법(MASTER §20-2).

── 무엇이 들어가는가 ─────────────────────────────────────────────
  style  {verdict: {color, lightColor, label, desc}}   web/config.js 에서 추출
  nodes  [[lon, lat], ...]                             접합된 교차점
  edges  [{seg_uid, a, b, verdict, width_min_m, coords, ...}]

`coords` 를 넣는 이유는 둘이다 — 스냅(#61)이 선형 위 최근접점을 찾아야
하고, 경로가 정해지면 그 좌표열을 Map Matching 에 던져야 한다(하이브리드).
중심점만 넣으면 둘 다 못 한다.

★ 노드접합을 여기서 새로 발명하지 않는다. `seg/params.py::NODE_TOL` 을
  그대로 쓴다. 파이썬이 0.5m 로 묶은 것을 TS 가 0.6m 로 묶으면 두 그래프가
  갈리고, 그러면 `route_vehicle.json` 과 대조가 안 된다.

★ 임계값을 여기서 재선언하지 않는다. 3.0/7.0 의 정본은 `seg/params.py`
  하나다(MASTER §10-2). 이 파일은 `width_min_m` 원값만 실어 보내고
  판정은 이미 계산된 `verdict` 를 그대로 옮긴다.

★ 판정 색도 재선언하지 않는다. 정본은 `web/config.js` 하나이고 지도와
  내비가 같은 값을 본다. 앱이 그 파일을 직접 읽을 수 없어서(ES 모듈이
  아니라 `const CONFIG = {` 로 시작하는 스크립트다) 발행이 뽑아 싣는다 —
  파이프라인이 추출하고 앱이 소비하는 이 저장소 방식 그대로다.

★ blocked 도 싣는다. 버리면 클라이언트가 "왜 못 가는지" 를 못 말한다.
  경로에서 빼는 것은 `edge_cost` 의 일이지 발행의 일이 아니다.
"""
from __future__ import annotations

import json
import math
import re

import geopandas as gpd
from shapely.geometry import Point

from firelane.paths import ROOT
from firelane.seg.params import NODE_TOL

P = ROOT / "data" / "processed"
W = ROOT / "web" / "data"

# 좌표 자릿수. publish_web.py 와 같은 6자리(약 11cm)를 쓴다.
PREC = 6
# 산출 상한. web/data 40MB 예산 안에서 이 파일 몫을 미리 못박는다.
SIZE_MAX = 2 * 1024 * 1024

# 내비가 실제로 읽는 것만 싣는다. 늘릴 때는 소비자를 먼저 만든다 —
# `route_vehicle.json` 이 83KB 로 발행되고 소비자가 0이던 상태를 반복하지 않는다.
# 내비가 실제로 읽는 것만 싣는다. **소비자를 먼저 만들고 늘린다** —
# route_vehicle.json 이 83KB 로 발행되고 소비자가 0이던 상태를 반복하지
# 않는다(MASTER §20-5).
#
#   width_cov · n_sample · cctv_dist_m · unknown_reason
#       ui/BottleneckPanel.tsx 가 "측정 신뢰도 · 표본 수 · 영상판정" 으로 띄운다
#   road_bt_m
#       domain/speed.ts 가 폭이 없을 때 속도 추정에 쓴다.
#       ★ **판정에는 안 쓴다** — 정수 90% · 2.0 에 30% 몰려 있어 폭 판정의
#         근거가 못 된다(대장 road_link.note)
KEEP = ("seg_uid", "verdict", "width_min_m", "width_max_m", "length_m",
        "seg_label", "road_name", "in_emd",
        "width_cov", "n_sample", "cctv_dist_m", "unknown_reason",
        "road_bt_m")

_STYLE_RE = re.compile(
    r'(\w+)\s*:\s*\{\s*color\s*:\s*\[([\d,\s]+)\]'
    r'(?:\s*,\s*lightColor\s*:\s*\[([\d,\s]+)\])?'
    r'\s*,\s*label\s*:\s*"([^"]*)"'
    r'\s*,\s*desc\s*:\s*"([^"]*)"'
)


def _verdict_style() -> dict:
    """`web/config.js` 의 verdict 4종에서 색·라벨·설명을 뽑는다.

    ★ 정규식으로 JS 를 읽는다. 취약하지만 대상이 `verdict:` 블록 하나뿐이다.
      **못 읽으면 죽는다** — 색이 빠진 채 발행되면 화면이 회색 한 덩어리가
      되고 아무도 못 알아챈다. 기본색을 두지 않는 이유도 같다.
    """
    txt = (ROOT / "web" / "config.js").read_text(encoding="utf-8")
    try:
        blk = txt[txt.index("verdict:"):]
        blk = blk[:blk.index("\n  },") + 5]
    except ValueError:
        raise SystemExit("★ web/config.js 에서 verdict 블록을 못 찾았다") from None

    out = {}
    for k, c, lc, label, desc in _STYLE_RE.findall(blk):
        rgb = [int(x) for x in c.split(",")]
        light = [int(x) for x in lc.split(",")] if lc else rgb
        out[k] = {
            "color": "rgb(%d,%d,%d)" % tuple(rgb),
            "lightColor": "rgb(%d,%d,%d)" % tuple(light),
            "label": label,
            "desc": desc,
        }

    need = {"clear", "needs_cv", "unknown", "blocked"}
    if set(out) != need:
        raise SystemExit(
            f"★ web/config.js 에서 판정 색을 못 읽었다.\n"
            f"  얻은 것 {sorted(out)}\n"
            f"  필요한 것 {sorted(need)}\n"
            f"  config.js 의 verdict 블록 서식이 바뀌었을 수 있다.")
    return out


def _node_key(x: float, y: float, tol: float) -> tuple[int, int]:
    """미터 좌표를 tol 격자로 양자화한다. union-find 의 씨앗."""
    return (int(round(x / tol)), int(round(y / tol)))


def _isna(v) -> bool:
    try:
        import pandas as pd
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _py(v):
    """numpy 스칼라를 파이썬 기본형으로. json 이 못 먹는다."""
    return v.item() if hasattr(v, "item") else v


def main() -> None:
    style = _verdict_style()

    seg = gpd.read_file(P / "segments.geojson")
    if seg.crs is None or seg.crs.to_epsg() != 4326:
        seg = seg.to_crs(4326)
    # 노드접합은 미터에서 한다. 도 단위로 0.5 를 재면 위도에 따라 달라진다.
    m = seg.to_crs(5186)

    # ── 끝점 수집 ────────────────────────────────────────────────
    ends: list[tuple[float, float]] = []
    for g in m.geometry:
        c = list(g.geoms[0].coords) if g.geom_type == "MultiLineString" else list(g.coords)
        ends.append(c[0])
        ends.append(c[-1])

    # ── union-find 로 NODE_TOL 안의 끝점을 묶는다 ────────────────
    # graph.py 는 STRtree 를 쓴다. 여기는 2,202 점이라 격자로 충분하다.
    parent: dict[int, int] = {i: i for i in range(len(ends))}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cells: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(ends):
        cells.setdefault(_node_key(x, y, NODE_TOL), []).append(i)

    for i in range(len(ends)):
        kx, ky = _node_key(ends[i][0], ends[i][1], NODE_TOL)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for jj in cells.get((kx + dx, ky + dy), ()):
                    if jj == i:
                        continue
                    if math.dist(ends[i], ends[jj]) <= NODE_TOL:
                        ri, rj = find(i), find(jj)
                        if ri != rj:
                            parent[ri] = rj

    # 대표점은 무게중심. graph.py 와 같은 방식이다.
    groups: dict[int, list[int]] = {}
    for i in range(len(ends)):
        groups.setdefault(find(i), []).append(i)

    nid: dict[int, int] = {}
    nodes_m: list[tuple[float, float]] = []
    dmax = 0.0
    for members in groups.values():
        cx = sum(ends[k][0] for k in members) / len(members)
        cy = sum(ends[k][1] for k in members) / len(members)
        idx = len(nodes_m)
        nodes_m.append((cx, cy))
        for k in members:
            nid[k] = idx
            dmax = max(dmax, math.dist(ends[k], (cx, cy)))

    # 노드 좌표를 4326 으로 되돌린다.
    nodes_ll = gpd.GeoSeries([Point(p) for p in nodes_m], crs=5186).to_crs(4326)
    nodes = [[round(p.x, PREC), round(p.y, PREC)] for p in nodes_ll]

    # ── 엣지 ─────────────────────────────────────────────────────
    edges = []
    loops = 0
    for i, (_, row) in enumerate(seg.iterrows()):
        a, b = nid[2 * i], nid[2 * i + 1]
        g = row.geometry
        c = list(g.geoms[0].coords) if g.geom_type == "MultiLineString" else list(g.coords)
        rec = {k: (None if k not in row or _isna(row[k]) else _py(row[k])) for k in KEEP}
        if a == b:
            # 자기루프. graph.py 가 버리는 것과 같은 마이크로 엣지다.
            # 경로에는 못 쓰지만 스냅 대상으로는 남긴다 — 그 위에 서 있을 수 있다.
            loops += 1
        rec["a"] = a
        rec["b"] = b
        rec["loop"] = int(a == b)
        rec["coords"] = [[round(x, PREC), round(y, PREC)] for x, y in c]
        edges.append(rec)

    out = {
        "crs": "EPSG:4326",
        "node_tol_m": NODE_TOL,
        "counts": {"nodes": len(nodes), "edges": len(edges), "self_loops": loops},
        "style": style,
        "nodes": nodes,
        "edges": edges,
    }
    txt = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    W.mkdir(parents=True, exist_ok=True)
    (W / "navi_graph.json").write_text(txt, encoding="utf-8")

    size = len(txt.encode())
    print(f"  navi_graph.json  노드 {len(nodes)} · 엣지 {len(edges)}"
          f" · 자기루프 {loops} · 노드 최대이동 {dmax:.3f}m"
          f" · 판정색 {len(style)}종 · {size / 1024:.0f}KB")
    if size > SIZE_MAX:
        raise SystemExit(
            f"★ navi_graph.json 이 상한을 넘었다 {size / 1024 / 1024:.1f}MB "
            f"> {SIZE_MAX / 1024 / 1024:.0f}MB. KEEP 을 줄이거나 PREC 를 낮춰라")
    if dmax > NODE_TOL:
        raise SystemExit(f"★ 노드 최대이동 {dmax:.3f}m 가 NODE_TOL 을 넘었다")


if __name__ == "__main__":
    main()
