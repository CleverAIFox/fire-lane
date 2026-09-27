#!/usr/bin/env python3
"""
localgeo.py — 동명동 국소 평면 근사. **좌표 상수의 집이 여기 하나다.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24 (PLAN §13 W12-1 · DECISIONS §239). `tools/kpi.py` ·
  `tools/bridge_audit.py` · `tools/its_linkmap.py` 가 아래 세 줄을
  **글자까지 같게** 박고 있었다 —

      LAT0 = 35.151
      MX = 111320 * math.cos(math.radians(LAT0))
      MY = 110574

  셋 다 거리·근접 판정에 쓴다(진입 실패율 KPI · 다리 실측 우선순위 ·
  ITS 링크 대조). 중심 위도를 바꾸면 **세 도구가 각자 다른 좌표계로 거리를
  재면서 아무도 안 운다.** 셋 다 배선 면제라 경보도 없다 — 2족(정본이 둘).

★ `src/firelane/seg/params.py` 로 올리지 않았다. 그 파일은 **판정 지문**
  안이라(`code_closure("firelane.segments")` 22파일) 상수 하나를 더해도
  코드 지문이 움직이고 재잠금이 따라온다. 이 값은 판정에 안 든다 —
  조사 도구 셋만 쓴다. **정본을 하나로 만드는 것과 지문을 흔드는 것은
  다른 일이고, 둘을 섞으면 재잠금이 값싸 보이기 시작한다.**

── 무엇이 아닌가 ───────────────────────────────────────────────
★ **투영이 아니다.** 제대로 된 변환은 EPSG:5186 이고 `src/firelane` 이 쓴다.
  여기 있는 것은 **한 동네 크기에서만 성립하는 어림**이다 — 위도 상수
  하나로 미터를 만들므로, 동명동 밖으로 나가면 오차가 커진다.

IN    없음 (상수)
OUT   없음 (상수와 거리 함수)
PARAM 없음 · 인자 없이 치면 자기검사
밖    **좌표계 변환은 안 한다.** 5179 ↔ 5186 ↔ 4326 은 `pyproj` 가 하고
      파이프라인이 든다. 여기서 드는 것은 **4326 두 점 사이 거리** 하나다.
      그리고 고도·측지선은 안 본다 — 평면 근사다.
"""
from __future__ import annotations

import math

#: 동명동 중심 위도. 국소 평면 근사의 기준점이다.
LAT0 = 35.151
#: 경도 1도의 미터. 위도에 따라 줄어든다.
MX = 111320 * math.cos(math.radians(LAT0))
#: 위도 1도의 미터. 위도에 거의 안 변한다.
MY = 110574


def meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """4326 두 점 사이 거리(m). 국소 평면 근사."""
    return math.hypot((lon1 - lon2) * MX, (lat1 - lat2) * MY)


def selftest() -> int:
    """근사가 **뜻하는 크기**를 내는가. 상수를 잘못 고치면 여기서 운다."""
    bad = []
    if not (90_000 < MX < 95_000):
        bad.append(f"MX={MX:.0f} — 위도 35도에서 경도 1도는 9만m 대다")
    if not (110_000 < MY < 111_500):
        bad.append(f"MY={MY} — 위도 1도는 11만m 대다")
    # 경도 0.001도 ≈ 91m · 위도 0.001도 ≈ 111m
    d = meters(126.920, 35.151, 126.921, 35.151)
    if not (85 < d < 95):
        bad.append(f"경도 0.001도가 {d:.1f}m — 91m 근처여야 한다")
    d = meters(126.920, 35.151, 126.920, 35.152)
    if not (105 < d < 116):
        bad.append(f"위도 0.001도가 {d:.1f}m — 111m 근처여야 한다")
    if meters(126.92, 35.15, 126.92, 35.15) != 0:
        bad.append("같은 점의 거리가 0 이 아니다")
    if bad:
        print("★ 국소 평면 근사가 깨졌다 — " + " · ".join(bad))
        return 1
    print(f"localgeo OK — LAT0 {LAT0} · 경도 1도 {MX:.0f}m · 위도 1도 {MY}m")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
