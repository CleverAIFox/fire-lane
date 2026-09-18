"""
skeleton.py — 판정 뼈대 후보(NGII 1:1,000 중심선 하이브리드)와 현행 구간의 대조. 순수 함수.

IN    호출자가 준 GeoDataFrame — NGII 중심선 · road_link · 판정 범위 도형 (전부 EPSG:5186)
OUT   없음 (반환값만). 파일은 `tools/skeleton_compare.py` 가 쓴다
PARAM COVER_D 5m · GAP 2m · MATCH_R 8m · MATCH_ANGLE 25° · MATCH_SHARE 0.6 (DECISIONS §173-7 · §184)
      NGII_N 9점 · 거리 분류 1.5 / 5 / 15m · FAR_M 3m (R1 판 2)

★ 2026-09-17 (DECISIONS §184 · PLAN 「판정 뼈대를 NGII 1:1,000 측량 중심선으로 다시 세운다」).
  R1 은 **판정을 안 바꾼다.** 뼈대 후보를 옆에 세워 현행 1,281 구간이 어디로 가는지 표로 낸다.
  `segments.py` 는 이 모듈을 import 하지 않는다 — R3 에서 배선한다.

  하이브리드 = NGII 중심선 + (NGII 가 COVER_D 안에 없는 road_link 조각) + (막다른 끝에서 GAP 안의 접속선)
  → 노딩 → 차수 2 사슬 병합. 2026-09-17 사전 측정(저장소 밖 · 로그만 남음)의 확정값을 상수로 옮겼다.

★ 판 2 (2026-09-18). 판 1 의 「멀리」 · 「짝없음」 은 위치 증거로 못 썼다(§184-4).
  ① 멀리 — 매칭 엣지 거리(offset_m)를 썼다. 현행 구간은 road_link 위에 서고, NGII 가 5m 안에 없는 곳은
     하이브리드가 **바로 그 road_link 조각(fallback)** 으로 메운다. 그래서 NGII 에서 5~15m 옆에 선 구간이
     자기 자신과 매칭돼 거리 0 이 나왔다 — 측정이 구조적으로 0 을 냈다.
     → 거리는 src == ngii 엣지만 잰다(`ngii_distance`). 매칭 엣지는 폭 · 이름 · 쌍선 대조에만 쓴다.
  ② 짝없음 — 가장 많이 모인 엣지 하나의 비율(share)을 썼다. 뼈대는 교차점에서 끊기므로 교차점을
     지나는 구간은 두 엣지로 표가 갈려 60% 를 못 넘는다. 2026-09-18 재측정 — 짝없음 168 중
     160 이 표본점 60% 이상이 **어느** 엣지엔가 붙어 있었다(20m 미만은 32 뿐 — 길이 조건으로는 못 거른다).
     → 짝없음 = 어느 엣지에도 안 붙은 표본점이 40% 넘을 때(`cover`). share 는 칸으로 남긴다.
"""
from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

COVER_D = 5.0          # road_link 를 NGII 가 덮었다고 보는 거리(m). 8 은 옆 골목을 잡는다(§173-7)
GAP = 2.0              # 막다른 끝 → 다른 선 이음 한도(m). 5 는 건물관통 2 로 기각(§173-7)
MIN_PIECE = 2.0        # 이보다 짧은 폴백 조각은 버린다(버퍼 경계의 부스러기)
MATCH_R = 8.0          # 구간 표본점 → 뼈대 엣지 허용 거리(m) — 도로명 엄격 매칭 ±8m(§173-7)
MATCH_ANGLE = 25.0     # 방향 차 허용(도)
MATCH_SHARE = 0.6      # 표본점 중 한 엣지로 모인 비율이 이 이상이면 매칭
STEP = 5.0             # 구간 표본 간격(m)
FAR_M = 3.0            # NGII 선 거리 중앙이 max(이 값, NGII 도로폭/2) 보다 크면 위치 의심(판 2 — 차로 안 차이를 뺀다)
NGII_N = 9             # NGII 선 거리 표본점 수 — 구간 양끝 포함 등간격. 2026-09-17 미리보기(ngii_distance.csv)와 같은 정의
CLASS_EDGES = ((1.5, "A"), (5.0, "B"), (15.0, "C"))   # NGII 선 거리 중앙 상한(이하) → 분류. 넘으면 D
CLASS_LABEL = {"A": "A ≤1.5m 겹침", "B": "B 1.5~5m", "C": "C 5~15m NGII 옆", "D": "D >15m NGII 없음"}
PAIR_WMIN, PAIR_DMIN, PAIR_DMAX, PAIR_ANGLE = 6.0, 3.0, 25.0, 15.0


