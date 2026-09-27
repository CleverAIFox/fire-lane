"""
passthrough.py — 읽지 않는 갈래. 존재만 기록한다.  (PLAN §1 #132)

IN    없다 — 실물을 열지 않는다
OUT   `status: SKIP` 계보 조각
밖   **왜 SKIP 인지는 대장이 든다.** 여기는 7줄이고 앞으로도 7줄이다 —
      이 갈래가 데이터셋의 36%(26/72)를 들면서 코드가 안 바뀌는 것이
      샤드 축 분리의 이득 전부다(DECISIONS §274-3).
"""
from __future__ import annotations

from firelane.read.ctx import Ctx


def read_raw_only(c: Ctx):
    """kind "raw_only" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    rec = c.rec
    # 다른 스크립트가 raw 를 직접 읽는 경우다(예: terrain.py 의 DEM).
    # 여기서 변환하지 않으므로 SKIP 으로 남긴다. FAIL 이 아니다.
    rec |= {"status": "SKIP", "features": "", "geom": [],
            "note": "raw_only — 별도 스크립트가 직접 읽는다", "outputs": []}
    return rec
