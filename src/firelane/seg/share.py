"""
seg/share.py — `#77` 가름 규칙. 한 폴리곤에 **이름이 다른 중심선이 둘 이상**이면 구간은 **자기 몫** 안에서만 폭을 잰다. (Zm56 · DECISIONS §588-2 · §593)

왜: 번길이 큰 폴리곤(본선 · 측도 · 광장)에 들어 있으면 법선이 벽~벽에서 **남의 몫까지 합쳐** 잰다 — 대장폭 4m 번길이 27.68m(`DM01876`)로 나온다.
어떻게: 근처 중심선(`ngii1k_center`)을 **도로명으로 묶고**(같은 이름은 한 길 — 쌍선을 안 가른다) 가장 가까운 묶음의 보로노이 몫으로 폴리곤을 자른다. 몫 ⊂ 폴리곤이라 **폭은 줄기만 한다.**

IN    ngii1k_center 링크(기하 · 도로명 · 도로폭) · 구간 기하 · 구간의 (도로명 · 대장폭)
OUT   자기 몫 폴리곤 — `WidthEngine` 이 그 안에서 다시 잰다
PARAM `CARVE_RATIO` · `CARVE_NEAR_M` · `CARVE_OWN_M` · `CARVE_FLOOR` (`seg/params.py`)
밖    **몫의 폭이 옳은가는 안 본다** — 걸러내는 쪽(후보 · 이름 불일치 · 먼 링크 · 하한)만 든다. 후보가 아니면 **현행 값을 그대로 둔다.**

★ 판정 규칙(`classify.py`)은 안 바뀐다 — 움직이는 것은 입력(폴리곤 몫)이다.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import shapely
from shapely.geometry import MultiPoint, Point
from shapely.strtree import STRtree

from firelane.seg.classify import CLEAR_M
from firelane.seg.params import CARVE_FLOOR, CARVE_NEAR_M, CARVE_OWN_M, CARVE_RATIO, RAY_M

SITE_STEP_M = 1.0          # 보로노이 점 간격 — 몫의 경계가 이 정도로 거칠다. 판정 문턱이 아니라 계산 해상도다


def _key(name) -> str:
    """도로명을 묶음 열쇠로. 빈 이름은 묶지 않는다(빈 문자열로 묶으면 이름 없는 서로 다른 길이 한 묶음이 된다)."""
    return name.replace(" ", "") if isinstance(name, str) and name.strip() else ""


class ShareCarver:
    """구간마다 「자기 몫」 폴리곤을 낸다. 후보가 아니거나 믿을 수 없으면 `None` — 그때 호출 쪽은 현행 값을 그대로 쓴다.

    links    [(LineString, 도로명 | None, 도로폭 | None)]
    ref_fn   구간 기하 → (구간의 도로명 | None, 대장폭 | None). 파이프라인은 `RoadNameIndex.match` 를 준다.
    """

    def __init__(self, links, ref_fn):
        self.geoms = [g for g, _, _ in links]
        self.names = [_key(n) for _, n, _ in links]
        self.widths = [w if isinstance(w, (int, float)) and w == w and w > 0 else None for _, _, w in links]
        self.tree = STRtree(self.geoms) if self.geoms else None
        self.ref_fn = ref_fn
        self.stats: Counter = Counter()

    # ── 가를까? ────────────────────────────────────────────────
    def _own(self, g):
        mid = g.interpolate(0.5, normalized=True)
        near = [int(i) for i in self.tree.query(mid.buffer(CARVE_OWN_M))]
        near = [i for i in near if self.geoms[i].distance(mid) <= CARVE_OWN_M]
        return min(near, key=lambda i: self.geoms[i].distance(mid)) if near else None

    def cell(self, g, wmin):
        """구간 `g`(폭 `wmin`)의 자기 몫 폴리곤. 가르지 않으면 `None`. 이유는 `stats` 에 센다."""
        if self.tree is None or wmin is None or wmin < CLEAR_M:
            self.stats["not_candidate"] += 1
            return None
        name, bt = self.ref_fn(g)
        own = self._own(g)
        if own is None:
            self.stats["no_own_link"] += 1
            return None
        own_name = self.names[own]
        if _key(name) and own_name and _key(name) != own_name:
            self.stats["name_mismatch"] += 1
            return None
        ref = max([v for v in (bt, self.widths[own]) if v], default=None)
        if ref is None or wmin < CARVE_RATIO * ref:
            self.stats["not_candidate"] += 1
            return None
        # 이름이 다른 묶음이 둘 이상 근처에 있는가. 빈 이름은 링크마다 따로 센다(이웃을 놓치는 쪽이 안전 — 안 가르면 현행 값이다).
        near = [int(i) for i in self.tree.query(g.buffer(CARVE_NEAR_M))]
        near = [i for i in near if self.geoms[i].distance(g) <= CARVE_NEAR_M]
        grp = {i: (self.names[i] or f"#{i}") for i in near}
        if own not in grp or len(set(grp.values())) < 2:
            self.stats["one_group"] += 1
            return None
        own_grp = grp[own]
        return self._voronoi(g, near, grp, own_grp)

    # ── 보로노이 몫 ────────────────────────────────────────────
    def _voronoi(self, g, near, grp, own_grp):
        win = g.buffer(RAY_M + CARVE_NEAR_M)
        pts, who = [], []
        for i in near:
            seg = self.geoms[i].intersection(win)
            if seg.is_empty:
                continue
            seg = shapely.segmentize(seg, SITE_STEP_M)
            for part in getattr(seg, "geoms", [seg]):
                for x, y in part.coords:
                    pts.append((x, y)); who.append(grp[i])
        if len({w for w in who}) < 2:
            self.stats["one_group"] += 1
            return None
        arr = np.asarray(pts)
        # 같은 좌표 점 중복 제거(보로노이가 중복 점을 싫어한다)
        _, first = np.unique(np.round(arr, 3), axis=0, return_index=True)
        first.sort()
        arr = arr[first]; who = [who[k] for k in first]
        cells = shapely.voronoi_polygons(MultiPoint(arr), extend_to=win)
        site_tree = STRtree([Point(p) for p in arr])
        own_cells = []
        for c in cells.geoms:
            for k in site_tree.query(c, predicate="contains"):
                if who[int(k)] == own_grp:
                    own_cells.append(c)
                    break
        if not own_cells:
            self.stats["no_cell"] += 1
            return None
        return shapely.make_valid(shapely.union_all(own_cells))

    def floor_ok(self, g, wmin_new):
        """몫으로 잰 폭이 자기 링크 `도로폭` 의 `CARVE_FLOOR` 배 이상인가 — 너무 좁게 잘랐으면 거절."""
        own = self._own(g)
        w = self.widths[own] if own is not None else None
        return w is None or wmin_new >= CARVE_FLOOR * w

    # ── 엔진에 거는 쪽 ─────────────────────────────────────────
    def refine(self, wx, s, res):
        """`wx._widths_once(s)` 의 결과 `res` 를 받아 **후보일 때만** 자기 몫 폴리곤 안에서 다시 재서 **더 좁은 값만** 돌려준다.

        후보가 아니거나 · 몫으로 값이 안 나오거나 · 더 넓거나(`not_narrower`) · 하한(`CARVE_FLOOR`)보다 좁으면 **`res` 를 그대로** 돌려준다 — 폭은 줄기만 한다.
        """
        if res[0] is None:
            return res
        cell = self.cell(s, res[0])
        if cell is None:
            return res
        saved = (wx.ngii1k_u, wx.ngii_u, wx.rw_u)
        try:
            wx.ngii1k_u, wx.ngii_u, wx.rw_u = (None if u is None else u.intersection(cell) for u in saved)
            alt = wx._widths_once(s)
        finally:
            wx.ngii1k_u, wx.ngii_u, wx.rw_u = saved
        for why, bad in (("no_value", alt[0] is None), ("not_narrower", alt[0] is not None and alt[0] >= res[0]),
                         ("floor", alt[0] is not None and not self.floor_ok(s, alt[0]))):
            if bad:
                self.stats[why] += 1
                return res
        self.stats["carved"] += 1
        return alt

    def report(self) -> str:
        return "가름 " + " · ".join(f"{k} {v}" for k, v in sorted(self.stats.items()))

    @classmethod
    def attach(cls, wx, center, rnx):
        """`ngii1k_center` 링크(기하 · 도로명 · 도로폭)로 만들어 `wx.carver` 에 건다. 중심선이 없으면 안 건다(현행 경로)."""
        if center is None or not len(center):
            return None

        def ref(g):
            n, _side, bt = rnx.match(g)
            return n, bt

        wx.carver = cls([(g, n, w) for g, n, w in zip(center.geometry, center["도로명"], center["도로폭"], strict=True)
                         if g is not None and not g.is_empty], ref)
        return wx.carver
