#!/usr/bin/env python3
"""
publish_navi.py — 내비가 먹을 그래프 하나를 낸다.  (PLAN #63 / #61)

IN    data/processed/segments.geojson · web/config.js
      data/processed/ngii1k_center_5186.gpkg · node_link_5186.gpkg ·
      node_point_5186.gpkg · turn_restriction.csv          (통행 규칙 — 없으면 규칙 없이 낸다)
      data/processed/parking_enforce.csv                    (불법주정차 단속 이력 — 도로 단위)
OUT   web/data/navi_graph.json
PARAM 노드접합 NODE_TOL(seg/params.py) · 좌표 정밀도 PREC · 크기 상한 SIZE_MAX

── 왜 새 파일인가 ────────────────────────────────────────────────
`segments.geojson` 에 컬럼을 더하지 않는다. 그것은 지도가 읽는 파일이고
golden 지문이 걸려 있다. **새 파일로 내면 기존 열여섯은 한 바이트도 안
바뀐다** — `route_vehicle.csv` 를 별 파일로 뺀 것과 같은 수법(MASTER §20-2).

── 무엇이 들어가는가 ─────────────────────────────────────────────
  style  {verdict: {color, lightColor, label, desc}}   web/config.js 에서 추출
  nodes  [[lon, lat], ...]                             접합된 교차점
  edges  [{seg_uid, a, b, verdict, width_min_m, coords, ow?, ...}]
  turns  [[들어오는 엣지, 노드, 나가는 엣지, TURN_TYPE], ...]   회전 금지

── 통행 규칙 (2026-09-22 · DECISIONS §215-1) ──────────────────────
`ow` — 일방통행. **없으면 양방향**이다(크기를 아끼려고 0 은 안 싣는다).
    1   a→b 로만 간다        -1  b→a 로만 간다
    2   일방통행인데 **방향을 모른다**
★ 방향을 대부분 모른다. 1:1000 중심선(`ngii1k_center.일방통행`)은 일방통행 **여부**만
  있고 방향 필드가 없다. 그림 방향이 진행 방향이라는 가정을 표준노드링크로 대 봤더니
  22선 중 같음 8 · 반대 14 였다 — 가정이 틀렸다. 방향은 표준노드링크(`node_link`)가 한
  방향 링크만 가진 곳에서만 확정한다. 나머지는 2 로 내고, 내비가 **양쪽 다 조금 불리하게**
  본다(역주행일 수도 있다). 지어내지 않는다.
`park` — 그 구간 **도로명**에 찍힌 불법주정차 단속 건수(2022-01~2025-02 · 두 판 합). 없으면 0.
    ★ 도로 단위다. 단속 장소가 「동명로 123」 처럼 도로명 + 번지라 구간까지 못 내린다 —
      같은 도로명의 구간은 같은 수를 받는다. 주정차 **위험의 대리값**이지 현재 주차가 아니다.
    ★ 판정에 안 쓴다. 화면(구간 카드 · 병목 패널)이 「단속 이력」 으로 띄울 뿐이다.
`turns` — 표준노드링크 TURNINFO 의 금지 셋(101 좌회전 · 102 직진 · 103 우회전 금지).
    011(유턴 허용) 같은 허용 규칙은 싣지 않는다.
★ 경로에서 **빼지 않는다.** 소방차는 불리하게 계산하고 경고한다(사용자 결정 2026-09-22).
  그 계산은 `web/navi/src/domain/rules.ts` 의 일이고 발행은 사실만 싣는다.

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
            "color": f"rgb({rgb[0]},{rgb[1]},{rgb[2]})",
            "lightColor": f"rgb({light[0]},{light[1]},{light[2]})",
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
    return (round(x / tol), round(y / tol))


def _isna(v) -> bool:
    try:
        import pandas as pd
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _py(v):
    """numpy 스칼라를 파이썬 기본형으로. json 이 못 먹는다."""
    return v.item() if hasattr(v, "item") else v


# ── 통행 규칙 ─────────────────────────────────────────────────
# 회전 금지 코드. 표준노드링크 구축기준 TURN_TYPE — 011 유턴 · 012 P턴 은 허용이라 뺀다.
TURN_BAN = {3, 101, 102, 103}
OW_COVER = 0.6      # 구간 길이의 이 비율 이상이 일방통행 중심선 위면 일방통행으로 본다
OW_BUF_M = 2.0      # 중심선 대조 폭. 1:1000 중심선과 구간 형상의 어긋남
NL_BUF_M = 4.0      # 표준노드링크 대조 폭. 링크가 1:1000 보다 거칠다
NODE_SNAP_M = 15.0  # TURNINFO 노드 ↔ 그래프 노드. 교차점 대표점끼리의 어긋남
TURN_ANGLE = 20.0   # 링크 ↔ 엣지 방위 허용차(도). 교차로 가지 사이 각은 보통 45° 이상이다


def _line(g):
    return g.geoms[0] if g.geom_type == "MultiLineString" else g


def _dir(L, d: float):
    a, b = L.interpolate(max(d - 3, 0)), L.interpolate(min(d + 3, L.length))
    vx, vy = b.x - a.x, b.y - a.y
    n = math.hypot(vx, vy) or 1.0
    return vx / n, vy / n


def _same_dir(L1, L2, at) -> int:
    """두 선이 `at` 부근에서 같은 방향이면 1, 반대면 -1, 비스듬하면 0."""
    ax, ay = _dir(L1, L1.project(at))
    bx, by = _dir(L2, L2.project(at))
    d = ax * bx + ay * by
    return 0 if abs(d) < 0.8 else (1 if d > 0 else -1)


def _nl_signs(nl: gpd.GeoDataFrame, L, buf: float) -> set[int]:
    """구간 `L` 을 따라가는 표준노드링크 링크들의 방향(1 같음 · -1 반대) 집합."""
    signs = set()
    for j in nl.sindex.query(L.buffer(buf)):
        K = nl.geometry[j]
        inter = K.intersection(L.buffer(buf))
        if inter.length < min(10.0, 0.5 * L.length):
            continue
        sd = _same_dir(L, K, inter.interpolate(0.5, normalized=True))
        if sd:
            signs.add(sd)
    return signs


def _oneway(m: gpd.GeoDataFrame) -> tuple[list[int], dict]:
    """구간마다 `ow`(0 · 1 · -1 · 2). `m` 은 5186 구간이다."""
    out = [0] * len(m)
    stat = {"oneway": 0, "dir_known": 0, "nl_twoway": 0}
    src = P / "ngii1k_center_5186.gpkg"
    if not src.exists():
        print("  ! ngii1k_center 없음 — 일방통행 없이 낸다")
        return out, stat
    c = gpd.read_file(src)
    ow = c[c["일방통행"] == "일방통행"].explode(index_parts=False).reset_index(drop=True)
    nl = None
    if (P / "node_link_5186.gpkg").exists():
        nl = gpd.read_file(P / "node_link_5186.gpkg").explode(index_parts=False).reset_index(drop=True)
    oidx = ow.sindex
    for i, g in enumerate(m.geometry):
        L = _line(g)
        cover = max((L.intersection(ow.geometry[j].buffer(OW_BUF_M)).length
                     for j in oidx.query(L.buffer(OW_BUF_M))), default=0.0)
        if cover < OW_COVER * L.length:
            continue
        stat["oneway"] += 1
        out[i] = 2
        if nl is None:
            continue
        near, wide = _nl_signs(nl, L, NL_BUF_M), _nl_signs(nl, L, 2 * NL_BUF_M)
        # ★ 방향 확정은 **좁게도 넓게도 한 방향**일 때만. 4m 에서 한 방향이던 것이 8m 에서
        #   반대 링크를 만나는 곳이 10곳 있었다 — 반대편 링크가 멀리 그려졌을 뿐인 양방향 길이다.
        #   틀린 확정은 모름보다 나쁘다: 옳은 방향을 벌하고 역주행을 공짜로 만든다.
        if len(near) == 1 and near == wide:
            out[i] = next(iter(near))      # 구간 형상 방향 = 엣지 a→b
            stat["dir_known"] += 1
        elif len(wide) == 2:
            stat["nl_twoway"] += 1
    return out, stat


_TOKEN_RE = re.compile(r"[\s,()·/]+")


def _road_of(txt: str, have: set[str]) -> str | None:
    """단속 장소 글에서 그래프에 있는 도로명 하나 — **토막마다** 앞에서부터 가장 긴 것.

    ★ 2026-09-22 독립 검토. 종전에는 공백을 다 지우고 정규식으로 뽑아 「동명동 동계천로」 가
      「동명동동계천로」 한 덩어리가 됐고 41,929행(도로명이 있는데도)을 놓쳤다. 공백으로 자르고,
      토막의 **앞머리**가 로 · 길로 끝나는 자리마다 그래프 도로명과 대 본다 — 「구성로204번길」 은
      「구성로204번길」 로, 「서석로7(웨딩의거리)」 는 「서석로」 로.
    """
    best = None
    for t in _TOKEN_RE.split(txt):
        for i, ch in enumerate(t):
            if ch in "로길" and t[:i + 1] in have and (best is None or i + 1 > len(best)):
                best = t[:i + 1]
    return best


def _parking(names: list[str | None]) -> tuple[list[int], dict]:
    """도로명별 단속 건수를 구간에 나눠 준다. 없으면 전부 0."""
    import pandas as pd
    src = P / "parking_enforce.csv"
    out = [0] * len(names)
    stat = {"rows": 0, "matched": 0, "roads": 0}
    if not src.exists():
        print("  ! parking_enforce 없음 — 단속 이력 없이 낸다")
        return out, stat
    s = pd.read_csv(src, usecols=["위반장소명"], dtype=str)["위반장소명"].fillna("")
    stat["rows"] = len(s)
    have = {n for n in names if n}
    cnt: dict[str, int] = {}
    for txt in s:
        k = _road_of(txt, have)
        if k:
            cnt[k] = cnt.get(k, 0) + 1
    stat["matched"] = sum(cnt.values())
    stat["roads"] = len(cnt)
    return [cnt.get(n, 0) if n else 0 for n in names], stat


def _turns(m: gpd.GeoDataFrame, nodes_m: list, ea: list, eb: list) -> tuple[list, dict]:
    """TURNINFO 금지 규칙을 그래프 (들어오는 엣지, 노드, 나가는 엣지) 로 옮긴다."""
    import pandas as pd
    stat = {"rules": 0, "mapped": 0}
    need = [P / "turn_restriction.csv", P / "node_link_5186.gpkg", P / "node_point_5186.gpkg"]
    if not all(f.exists() for f in need):
        print("  ! 회전제한 입력 없음 — 회전 규칙 없이 낸다")
        return [], stat
    tr = pd.read_csv(need[0], dtype={"NODE_ID": str, "ST_LINK": str, "ED_LINK": str})
    tr = tr[tr["TURN_TYPE"].isin(TURN_BAN)]
    stat["rules"] = len(tr)
    nl = gpd.read_file(need[1]).set_index("LINK_ID")
    nl.index = nl.index.astype(str)
    npt = gpd.read_file(need[2]).set_index("NODE_ID")
    npt.index = npt.index.astype(str)
    lines = [_line(g) for g in m.geometry]

    def gnode(pt) -> int | None:
        best, bd = None, NODE_SNAP_M
        for k, (x, y) in enumerate(nodes_m):
            d = math.hypot(x - pt.x, y - pt.y)
            if d < bd:
                best, bd = k, d
        return best

    def out_bearing(L, p) -> float:
        """`p` 에서 선을 따라 **밖으로** 15m 나가는 방위(도)."""
        d = L.project(p)
        q = L.interpolate(min(d + 15, L.length)) if d < L.length / 2 else L.interpolate(max(d - 15, 0))
        o = L.interpolate(d)
        return math.degrees(math.atan2(q.x - o.x, q.y - o.y)) % 360

    def edge_on(link, lp, node: int) -> int | None:
        """`node` 에서 나가는 엣지 중 `link` 와 같은 쪽으로 뻗는 것.

        ★ 겹침 길이로 고르지 않는다. 표준노드링크는 1:1000 보다 거칠어 교차점 부근에서
          4m 넘게 어긋나고, 겹침으로 대면 17개 노드 중 한 규칙도 못 옮겼다. **노드에서
          뻗는 방위**는 어긋남에 둔하다.
        """
        want = out_bearing(_line(link), lp)
        here = Point(nodes_m[node])
        best, bd = None, TURN_ANGLE
        for j, (x, y) in enumerate(zip(ea, eb, strict=True)):
            if node not in (x, y) or x == y:
                continue
            dd = abs((out_bearing(lines[j], here) - want + 180) % 360 - 180)
            if dd < bd:
                best, bd = j, dd
        return best

    out = set()
    for r in tr.itertuples():
        if r.NODE_ID not in npt.index or r.ST_LINK not in nl.index or r.ED_LINK not in nl.index:
            continue
        n = gnode(npt.geometry[r.NODE_ID])
        if n is None:
            continue
        lp = npt.geometry[r.NODE_ID]
        ei = edge_on(nl.geometry[r.ST_LINK], lp, n)
        eo = edge_on(nl.geometry[r.ED_LINK], lp, n)
        if ei is None or eo is None or ei == eo:
            continue
        out.add((ei, n, eo, int(r.TURN_TYPE)))
    stat["mapped"] = len(out)
    return sorted(out), stat


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
    ow, ow_stat = _oneway(m)
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
        if ow[i]:
            rec["ow"] = ow[i]
        edges.append(rec)
    turns, tr_stat = _turns(m, nodes_m, [e["a"] for e in edges], [e["b"] for e in edges])
    park, pk_stat = _parking([e.get("road_name") for e in edges])
    for e, n in zip(edges, park, strict=True):
        if n:
            e["park"] = n

    out = {
        "crs": "EPSG:4326",
        "node_tol_m": NODE_TOL,
        "counts": {"nodes": len(nodes), "edges": len(edges), "self_loops": loops,
                   "oneway": ow_stat["oneway"], "oneway_dir_known": ow_stat["dir_known"],
                   "turn_bans": len(turns)},
        "style": style,
        "nodes": nodes,
        "edges": edges,
        "turns": [list(t) for t in turns],
    }
    txt = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    W.mkdir(parents=True, exist_ok=True)
    (W / "navi_graph.json").write_text(txt, encoding="utf-8")

    size = len(txt.encode())
    print(f"  navi_graph.json  노드 {len(nodes)} · 엣지 {len(edges)}"
          f" · 자기루프 {loops} · 노드 최대이동 {dmax:.3f}m"
          f" · 판정색 {len(style)}종 · {size / 1024:.0f}KB")
    print(f"  통행 규칙  일방통행 {ow_stat['oneway']} (방향 확정 {ow_stat['dir_known']}"
          f" · 표준노드링크가 양방향 {ow_stat['nl_twoway']}) · 회전 금지 {tr_stat['rules']}건 중"
          f" {tr_stat['mapped']} 을 그래프에")
    print(f"  주정차 단속  {pk_stat['rows']:,}건 중 도로명이 맞는 {pk_stat['matched']:,}건"
          f" · 도로 {pk_stat['roads']}")
    if size > SIZE_MAX:
        raise SystemExit(
            f"★ navi_graph.json 이 상한을 넘었다 {size / 1024 / 1024:.1f}MB "
            f"> {SIZE_MAX / 1024 / 1024:.0f}MB. KEEP 을 줄이거나 PREC 를 낮춰라")
    if dmax > NODE_TOL:
        raise SystemExit(f"★ 노드 최대이동 {dmax:.3f}m 가 NODE_TOL 을 넘었다")


if __name__ == "__main__":
    main()
