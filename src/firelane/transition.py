"""
transition.py — 옛 구간 → 새 구간 **전이표**. 순수 함수.

IN    호출자가 준 GeoDataFrame 둘 (전부 EPSG:5186 미터)
OUT   없음 (반환값만). 파일은 `tools/transition.py` 가 쓴다
PARAM STEP 5m · MATCH_R 8m · MATCH_ANGLE 25° · MIN_SHARE 0.2 · FALLBACK_R 15m (DECISIONS §187)

★ 2026-09-18 (DECISIONS §187 · PLAN 「판정 뼈대를 NGII 1:1,000 측량 중심선으로 다시 세운다」 R2).
  R3 가 뼈대를 갈면 **구간이 다른 자리에서 잘린다.** 그래서 `baseline.py diff` 의 1:1 중점 최근접
  매칭은 R3 전후에 성립하지 않는다 — 한 구간이 둘로 쪼개지면(1:N) 중점이 어느 쪽에도 안 맞고,
  둘이 하나로 합쳐지면(N:1) 한쪽이 임의로 버려진다. 그 상태로 판정 전이표를 찍으면
  **판정이 움직인 것과 경계가 움직인 것을 구별할 수 없다.**

  여기서는 한 엣지만 고르지 않는다. 표본점이 흩어진 대로 **전부** 남기고 비율(share)을 적는다.
  판정 전이는 구간 수가 아니라 **길이(m)** 로 센다 — 1:N 을 구간 수로 세면 옛 구간 하나가
  여러 번 세어져 합이 안 맞는다.

★ 이 모듈은 판정을 안 만든다. 두 산출물을 읽고 표를 낼 뿐이라 `segments.py` 가 import 하지 않는다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString

from firelane.skeleton import angle_diff, bearing

STEP = 5.0             # 옛 구간 표본 간격(m) — skeleton.STEP 과 같다
MATCH_R = 8.0          # 표본점 → 새 선 허용 거리(m) — skeleton.MATCH_R 과 같다
MATCH_ANGLE = 25.0     # 방향 차 허용(도) — skeleton.MATCH_ANGLE 과 같다
MIN_SHARE = 0.2        # 이 비율 미만으로 걸친 대응은 버린다(교차부에서 한두 점만 스치는 것)
FALLBACK_R = 15.0      # 방향 매칭이 0 일 때 중점 최근접 폴백(m) — baseline.diff 의 tol 과 같다


def _line(g):
    if g is None or g.is_empty:
        return None
    if g.geom_type == "LineString":
        return g
    m = shapely.line_merge(g)
    if m.geom_type == "LineString":
        return m
    parts = [p for p in getattr(m, "geoms", []) if p.geom_type == "LineString"]
    return max(parts, key=lambda p: p.length) if parts else None


def shares(old: LineString, new: list[LineString], tree: shapely.STRtree,
           r: float = MATCH_R, ang: float = MATCH_ANGLE) -> dict[int, float]:
    """옛 구간의 표본점이 어느 새 구간에 얼마나 붙었나. **한 엣지만 고르지 않는다.**

    표본점마다 r 안 · 방향 ang 안에서 가장 가까운 새 구간 하나에 한 표. 표를 비율로 돌려준다.
    합이 1 미만이면 그만큼은 어디에도 안 붙은 것이다(그 길이가 소멸 후보).

    ★ 표본은 **칸 가운데**다 — 양끝을 안 찍는다(`skeleton.match` 와 다른 점). 끝점은 이웃 구간과
      공유하는 노드라 거리가 0 이고, 이어지는 구간은 방향도 같다. 양끝을 찍으면 **같은 산출물끼리
      대조해도** 끝 표본이 이웃에게 한 표씩 가서 1:1 이 깨진다 — 2026-09-18 항등 자기검사에서
      1,281 중 348 이 그 모양이었다. 짧은 구간일수록 한 표의 비중이 커서 MIN_SHARE 로도 못 거른다.
    """
    n = max(3, int(old.length // STEP) + 1)
    votes: dict[int, int] = {}
    for t in (np.arange(n) + 0.5) / n * old.length:
        p = old.interpolate(t)
        b = bearing(old, t)
        best, bd = None, r + 1e-9
        for j in tree.query(p.buffer(r)):
            e = new[j]
            d = e.distance(p)
            if d <= bd and angle_diff(bearing(e, e.project(p)), b) <= ang:
                best, bd = int(j), d
        if best is not None:
            votes[best] = votes.get(best, 0) + 1
    return {j: round(v / n, 3) for j, v in votes.items()}


def build(old: pd.DataFrame, new: pd.DataFrame, uid_col: str = "seg_uid",
          verdict_col: str = "verdict", min_share: float = MIN_SHARE) -> pd.DataFrame:
    """옛 구간마다 (새 구간, 비율) 행들. 대응이 없으면 new 칸이 비고 `match` 가 `소멸` 이다.

    `match` — `방향`(8m · 25°) · `중점`(방향 0 일 때 15m 폴백) · `소멸`
    """
    ng = [_line(g) for g in new.geometry]
    keep = [i for i, g in enumerate(ng) if g is not None]
    geoms = [ng[i] for i in keep]
    tree = shapely.STRtree(geoms)
    mids = np.array([[g.interpolate(0.5, normalized=True).x,
                      g.interpolate(0.5, normalized=True).y] for g in geoms]) if geoms else np.zeros((0, 2))
    rows = []
    for _, s in old.iterrows():
        g = _line(s.geometry)
        if g is None:
            continue
        base = {"old_uid": s.get(uid_col), "old_verdict": s.get(verdict_col),
                "old_road": s.get("road_name"), "old_len_m": round(g.length, 1)}
        sh = {k: v for k, v in shares(g, geoms, tree).items() if v >= min_share} if geoms else {}
        kind = "방향"
        if not sh and geoms:
            # ★ 방향이 0 이면 통째로 버리지 않는다 — 뼈대가 갈리면 같은 길이 몇 도 돌 수 있다.
            #   `baseline.diff` 와 같은 중점 최근접 15m 를 폴백으로 둔다. 붙었다는 증거는 약하므로 칸에 적는다.
            m = g.interpolate(0.5, normalized=True)
            d = np.hypot(mids[:, 0] - m.x, mids[:, 1] - m.y)
            j = int(d.argmin())
            if d[j] <= FALLBACK_R:
                sh, kind = {j: 1.0}, "중점"
        if not sh:
            rows.append({**base, "new_uid": None, "new_verdict": None, "share": 0.0,
                         "len_share_m": 0.0, "same_uid": False, "match": "소멸"})
            continue
        for j, v in sorted(sh.items(), key=lambda kv: -kv[1]):
            t = new.iloc[keep[j]]
            rows.append({**base, "new_uid": t.get(uid_col), "new_verdict": t.get(verdict_col),
                         "share": v, "len_share_m": round(g.length * v, 1),
                         "same_uid": bool(s.get(uid_col) is not None and s.get(uid_col) == t.get(uid_col)),
                         "match": kind})
    t = pd.DataFrame(rows)
    added = set(new[uid_col]) - set(t.loc[t.new_uid.notna(), "new_uid"]) if len(t) else set(new[uid_col])
    for u in sorted(x for x in added if x is not None):
        r = new.loc[new[uid_col] == u].iloc[0]
        g = _line(r.geometry)
        t = pd.concat([t, pd.DataFrame([{
            "old_uid": None, "old_verdict": None, "old_road": None, "old_len_m": 0.0,
            "new_uid": u, "new_verdict": r.get(verdict_col), "share": 0.0,
            "len_share_m": 0.0, "same_uid": False, "match": "신설",
            "new_len_m": round(g.length, 1) if g is not None else 0.0}])], ignore_index=True)
    return t


def cardinality(t: pd.DataFrame) -> pd.Series:
    """옛 구간마다 1:1 · 1:N · N:1 · N:M · 소멸. 새 구간을 몇이 나눠 갖는지까지 본다."""
    m = t[t.match.isin(["방향", "중점"])]
    per_old = m.groupby("old_uid").new_uid.nunique()
    per_new = m.groupby("new_uid").old_uid.nunique()
    out = {}
    for u, k in per_old.items():
        mx = m.loc[m.old_uid == u, "new_uid"].map(per_new).max()
        out[u] = f"{'1' if mx <= 1 else 'N'}:{'1' if k <= 1 else 'N'}"
    for u in t.loc[t.match == "소멸", "old_uid"]:
        out[u] = "소멸"
    return pd.Series(out, dtype=object)


def verdict_flow(t: pd.DataFrame) -> pd.DataFrame:
    """판정 전이 — **길이(m) 가중**. 구간 수로 세면 1:N 에서 옛 구간이 여러 번 세어진다."""
    m = t[t.match.isin(["방향", "중점"])]
    order = ["clear", "needs_cv", "blocked", "unknown"]
    f = m.pivot_table(index="old_verdict", columns="new_verdict", values="len_share_m",
                      aggfunc="sum", fill_value=0.0)
    f = f.reindex(index=order, columns=order, fill_value=0.0).round(0).astype(int)
    f["소멸"] = t[t.match == "소멸"].groupby("old_verdict").old_len_m.sum().reindex(order).fillna(0).round(0).astype(int)
    return f


def summarize(t: pd.DataFrame, n_old: int, n_new: int) -> dict:
    card = cardinality(t)
    m = t[t.match.isin(["방향", "중점"])]
    cov = m.groupby("old_uid").share.sum()
    return {
        "old": n_old, "new": n_new,
        "cardinality": {k: int(v) for k, v in card.value_counts().sort_index().items()},
        "gone": int((card == "소멸").sum()),
        "added": int((t.match == "신설").sum()),
        "same_uid": int(m.same_uid.sum()),
        "same_uid_rate": round(float(100 * m.same_uid.sum() / max(1, n_old)), 1),
        "fallback_mid": int((t.match == "중점").sum()),
        "len_old_m": round(float(t.drop_duplicates("old_uid").old_len_m.sum()), 1),
        "len_matched_m": round(float(m.len_share_m.sum()), 1),
        "cover_median": round(float(cov.median()), 3) if len(cov) else 0.0,
    }
