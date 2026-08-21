#!/usr/bin/env python3
"""
seg/basisno.py — 구간 라벨을 도로명주소 기초번호로 만든다.

── 왜 필요한가 ────────────────────────────────────────────────
`road_name` 만으로는 구간을 지목할 수 없다.

    동계천로          88 구간
    동명로            68 구간
    필문대로205번길   33 구간

`publish_web.py` 의 `seg_no` 는 `(road_name, _oy, _ox)` 정렬 순번이라
노딩이 하나만 바뀌어도 전부 밀린다 — `seg_id` 가 불변 키가 아닌 것과
같은 이유다(MASTER §5). '서/중/동' 같은 어휘도 우리가 만든 말이라
소방관이 못 알아듣는다.

── 기초구간이 정본이다 ────────────────────────────────────────
`juso_elctrnmap` 의 `TL_SPRD_INTRVL`(기초구간) 에 도로명주소법의
기초번호가 **값으로** 들어 있다.

    ODD_BSI_MN  홀수측 본번        RDS_MAN_NO  도로구간 관리번호
    EVE_BSI_MN  짝수측 본번        BSI_INT_SN  기초구간 일련번호

★ 2026-08-21 재작성. 이전 판은 도로선을 `linemerge` 해서 기점부터
  누적거리를 재고 20m 마다 번호를 매겼다. 그 방식은 두 가지가 깨졌다.

    1. `road_link` 가 스코프로 클리핑돼 본선의 진짜 기점이 선 밖에 있다.
       무등로 +420 · 중앙로 +186 처럼 일관되게 밀렸다(동일부호 100%).
    2. 클리핑으로 선이 끊긴 도로가 181개였고, 가장 긴 성분만 기준으로
       삼으면 나머지 조각의 번호가 어긋났다(제봉로 IQR 150).

  `poi_store` 로 오프셋을 추정해 1번은 덮었지만 2번은 못 덮었다.
  그리고 보정에 쓴 자료는 그 순간부터 검증 수단이 아니다(MASTER §4).
  정본이 raw 안에 있는데 추정으로 우회할 이유가 없다.

  겹침 길이로 붙이는 방식은 `roadname.RoadNameIndex` 와 동일하다.
  세그먼트는 원본 선 위에 그대로 놓여 있으므로 추정할 필요가 없다.
"""
from __future__ import annotations

from shapely.strtree import STRtree

# 겹침 길이가 구간 길이의 이 비율 미만이면 매칭 실패로 본다.
MATCH_MIN = 0.30

# 매칭에 쓰는 띠 폭(편측). 기초구간은 도로중심선 위에 놓여 있다.
BAND = 1.0


def _num(v):
    """'41' → 41. 빈 값·비정수는 None."""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


class BasisIntervalIndex:
    """기초구간 공간 인덱스. 겹침 길이로 기초번호를 고른다.

    한 세그먼트가 기초구간 여러 개에 걸치므로 시작·끝 양쪽을 본다.
    `label()` 이 '필문대로205번길 11-17' 형태를 만든다.
    """

    def __init__(self, geoms, odd, eve):
        self.geo = list(geoms)
        self.odd = [_num(x) for x in odd]
        self.eve = [_num(x) for x in eve]
        self.tree = STRtree(self.geo) if self.geo else None

    @classmethod
    def from_gdf(cls, intrvl):
        """`road_intrvl` GeoDataFrame 에서 만든다."""
        need = ("ODD_BSI_MN", "EVE_BSI_MN")
        miss = [c for c in need if c not in intrvl.columns]
        if miss:
            raise KeyError(f"기초구간에 {miss} 가 없다. 보유: {list(intrvl.columns)}")
        return cls(list(intrvl.geometry),
                   list(intrvl["ODD_BSI_MN"]), list(intrvl["EVE_BSI_MN"]))

    def _hits(self, g):
        """세그먼트에 겹치는 기초구간을 (겹침길이, 홀수번호) 로."""
        if self.tree is None:
            return []
        band = g.buffer(BAND)
        out = []
        for k in self.tree.query(band):
            ov = self.geo[k].intersection(band)
            if ov.is_empty or ov.length <= 0:
                continue
            n = self.odd[k] if self.odd[k] is not None else self.eve[k]
            if n is None:
                continue
            out.append((ov.length, n, self.geo[k].project(g.interpolate(0.0))))
        return out

    def range_for(self, g) -> tuple[int | None, int | None]:
        """세그먼트가 걸치는 기초번호 구간 (시작, 끝).

        겹침 총량이 세그먼트 길이의 MATCH_MIN 미만이면 판단하지 않는다.
        """
        hits = self._hits(g)
        if not hits:
            return None, None
        if sum(h[0] for h in hits) < g.length * MATCH_MIN:
            return None, None
        nums = sorted(n for _, n, _ in hits)
        return nums[0], nums[-1]

    def label(self, road_name, g) -> str | None:
        """사람이 읽는 구간 이름. '필문대로205번길 11-17'.

        기초번호를 못 찾으면 도로명만 준다. 없는 번호를 지어내지 않는다.
        """
        if road_name is None:
            return None
        s, e = self.range_for(g)
        if s is None:
            return str(road_name)
        return f"{road_name} {s}" if s == e else f"{road_name} {s}-{e}"
