#!/usr/bin/env python3
"""
publish_navi.py — 내비가 먹을 그래프 하나를 낸다.  (PLAN #63 / #61)

IN    data/processed/segments.geojson · web/config.js
      data/processed/ngii1k_center_5186.gpkg · node_link_5186.gpkg ·
      node_point_5186.gpkg · turn_restriction.csv          (통행 규칙 — 없으면 규칙 없이 낸다)
      data/processed/parking_enforce.csv                    (불법주정차 단속 이력 — 도로 단위)
      data/processed/enforce_cam.csv                        (불법주정차 단속 카메라 — 도로 단위)
OUT   web/data/navi_graph.json
PARAM 노드접합 NODE_TOL(seg/params.py) · 좌표 정밀도 PREC · 크기 상한 SIZE_MAX

── 왜 새 파일인가 ────────────────────────────────────────────────
`segments.geojson` 에 컬럼을 더하지 않는다. 그것은 지도가 읽는 파일이고
golden 지문이 걸려 있다. **새 파일로 내면 기존 열여섯은 한 바이트도 안
바뀐다** — `route_vehicle.csv` 를 별 파일로 뺀 것과 같은 수법(MASTER §20-2).

── 무엇이 들어가는가 ─────────────────────────────────────────────
  style  {verdict: {color, lightColor, label, desc}}   web/config.js 에서 추출
  terrain {enabled, exaggeration}                     web/config.js 에서 추출(§217-2)
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
`park` — 그 구간 **도로명**에 찍힌 불법주정차 단속 건수(2022-01~2025-02 · 두 판 합).
`ecam` — 그 구간 **도로명**에 선 불법주정차 단속 **카메라 지점** 수(`enforce_cam` · 57지점).
    ★ 도로 단위다. 단속 장소가 「동명로 123」 처럼 도로명 + 번지라 구간까지 못 내린다 —
      같은 도로명의 구간은 같은 수를 받는다. 주정차 **위험의 대리값**이지 현재 주차가 아니다.
    ★ 카메라는 **지점**으로 센다. 한 지점이 방향마다 한 행이라(3·36·40·41·42·45번) 행으로
      세면 같은 곳이 둘로 셋으로 불어난다. 번호가 지점이고 행이 방향이다(대장 note).
    ★ 판정에 안 쓴다. 화면(구간 카드 · 병목 패널)이 「단속 이력」 으로 띄우고,
      경로 비용은 `web/navi/src/domain/pressure.ts` 가 **계수 0** 으로 받는다 — 칸만 섰다.

★ **결측과 0 을 가른다** (2026-09-25). 둘 다 `null` 과 `0` 으로 **명시해서** 싣는다.

      null   그 구간에 **도로명이 없다.** 셀 수가 없었다 — 모른다
      0      도로명이 있고, 그 도로명에 찍힌 것이 **하나도 없다**

  종전에는 `if n:` 으로 0 을 **빼서** 발행했다. 그러면 받는 쪽에서 결측과 0 이 같은
  모습(`undefined`)이 되고, 「없음」 하나로 찍힌다 — **모르는 것을 없다고 말하는**
  자리다. 크기보다 이쪽이 중하다.

★ **0 이 「없다」가 아니다** (2026-09-25 실측). 지금 구간 1,281 전부에 도로명이 있어
  `park` 결측은 0 이고, 종전에 빠져 있던 110 은 **전부 실제 0** 이었다 — 그 자리의
  「없음」 표기는 우연히 맞았다. 그러나 **0 의 강도가 둘로 갈린다:**

      park  141,556행 중 54,541행만 도로명이 붙었다(87,015행 미배치 — 지번 표기)
      ecam  57지점 중 18지점만 붙었다(39지점 미배치 — 「지산동 521-3」 꼴)

  그래서 `ecam: 0` 은 「카메라가 없다」가 아니라 **「붙은 18지점 중에 없다」** 다.
  미배치 몫을 `counts.*_unplaced_*` 로 같이 실어 읽는 쪽이 0 의 강도를 알게 한다.
  지오코딩을 지어내서 0 을 메우지 않는다.
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

# ★ 2026-10-03 (§367-4). 통행 규칙(일방통행 · 회전 금지)을 `publish_rules` 로
#   갈랐다 — 표준노드링크·TURNINFO 를 읽는 것이 그 둘뿐이고, 그 대조 폭 상수도
#   거기 산다. 이 파일은 그 답을 **칸에 옮기기만** 한다.
from firelane.cli import no_args
from firelane.paths import ROOT
from firelane.publish_rules import _oneway, _turns
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


_TERRAIN_RE = re.compile(r"terrain\s*:\s*\{[^}]*?enabled\s*:\s*(true|false)[^}]*?exaggeration\s*:\s*([\d.]+)", re.S)


def _terrain() -> dict:
    """`web/config.js` 의 terrain 블록 — 지형 과장 배수의 정본은 그 파일 하나다(§217-2).

    ★ 못 읽으면 죽는다. 기본값을 두면 옛 지도와 내비의 지형 배수가 조용히 갈린다.
    """
    txt = (ROOT / "web" / "config.js").read_text(encoding="utf-8")
    m = _TERRAIN_RE.search(txt)
    if not m:
        raise SystemExit("★ web/config.js 에서 terrain.enabled · exaggeration 을 못 읽었다")
    return {"enabled": m.group(1) == "true", "exaggeration": float(m.group(2))}


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


def _spread(cnt: dict[str, int], names: list[str | None]) -> list[int | None]:
    """도로명별 수를 구간에 나눠 준다.

    ★ **도로명이 없는 구간은 `None`** 이다 — 0 이 아니다. 셀 수가 없었다는 뜻이고,
      「그 도로에 한 건도 없다」(0)와 섞으면 모르는 것을 없다고 말하게 된다.
    """
    return [(cnt.get(n, 0) if n else None) for n in names]


def _parking(names: list[str | None]) -> tuple[list[int | None], dict]:
    """도로명별 불법주정차 단속 **건수**. 자료가 없으면 전부 결측(`None`)이다."""
    import pandas as pd
    src = P / "parking_enforce.csv"
    stat = {"rows": 0, "matched": 0, "roads": 0}
    if not src.exists():
        # ★ 0 으로 채우지 않는다. 자료가 없는 것은 「한 건도 없다」가 아니다.
        print("  ! parking_enforce 없음 — 단속 이력을 결측으로 낸다")
        return [None] * len(names), stat
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
    return _spread(cnt, names), stat


def _enforce_cam(names: list[str | None]) -> tuple[list[int | None], dict]:
    """도로명별 단속 카메라 **지점** 수. 자료가 없으면 전부 결측(`None`)이다.

    ★ 행이 아니라 **번호**를 센다. 한 지점이 방향마다 한 행이라 행으로 세면 같은
      카메라가 두 번 세 번 센다(3·36·40·41·42·45번 · 대장 `enforce_cam.note`).
    ★ 주소가 지번(「지산동 521-3」)인 지점은 도로명이 안 나와 **못 붙는다.** 지오코딩을
      지어내지 않는다 — 붙은 수와 못 붙은 수를 같이 찍어 얼마나 성긴지 보이게 한다.
    """
    import pandas as pd
    src = P / "enforce_cam.csv"
    stat = {"rows": 0, "sites": 0, "matched": 0, "roads": 0}
    if not src.exists():
        print("  ! enforce_cam 없음 — 단속 카메라를 결측으로 낸다")
        return [None] * len(names), stat
    df = pd.read_csv(src, usecols=["번호", "주소"], dtype=str).fillna("")
    stat["rows"] = len(df)
    have = {n for n in names if n}
    # 지점(번호) → 그 지점의 도로명. 방향 행 여럿이 같은 지점을 가리킨다.
    site: dict[str, str] = {}
    for r in df.itertuples(index=False):
        k = _road_of(r.주소, have)
        if k and r.번호 not in site:
            site[r.번호] = k
    stat["sites"] = df["번호"].nunique()
    stat["matched"] = len(site)
    cnt: dict[str, int] = {}
    for k in site.values():
        cnt[k] = cnt.get(k, 0) + 1
    stat["roads"] = len(cnt)
    return _spread(cnt, names), stat


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
    rn = [e.get("road_name") for e in edges]
    park, pk_stat = _parking(rn)
    ecam, ec_stat = _enforce_cam(rn)
    # ★ `if n:` 을 쓰지 않는다. 0 과 결측을 **둘 다 명시해서** 싣는다 — 빼면 받는 쪽에서
    #   둘이 같은 모습이 되고, 그것이 「모르는 것을 없다고 말하는」 결함이었다.
    for e, n, c in zip(edges, park, ecam, strict=True):
        e["park"] = n
        e["ecam"] = c

    # 결측(도로명 없음) · 0(도로명은 있고 찍힌 것이 없음)을 **발행물이 스스로 센다.**
    # 이 수가 있으면 「없음 110건」 같은 오독을 도구가 기계로 잡는다.
    pk_stat["null_edges"] = sum(1 for n in park if n is None)
    pk_stat["zero_edges"] = sum(1 for n in park if n == 0)
    ec_stat["null_edges"] = sum(1 for n in ecam if n is None)
    ec_stat["zero_edges"] = sum(1 for n in ecam if n == 0)

    out = {
        "crs": "EPSG:4326",
        "node_tol_m": NODE_TOL,
        "counts": {"nodes": len(nodes), "edges": len(edges), "self_loops": loops,
                   "oneway": ow_stat["oneway"], "oneway_dir_known": ow_stat["dir_known"],
                   # ★ 모름의 **사유별 수**(§367). 화면은 안 쓴다 — `navicheck` 가
                   #   읽어 「방향 모름」 래칫의 분모를 사유별로 가른다. 수를 문서에
                   #   안 적고 산출물이 들게 하는 그 규율이다(§246-2).
                   "oneway_nl": {k: ow_stat[k] for k in
                                 ("nl_twoway", "nl_none", "nl_split", "nl_absent")},
                   "turn_bans": len(turns),
                   "park_null": pk_stat["null_edges"], "park_zero": pk_stat["zero_edges"],
                   "ecam_null": ec_stat["null_edges"], "ecam_zero": ec_stat["zero_edges"],
                   # ★ **0 이 얼마나 약한가.** 원천에서 도로명이 안 나와 어느 구간에도
                   #   못 붙은 몫이다. 이것이 크면 `park`·`ecam` 의 0 은 「없다」가
                   #   아니라 「붙은 것 중에 없다」다 — 읽는 쪽이 그것을 알아야 한다.
                   "park_unplaced_rows": pk_stat["rows"] - pk_stat["matched"],
                   "ecam_unplaced_sites": ec_stat["sites"] - ec_stat["matched"]},
        "style": style,
        "terrain": _terrain(),
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
    print(f"  통행 규칙  일방통행 {ow_stat['oneway']} (방향 확정 {ow_stat['dir_known']})"
          f" · 회전 금지 {tr_stat['rules']}건 중 {tr_stat['mapped']} 을 그래프에")
    # ★ 2026-10-03 (§367). **모름의 사유를 가른다.** 종전에는 「양방향 N」 하나만
    #   찍어서, 56건이 왜 모름인지가 어디에도 없었다. 넷으로 가르면 다음에 무엇을
    #   고쳐야 하는지가 한 줄에 나온다 — 매칭 범위(`nl_none`)냐 버퍼 조율
    #   (`nl_split`)이냐 **원래 양방향**(`nl_twoway`)이냐 레이크(`nl_absent`)냐.
    print(f"    방향 모름 {ow_stat['oneway'] - ow_stat['dir_known']} 의 사유 —"
          f" 양방향 {ow_stat['nl_twoway']}"
          f" · 링크 없음 {ow_stat['nl_none']}"
          f" · 좁게↔넓게 갈림 {ow_stat['nl_split']}"
          f" · 레이크에 node_link 없음 {ow_stat['nl_absent']}")
    print(f"  주정차 단속  {pk_stat['rows']:,}건 중 도로명이 맞는 {pk_stat['matched']:,}건"
          f" · 도로 {pk_stat['roads']}"
          f" · 구간 결측 {pk_stat['null_edges']} · 0건 {pk_stat['zero_edges']}")
    print(f"  단속 카메라  {ec_stat['sites']}지점({ec_stat['rows']}방향) 중 도로명이 맞는"
          f" {ec_stat['matched']}지점 · 도로 {ec_stat['roads']}"
          f" · 구간 결측 {ec_stat['null_edges']} · 0지점 {ec_stat['zero_edges']}")
    if size > SIZE_MAX:
        raise SystemExit(
            f"★ navi_graph.json 이 상한을 넘었다 {size / 1024 / 1024:.1f}MB "
            f"> {SIZE_MAX / 1024 / 1024:.0f}MB. KEEP 을 줄이거나 PREC 를 낮춰라")
    if dmax > NODE_TOL:
        raise SystemExit(f"★ 노드 최대이동 {dmax:.3f}m 가 NODE_TOL 을 넘었다")


if __name__ == "__main__":
    no_args(__doc__)          # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    main()
