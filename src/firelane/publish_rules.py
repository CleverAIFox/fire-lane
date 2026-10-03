#!/usr/bin/env python3
"""
publish_rules.py — **통행 규칙을 그래프 칸으로 옮긴다.** (DECISIONS §367-4)

    일방통행   `ngii1k_center` 의 「일방통행」 → `ow`(0 · 1 · -1 · 2)
    회전 금지   TURNINFO → (들어오는 엣지, 노드, 나가는 엣지) 셋

── 왜 갈랐나 ───────────────────────────────────────────────────
`publish_navi.py` 가 613줄로 상한(600)을 넘었다. 쪼개는 축을 **크기가 아니라
「무엇을 읽는가」**로 골랐다 — §274 가 `read/` 를 가를 때 세운 그 기준이다.

이 두 묶음만이 **표준노드링크·TURNINFO 를 읽는다.** 나머지(판정색 · 지형 ·
노드 접합 · 단속 · 카메라)는 안 읽는다. 크기로 갈랐으면 `turns`(66줄)와
`oneway`(60줄)가 다른 파일에 갔을 텐데, 그러면 「표준노드링크 대조 폭을
바꿨다」가 **두 파일을 동시에** 움직인다.

★ **상수가 같이 간다.** `OW_BUF_M` · `NL_BUF_M` · `NODE_SNAP_M` · `TURN_ANGLE`
  은 전부 「이 원천과 우리 형상이 얼마나 어긋나는가」이고, 그 판단이 이 파일
  하나에 산다. 발행기에 남겨 두면 정본이 둘이 된다.

★ **판정에 안 닿는다.** `code_closure("firelane.segments")` 와
  `code_closure("firelane.ingest")` 둘 다 이 파일을 안 든다(실측) — 그래서
  `golden` 재잠금도 샤드 재도장도 없다. 산출도 바이트 동일이다.

IN    data/processed/ngii1k_center_5186.gpkg · node_link_5186.gpkg ·
      turn_restriction.csv · node_point_5186.gpkg
OUT   없다 — 값을 **돌려주기만** 한다. 파일은 `publish_navi` 가 쓴다
      ★ 공개하는 것은 `oneway()` · `turns()` **둘뿐이다.** 나머지는 `_` 로
        덮는다 — 꾸러미 경계를 넘는 이름이 곧 그 모듈의 계약이다(§370).
밖    **경로에서 빼지 않는다.** 규칙은 비용으로 바뀌고 그것은 내비 일이다
      (`web/navi/src/domain/rules.ts` · §215-1). 여기는 **칸만** 채운다.
      **배수도 여기 없다** — 그 수는 내비 쪽 정책이다.
"""
from __future__ import annotations

import math

import geopandas as gpd
from shapely.geometry import Point

from firelane.paths import ROOT

P = ROOT / "data" / "processed"

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


def oneway(m: gpd.GeoDataFrame) -> tuple[list[int], dict]:
    """구간마다 `ow`(0 · 1 · -1 · 2). `m` 은 5186 구간이다.

    ★ 2026-10-03 (DECISIONS §367). **「방향을 못 정했다」의 사유를 가른다.**
      종전 `stat` 은 `oneway` · `dir_known` · `nl_twoway` 셋이었고, 실측이
      57 · 1 · ? 였다. 56건이 왜 모름으로 남았는지가 **어디에도 없었다** —
      링크가 **없어서**인지 양방향 둘이 잡혀서인지 좁게/넓게가 갈려서인지.
      그 구별이 없으면 다음에 무엇을 고쳐야 하는지도 알 수 없다. 넷으로 가른다 —

          nl_none    버퍼 안에 표준노드링크가 **하나도 없다** → 매칭 범위 문제
          nl_twoway  반대 방향 둘이 잡힌다 → **양방향 길이다**(모름이 맞다)
          nl_split   좁게는 하나인데 넓게가 다르다 → 버퍼 조율 문제
          nl_absent  `node_link_5186.gpkg` 자체가 없다 → 레이크 문제

      ★ 이 값은 **경로를 안 바꾼다.** `ow` 배정 규칙을 한 글자도 안 고쳤다 —
        세는 칸만 늘렸으므로 `navi_graph.json` 이 바이트 동일이다.
    """
    out = [0] * len(m)
    stat = {"oneway": 0, "dir_known": 0, "nl_twoway": 0,
            "nl_none": 0, "nl_split": 0, "nl_absent": 0}
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
            stat["nl_absent"] += 1
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
        elif not wide:
            # ★ 넓게 봐도 링크가 없다. **양방향이라서 모르는 것이 아니다** —
            #   그냥 표준노드링크가 그 골목을 안 든다. 간선만 덮기 때문이다
            #   (§1 #31 이 ITS 소통정보에서 같은 것을 쟀다).
            stat["nl_none"] += 1
        else:
            # 좁게와 넓게가 갈린다 — 버퍼 조율로 풀릴 수 있는 쪽이다
            stat["nl_split"] += 1
    return out, stat



def turns(m: gpd.GeoDataFrame, nodes_m: list, ea: list, eb: list) -> tuple[list, dict]:
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
