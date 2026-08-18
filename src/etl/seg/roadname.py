#!/usr/bin/env python3
"""
seg/roadname.py — 도로명 되붙이기.

노딩하면 원본 속성이 끊긴다. `seg_id`(DM00001)만 보이면 사람이 어느 골목인지
알 수 없으므로 도로선에서 이름을 되찾아온다.

2026-08-18 Stage 2 에서 `segments.py` 의 `main()` 밖으로 꺼냈다. 원래는
`_rn_geo` · `_rn_nm` · `_rn_dpn` · `_rn_bt` · `_rn_tree` 다섯 개의 로컬을
`road_name()` 이 폐포로 잡고 있었다. 다섯 개가 항상 같이 움직이므로
하나의 인덱스 객체다 — 흩어져 있을 이유가 없었다.

로직은 한 글자도 바꾸지 않았다. `tools/golden.py` 로 산출물 동일을 증명한다.

★ 생성자가 GeoDataFrame 이 아니라 리스트를 받는다.
  geopandas 없이 단위 테스트할 수 있어야 하기 때문이다. GeoDataFrame 에서
  만들 때는 `from_gdf()` 를 쓴다.
"""
from __future__ import annotations

from shapely.strtree import STRtree

# 겹침 길이가 구간 길이의 이 비율 미만이면 매칭 실패로 본다.
MATCH_MIN = 0.5

# 매칭에 쓰는 띠 폭(편측). 세그먼트는 원본 선 위에 그대로 놓여 있으므로 좁아도 된다.
BAND = 0.5


class RoadNameIndex:
    """도로선 공간 인덱스. 겹침 길이로 이름을 고른다."""

    def __init__(self, geoms, names, dpns, bts):
        self.geo = list(geoms)
        self.nm = list(names)
        # RDS_DPN_SE 0=주도로 1=부속(측도·측면도로).
        # 중앙로(본선 25m) 옆에 붙은 폭 1.3m 통로가 같은 도로명을 갖는다.
        # 이름만 보면 대로인데 폭이 1m 로 나와 오산출로 오해하기 쉽다.
        self.dpn = list(dpns)
        self.bt = list(bts)
        self.tree = STRtree(self.geo) if self.geo else None

    @classmethod
    def from_gdf(cls, road):
        """`road_link` GeoDataFrame 에서 만든다. RN 이 빈 행은 버린다."""
        r = road[road["RN"].notna()].copy()
        return cls(list(r.geometry), list(r["RN"]),
                   list(r["RDS_DPN_SE"].astype(str)), list(r["ROAD_BT"]))

    def match(self, g):
        """겹침 길이가 가장 긴 도로선의 (RN, RDS_DPN_SE, ROAD_BT).

        세그먼트는 road_link 를 교차점에서 자른 조각이므로 원본 선 위에
        그대로 놓여 있다. 추정할 필요가 없다.
        중점 최근접 방식은 교차로에서 옆 도로를 집는다.
        """
        if self.tree is None:
            return None, None, None
        band = g.buffer(BAND)
        best, best_len, best_k = None, 0.0, None
        for k in self.tree.query(band):
            ov = self.geo[k].intersection(band)
            if ov.is_empty:
                continue
            if ov.length > best_len:
                best, best_len, best_k = self.nm[k], ov.length, k
        if best is None or best_len < g.length * MATCH_MIN:
            return None, None, None
        return best, self.dpn[best_k], self.bt[best_k]

    def nearest(self, geom, radius: float = 15.0):
        """반경 안에서 가장 가까운 도로선의 이름. 진단 출력용이다.

        `match` 와 달리 겹침을 요구하지 않는다. 병렬 엣지처럼 "대충 어디쯤"
        만 알면 되는 자리에 쓴다. 없으면 None.
        """
        if self.tree is None:
            return None
        q = self.tree.query(geom.buffer(radius))
        return min(((self.geo[k].distance(geom), self.nm[k]) for k in q),
                   default=(None, None))[1]
