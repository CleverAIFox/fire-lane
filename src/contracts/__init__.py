"""
contracts — 파트 간 유일한 접점.

── 왜 있나 ─────────────────────────────────────────────────────
GIS · 비전 · 인프라 세 파트가 서로의 코드를 import 하지 않는다.
전부 이 패키지만 본다. 그래야 각 파트가 남의 진행 속도에 안 묶인다.

    firelane  ──┐
    cv        ──┼──▶  contracts  ◀── 여기만 공유한다
    api       ──┘

정본 서술은 `docs/MASTER.md §19` 다. 이 패키지는 그것의 **실행 가능한
사본**이며, 어긋나면 `tests/test_contract_vision.py` 가 잡는다.
`web/config.js` 가 `seg/params.py` 의 표시용 사본인 것과 같은 관계다(R3).

★ 여기에 계산을 넣지 않는다. 스키마와 검증만 둔다. 판정 로직이
  들어오면 임계값이 두 군데에 살게 되고, 실측 후 한쪽만 바뀐다.

IN    없음
OUT   없음 (형)
PARAM 없음
"""
from __future__ import annotations

from .vision import ObsSpec, VisionResult

__all__ = ["ObsSpec", "VisionResult"]

