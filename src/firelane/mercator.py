"""
mercator.py — 웹 메르카토르 ↔ 경위도. **순수 수식. I/O 없음.**

★ 2026-09-13. `ortho` · `terrain` 이 같은 역변환을 한 벌씩 들고 있었다
  (56노드). 타일 경계를 `view.json` 에 적는 코드가 양쪽에 있었고,
  한쪽만 고치면 배경과 지형의 경계가 조용히 갈린다.

IN    없음
OUT   없음 (순수 함수)
"""
from __future__ import annotations

import math

R = 6378137.0


def to_lonlat(mx: float, my: float) -> tuple[float, float]:
    """웹 메르카토르 미터 → (경도, 위도) 도."""
    return (mx / R * 180 / math.pi,
            (2 * math.atan(math.exp(my / R)) - math.pi / 2) * 180 / math.pi)