def _lines(geoms) -> list[LineString]:
    out: list[LineString] = []
    for g in geoms:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "LineString":
            out.append(g)
        elif g.geom_type in ("MultiLineString", "GeometryCollection"):
            out += _lines(g.geoms)
    return out


def bearing(line: LineString, at: float | None = None) -> float:
    """0~180° 방향. `at` 이 주어지면 그 거리 근처 1m 구간의 방향."""
    if at is None:
        (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    else:
        a, b = max(at - 1.0, 0.0), min(at + 1.0, line.length)
        p, q = line.interpolate(a), line.interpolate(b)
        x0, y0, x1, y1 = p.x, p.y, q.x, q.y
    return math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def fallback(road_link: list[LineString], ngii: list[LineString], d: float = COVER_D) -> list[LineString]:
    """NGII 가 d 안에 없는 road_link 조각 — NGII 가 간선을 쌍선 · 경계로만 그린 곳을 메운다."""
    cover = unary_union([g.buffer(d) for g in ngii]) if ngii else None
    out = []
    for g in road_link:
        rest = g.difference(cover) if cover is not None else g
        out += [p for p in _lines([rest]) if p.length >= MIN_PIECE]
    return out


def connectors(ngii: list[LineString], others: list[LineString], gap: float = GAP) -> list[LineString]:
    """NGII 막다른 끝에서 gap 안의 **다른** 선까지 잇는 짧은 선. 끝이 이미 닿아 있으면(≤1cm) 안 만든다."""
    ends: dict[tuple, int] = {}
    for g in ngii:
        for c in (g.coords[0], g.coords[-1]):
            k = (round(c[0], 2), round(c[1], 2))
            ends[k] = ends.get(k, 0) + 1
    pool = ngii + others
    tree = shapely.STRtree(pool)
    out = []
    for i, g in enumerate(ngii):
        for c in (g.coords[0], g.coords[-1]):
            if ends[(round(c[0], 2), round(c[1], 2))] > 1:
                continue
            p = Point(c)
            best, bd = None, gap + 1e-9
            for j in tree.query(p.buffer(gap)):
                if j == i:
                    continue
                dd = pool[j].distance(p)
                if 0.01 < dd <= bd:
                    best, bd = pool[j], dd
            if best is not None:
                q = best.interpolate(best.project(p))
                out.append(LineString([p, q]))
    return out


def merge_degree2(lines: list[LineString]) -> list[LineString]:
    """노딩(교차점에서 끊기) → 차수 2 사슬 병합. 막다른 끝 · 교차점 사이가 엣지 하나가 된다."""
    if not lines:
        return []
    noded = unary_union(lines)
    merged = shapely.line_merge(noded)
    return _lines([merged])


def build(ngii: gpd.GeoDataFrame, road_link: gpd.GeoDataFrame, keep,
          d: float = COVER_D, gap: float = GAP) -> gpd.GeoDataFrame:
    """판정 범위 `keep` 에 걸치는 선으로 하이브리드 뼈대를 세운다. 도형은 자르지 않는다(판정 범위 규칙과 같다)."""
    ng = _lines(ngii[ngii.intersects(keep)].geometry)
    rl = _lines(road_link[road_link.intersects(keep)].geometry)
    fb = fallback(rl, ng, d)
    cn = connectors(ng, fb, gap)
    edges = merge_degree2(ng + fb + cn)
    g = gpd.GeoDataFrame({"edge_id": [f"E{i:05d}" for i in range(len(edges))]}, geometry=edges, crs=5186)
    g["length_m"] = g.length.round(1)

    # ★ 병합하면 속성이 사라진다. 엣지 가운데 점에서 가까운 NGII 선의 속성을 붙이고 출처를 가른다.
    ngdf = ngii[ngii.intersects(keep)].reset_index(drop=True)
    ntree = shapely.STRtree(list(ngdf.geometry)) if len(ngdf) else None
    fbu = unary_union(fb) if fb else None
    src, attrs = [], {k: [] for k in ("도로폭", "도로명", "분리대유무")}
    for e in g.geometry:
        mid = e.interpolate(0.5, normalized=True)
        j = ntree.nearest(mid) if ntree is not None else None
        near = ngdf.iloc[int(j)] if j is not None and ngdf.geometry.iloc[int(j)].distance(mid) <= 0.5 else None
        if near is not None:
            src.append("ngii")
        elif fbu is not None and fbu.distance(mid) <= 0.5:
            src.append("fallback")
        else:
            src.append("connector")
        for k in attrs:
            attrs[k].append(near.get(k) if near is not None and k in ngdf.columns else None)
    g["src"] = src
    for k, v in attrs.items():
        g[k] = v
    g["도로폭"] = pd.to_numeric(g["도로폭"], errors="coerce")
    g["pair"] = parallel_pairs(g)
    return g


def parallel_pairs(edges: gpd.GeoDataFrame, wmin: float = PAIR_WMIN) -> list[bool]:
    """폭 wmin 이상 엣지 중 3~25m 옆에 거의 평행한 다른 엣지가 있는가 — 분리대 쌍선 후보(간선 이중 판정)."""
    geoms = list(edges.geometry)
    tree = shapely.STRtree(geoms)
    w = pd.to_numeric(edges.get("도로폭"), errors="coerce") if "도로폭" in edges else pd.Series([np.nan] * len(geoms))
    out = []
    for i, e in enumerate(geoms):
        if not (w.iloc[i] >= wmin):
            out.append(False)
            continue
        mid = e.interpolate(0.5, normalized=True)
        b0, hit = bearing(e, e.length / 2), False
        for j in tree.query(mid.buffer(PAIR_DMAX)):
            if j == i:
                continue
            o = geoms[j]
            dist = o.distance(mid)
            if PAIR_DMIN <= dist <= PAIR_DMAX and angle_diff(bearing(o, o.project(mid)), b0) < PAIR_ANGLE:
                hit = True
                break
        out.append(hit)
    return out


def _votes(seg: LineString, edges: list[LineString], tree: shapely.STRtree,
           r: float = MATCH_R, ang: float = MATCH_ANGLE) -> tuple[dict[int, list[float]], int]:
    """표본점마다 r 안 · 방향 ang 안의 가장 가까운 엣지에 한 표. (엣지 → 거리 목록, 표본점 수)."""
    n = max(3, int(seg.length // STEP) + 1)
    votes: dict[int, list[float]] = {}
    for t in np.linspace(0, seg.length, n):
        p = seg.interpolate(t)
        b = bearing(seg, t)
        best, bd = None, r + 1e-9
        for j in tree.query(p.buffer(r)):
            e = edges[j]
            dd = e.distance(p)
            if dd <= bd and angle_diff(bearing(e, e.project(p)), b) <= ang:
                best, bd = j, dd
        if best is not None:
            votes.setdefault(int(best), []).append(bd)
    return votes, n


def match(seg: LineString, edges: list[LineString], tree: shapely.STRtree,
          r: float = MATCH_R, ang: float = MATCH_ANGLE) -> tuple[int | None, float, float | None]:
    """구간 하나 → (엣지 번호, 모인 비율, 모인 점의 거리 중앙). 방향이 어긋난 점은 세지 않는다."""
    votes, n = _votes(seg, edges, tree, r, ang)
    if not votes:
        return None, 0.0, None
    j, ds = max(votes.items(), key=lambda kv: len(kv[1]))
    return j, round(len(ds) / n, 3), round(float(np.median(ds)), 2)


def coverage(seg: LineString, edges: list[LineString], tree: shapely.STRtree) -> float:
    """표본점 중 **어느** 엣지엔가 붙은 비율. 교차점에서 두 엣지로 갈린 구간도 1.0 이다(판 2 ②)."""
    votes, n = _votes(seg, edges, tree)
    return round(sum(len(v) for v in votes.values()) / n, 3)


def ngii_distance(seg: LineString, ngii_union, ngii: gpd.GeoDataFrame, ngii_tree: shapely.STRtree | None) -> dict:
    """NGII 측량 중심선(src == ngii)까지의 거리 — 위치 증거. fallback 은 현행 선과 같은 원천이라 뺀다(판 2 ①).

    표본은 양끝 포함 NGII_N 점 · 방향 조건 없음. 폭 · 이름은 구간 가운데 점에서 가장 가까운 NGII 엣지의 것.
    """
    if ngii_union is None or ngii_tree is None or len(ngii) == 0:
        return {"ngii_med": None, "ngii_max": None, "ngii_w": None, "ngii_name": None}
    pts = shapely.line_interpolate_point(seg, np.linspace(0.0, 1.0, NGII_N), normalized=True)
    d = shapely.distance(ngii_union, pts)
    j = int(ngii_tree.nearest(pts[NGII_N // 2]))
    w = ngii["도로폭"].iloc[j] if "도로폭" in ngii.columns else None
    name = ngii["도로명"].iloc[j] if "도로명" in ngii.columns else None
    return {"ngii_med": float(np.median(d)), "ngii_max": float(d.max()),
            "ngii_w": None if w is None or pd.isna(w) else float(w),
            "ngii_name": None if name is None or pd.isna(name) or str(name).strip() == "" else str(name)}


def dist_class(med) -> str | None:
    """NGII 선 거리 중앙 → A ≤1.5 · B ≤5 · C ≤15 · D. 거리가 없으면 None."""
    if med is None or pd.isna(med):
        return None
    for hi, k in CLASS_EDGES:
        if float(med) <= hi:
            return k
    return "D"


def far_limit(ngii_w) -> float:
    """「멀리」 문턱 — 넓은 간선은 차로 안에서도 중심선과 몇 m 벌어진다. 도로폭 절반 아래는 위치 차이로 안 친다."""
    if ngii_w is None or pd.isna(ngii_w):
        return FAR_M
    return max(FAR_M, float(ngii_w) / 2.0)


def suspect(row: dict) -> str:
    """위치 의심 사유. 빈 문자열이면 의심 없음. 판정을 바꾸지 않는다 — 사람이 볼 목록을 고른다."""
    why = []
    # ★ 판 2 ② — share(한 엣지)가 아니라 cover(어느 엣지든). cover 칸이 없는 옛 행은 share 로 본다.
    cov = row.get("cover", row.get("share", 0))
    if (cov if cov is not None and not pd.isna(cov) else 0) < MATCH_SHARE:
        why.append("짝없음")
    ew, wm = row.get("edge_width"), row.get("width_min_m")
    if ew is not None and wm is not None and not (pd.isna(ew) or pd.isna(wm)) and abs(float(ew) - float(wm)) >= 2.0:
        why.append("폭불일치")
    # ★ 폭불일치만으로는 약하다 — width_min_m 은 구간 안 **최소** 통과폭이고 NGII 도로폭은 대표 폭이라
    #   좁아지는 골목마다 2m 넘게 벌어진다. 매칭 엣지가 3m 넘게 떨어져 있으면 "엉뚱한 자리에서 쟀다" 쪽 증거라 따로 단다.
    #   2026-09-17 r_eda2 — 동계천로 needs_cv 0.97m 가 10.1m 옆 NGII 도로폭 13.9m 였다.
    # ★ 판 2 ① — 매칭 엣지 거리(offset_m)가 아니라 NGII 선 거리(ngii_med). D(>15m)는 멀리가 아니다 —
    #   그 자리에 측량 중심선이 없다는 뜻이지 옆에 섰다는 증거가 아니다. 「측량밖」 으로 따로 단다.
    med = row.get("ngii_med")
    k = dist_class(med)
    if k == "D":
        why.append("측량밖")
    elif k is not None and float(med) > far_limit(row.get("ngii_w")):
        why.append("멀리")
    if (row.get("bldg_ngii_m") or 0) > 1.0 and (row.get("edge_bldg_ngii_m") or 0) <= 0.5:
        why.append("건물관통")
    if row.get("edge_pair"):
        why.append("쌍선")
    return "·".join(why)


def priority(suspect_text: str) -> int:
    """사람이 볼 순서. 위치 증거(멀리 · 건물관통)가 폭 차이보다 앞선다. 0 은 의심 없음."""
    w = {"멀리": 8, "건물관통": 4, "폭불일치": 2, "짝없음": 1, "쌍선": 1, "측량밖": 1}
    return sum(v for k, v in w.items() if k in (suspect_text or "").split("·"))


def compare(segments: gpd.GeoDataFrame, edges: gpd.GeoDataFrame,
            ngii_bldg: gpd.GeoDataFrame | None = None, juso_bldg: gpd.GeoDataFrame | None = None) -> pd.DataFrame:
    """현행 구간마다 매칭 엣지 · 이동 거리 · 두 건물 원천 관통 · 폭 대조 · 의심 사유."""
    eg = list(edges.geometry)
    tree = shapely.STRtree(eg)
    ng = edges[edges["src"] == "ngii"].reset_index(drop=True) if "src" in edges.columns else edges.iloc[0:0]
    ng_union = shapely.union_all(list(ng.geometry)) if len(ng) else None
    ng_tree = shapely.STRtree(list(ng.geometry)) if len(ng) else None
    nb = unary_union(list(ngii_bldg.geometry.buffer(0))) if ngii_bldg is not None and len(ngii_bldg) else None
    jb = unary_union(list(juso_bldg.geometry.buffer(0))) if juso_bldg is not None and len(juso_bldg) else None
    rows = []
    for _, s in segments.iterrows():
        g = s.geometry
        votes, n = _votes(g, eg, tree)
        if votes:
            jj, ds = max(votes.items(), key=lambda kv: len(kv[1]))
            j, share, off = jj, round(len(ds) / n, 3), round(float(np.median(ds)), 2)
        else:
            j, share, off = None, 0.0, None
        cov = round(sum(len(v) for v in votes.values()) / n, 3)
        e = edges.iloc[j] if j is not None else None
        row = {
            "seg_uid": s.get("seg_uid"), "seg_id": s.get("seg_id"), "road_name": s.get("road_name"),
            "verdict": s.get("verdict"), "width_min_m": s.get("width_min_m"), "width_src": s.get("width_src"),
            "length_m": s.get("length_m"),
            "edge_id": e["edge_id"] if e is not None else None, "share": share, "cover": cov, "offset_m": off,
            "edge_src": e["src"] if e is not None else None,
            "edge_width": e["도로폭"] if e is not None else None,
            "edge_name": e["도로명"] if e is not None else None,
            "edge_pair": bool(e["pair"]) if e is not None else False,
            "bldg_ngii_m": round(g.intersection(nb).length, 1) if nb is not None else None,
            "bldg_juso_m": round(g.intersection(jb).length, 1) if jb is not None else None,
            "edge_bldg_ngii_m": round(e.geometry.intersection(nb).length, 1) if (e is not None and nb is not None) else None,
        }
        row.update(ngii_distance(g, ng_union, ng, ng_tree))
        row["dist_class"] = dist_class(row["ngii_med"])
        rn = s.get("road_name")
        row["same_name"] = bool(row["ngii_name"] is not None and rn is not None and not pd.isna(rn)
                                and str(rn) == row["ngii_name"])
        row["suspect"] = suspect(row)
        row["priority"] = priority(row["suspect"])
        rows.append(row)
    return pd.DataFrame(rows)
