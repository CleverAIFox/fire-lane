#!/usr/bin/env python3
"""
quiet_gdal.py — GDAL/rasterio 의 알려진 무해 잡음만 걷어낸다.

    import quiet_gdal  # rasterio 를 쓰기 전에

── 무엇을 막나 ────────────────────────────────────────────────
1. `NotGeoreferencedWarning`
   정사영상 TIF 에 geotransform 이 없다. 사실이고 이미 알고 있다
   (PLAN #11 — 도엽 bbox + 사방 균등 pad 가정). ortho.py 가 스코프
   bbox 로 직접 배치하므로 동작에 지장이 없다.

2. `rasterio._env.log_error` 안에서 난 `UnicodeDecodeError`
   원본 TIF 메타가 cp949 인데 rasterio 콜백이 UTF-8 로 디코딩한다.
   콜백 내부 예외라 sys.unraisablehook 으로 트레이스백이 찍힌다.
   매 실행 4벌.

── 무엇을 막지 않나 ★ ─────────────────────────────────────────
그 **둘만** 막는다. 다른 예외, 다른 모듈, 다른 경고는 그대로 통과한다.
2026-08-21 `OSError: Errno 12`(메모리 부족) 를 이 스팸 사이에서 찾느라
시간을 태웠다. 잡음을 지우는 목적은 진짜 오류를 보이게 하는 것이지
오류를 감추는 것이 아니다.

억제 건수는 `suppressed()` 로 셀 수 있다. 예상보다 많이 세어지면
새로운 문제가 섞여 들어온 것이다.
"""
from __future__ import annotations

import sys
import warnings

_count = {"unicode": 0, "warning": 0}
_installed = False


def suppressed() -> dict[str, int]:
    """억제한 건수. 예상 밖으로 늘면 새 문제가 섞인 것이다."""
    return dict(_count)


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    # 1. geotransform 없음 경고
    try:
        from rasterio.errors import NotGeoreferencedWarning
        warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
    except Exception:                                        # noqa: BLE001
        warnings.filterwarnings("ignore", message=".*not georeferenced.*")

    # 2. rasterio 로그 콜백의 cp949 디코딩 실패
    prev = sys.unraisablehook

    def _hook(un):
        if un.exc_type is UnicodeDecodeError and \
                "rasterio._env" in repr(getattr(un, "object", None)):
            _count["unicode"] += 1
            return
        prev(un)

    sys.unraisablehook = _hook


install()
