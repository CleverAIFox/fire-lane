#!/usr/bin/env python3
"""
localgeo.py — 국소 평면 근사를 **도구 쪽 이름으로 넘긴다.**

★ 2026-10-11 (DECISIONS §469). 정본이 `src/firelane/localplane.py` 로 올라갔다.
  여기 두면 `src/firelane` 쪽이 계층 때문에 import 할 수 없고, 그래서
  `publish_context` 가 제 상수를 들고 있었다 — 위도 1도가 저장소에서 세 수가
  된 뿌리다. **정본을 못 쓰게 두면 사본이 생긴다.**

★ 이 파일은 **이름만 남긴다.** 도구 쪽 소비자 열하나가 `from localgeo import …`
  를 쓰고 그 줄을 다 고치는 것은 이 판의 일이 아니다(옮기는 판과 고치는 판을
  섞으면 무엇이 무엇을 깨뜨렸는지 못 가른다).

★ 왜 생겼는가 · 왜 `seg/params.py` 가 아닌가 — **그 역사는 정본의 머리말**이
  든다. 여기 베끼면 그 글이 낡는다(그리고 베낀 상수가 독점 검사를 울린다).

IN    없음 (상수)
OUT   없음 (상수와 거리 함수)
PARAM 없음 · 인자 없이 치면 자기검사
밖    **계산을 안 한다.** 전부 `firelane.localplane` 이 한다.
"""

from __future__ import annotations

# ★ 2026-10-11 (DECISIONS §469). **상수의 집이 `src` 로 올라갔다.** 여기 두면
#   `src/firelane` 쪽이 계층 때문에 import 할 수 없고, 그래서 `publish_context`
#   가 제 상수를 들고 있었다(위도 110,540 — 세 번째 값). 정본을 못 쓰게 두면
#   사본이 생긴다. 이 파일은 **이름만 남겨 넘긴다** — 도구 쪽 소비자 열하나가
#   `from localgeo import ...` 를 쓰고 그 줄을 다 고치는 것은 이 판의 일이 아니다.
from firelane import localplane as LP
from firelane.cli import no_args
from firelane.localplane import LAT0, MX, MY, metres

__all__ = ["LAT0", "MX", "MY", "meters", "metres"]


def meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """4326 두 점 사이 거리(m). 국소 평면 근사.

    ★ 인자 꼴이 평평한 넷이라 정본(`metres`)과 다르다 — 소비자가 이 꼴로
      부르고 있어 남긴다. 계산은 **정본 하나**가 한다.
    """
    return metres((lon1, lat1), (lon2, lat2))


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
    # ★ 정본과 **같은 수를 쓰는가** — 넘기는 파일이 제 상수를 다시 갖지 않는가
    if (LAT0, MY) != (LP.LAT0, LP.MY) or abs(MX - LP.MX) > 1e-9:
        bad.append("상수가 정본과 다르다 — 이 파일은 넘기기만 해야 한다")
        print("★ " + bad[-1]); return 1
    print(f"localgeo OK — LAT0 {LAT0} · 경도 1도 {MX:.0f}m · 위도 1도 {MY}m"
          " (정본 firelane.localplane)")
    return 0


if __name__ == "__main__":
    no_args(__doc__)          # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    raise SystemExit(selftest())
