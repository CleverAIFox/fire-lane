#!/usr/bin/env python3
"""
srgb.py — sRGB 색의 **표준 변환 한 집**. 감마 · 상대휘도 · L*a*b* · ΔE.

    uv run python tools/srgb.py --selftest   자기검사

── 왜 생겼나 (2026-10-11 · DECISIONS §474) ─────────────────────
sRGB **역감마**(전달함수)가 세 벌이었다 — 글자까지 같고, 둘은 **같은 파일**에
있었다 —

    tools/colorsim.py  `_lab()` 안        c/12.92 … ((c+0.055)/1.055)**2.4
    tools/colorsim.py  `luminance()` 안   같은 다섯 줄
    tools/uicheck.py   `_lum()` 안        같은 다섯 줄 (받는 꼴만 hex)

그리고 WCAG 상대휘도의 가중치(0.2126 · 0.7152 · 0.0722)가 두 벌이었다.
`tools/mutate.py` 의 생존 목록이 그 자리를 **이미 가리키고 있었다** —
「`uicheck` 2 — 층 공식의 WCAG 상수(0.04045)」. 흔들어도 아무도 안 울었다.

★ **맡길 의존성이 없다.** `colorsys`(표준 라이브러리)는 HSV · HLS · YIQ 뿐이고
  sRGB 감마도 Lab 도 안 한다. `pillow` 의 `ImageCms` 는 **ICC 프로파일** 변환이라
  같은 수가 안 나오고 littlecms 판에 따라 갈린다 — 관문이 판마다 갈리면 관문이
  아니다. 그래서 **공식은 여기 남는다.** `#168` 이 고치는 것은 「의존성이 할 수
  있는 일을 손으로 짠다」이고, 이 자리는 **「정본 없이 손으로 짠 것이 셋」**이다.

★ 집을 `tools/` 에 둔다 — 소비자 둘이 다 도구다. `src/firelane` 쪽 소비자가
  생기면 **그때 올린다.** 미루는 것이 아니라 재고 올린다 — §473 이 보인 대로
  폐포를 재는 데 1초고(`shardseal.code_print`), 「저쪽은 판정이라」로 미루면
  `src` 소비자는 못 쓰는 것이 아니라 **손으로 짠다**(§471 의 규약).

── 무엇이 아닌가 ───────────────────────────────────────────────
★ **색을 고르지 않는다.** 어떤 색이어야 하는지는 `colorsim` · `uicheck` 가
  제 축으로 묻는다. 여기는 수를 내는 자리다.
★ **색각 이상 변환은 여기 없다.** 그것은 `colorsim` 의 주제이고 LMS 행렬이
  그 파일의 선언이다 — 한 소비자만 쓰는 것을 공용 집에 올리지 않는다.

IN    없음 (순수 함수)
OUT   없음
PARAM 없음 · 인자 없이 치면 자기검사
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
밖    **색 공간을 다 하지 않는다.** CMYK · HSL · Oklab 은 안 든다.
      ΔE 는 **CIE76** 하나다 — CIEDE2000 은 가중식이 길고, 이 저장소가
      그것을 쓸 자리가 아직 없다(쓰게 되면 그 판이 사유와 함께 더한다).
"""
from __future__ import annotations

import math

#: sRGB 역감마의 무릎. 이 아래는 선형 구간이다.
KNEE = 0.04045

#: 선형 구간의 기울기.
SLOPE = 12.92

#: 거듭제곱 구간의 오프셋 · 배율 · 지수.
OFFSET, SCALE, GAMMA = 0.055, 1.055, 2.4

#: WCAG 상대휘도의 가중치 (R, G, B). 합은 1 이다.
LUM_WEIGHTS = (0.2126, 0.7152, 0.0722)

#: WCAG 대비식의 바닥값. 검정 대 검정이 0/0 이 되지 않게 둔다.
CONTRAST_FLOOR = 0.05

#: sRGB → XYZ (D65). 백색점으로 나눌 값이 아래 `WHITE_D65` 다.
RGB2XYZ = ((0.4124, 0.3576, 0.1805),
           (0.2126, 0.7152, 0.0722),
           (0.0193, 0.1192, 0.9505))

#: D65 백색점.
WHITE_D65 = (0.95047, 1.00000, 1.08883)

#: L*a*b* 의 f(t) 가 선형으로 꺾이는 점과 그 기울기.
LAB_KNEE, LAB_SLOPE = 0.008856, 7.787


def linear(c8: float) -> float:
    """0~255 sRGB 한 채널 → **선형** 0~1. 역감마 하나가 여기 있다."""
    c = c8 / 255.0
    return c / SLOPE if c <= KNEE else ((c + OFFSET) / SCALE) ** GAMMA


def luminance(rgb: tuple[float, ...]) -> float:
    """WCAG 상대휘도. 0(검정) ~ 1(흰색)."""
    r, g, b = (linear(c) for c in rgb)
    wr, wg, wb = LUM_WEIGHTS
    return wr * r + wg * g + wb * b


def lum_ratio(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """두 색의 휘도비(≥1). 1.00 이면 **밝기가 같다**."""
    la, lb = luminance(a) + CONTRAST_FLOOR, luminance(b) + CONTRAST_FLOOR
    return max(la, lb) / min(la, lb)


def hex_rgb(hex6: str) -> tuple[int, int, int]:
    """`#rrggbb` → (r, g, b). 앞의 `#` 는 있어도 없어도 된다."""
    h = hex6.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"여섯 자리 16진색이 아니다 — {hex6!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def lab(rgb: tuple[float, ...]) -> tuple[float, float, float]:
    """sRGB → CIE L*a*b* (D65). 감마와 백색점은 표준값이다."""
    lin = [linear(c) for c in rgb]
    x, y, z = (sum(m[i] * lin[i] for i in range(3)) / w
               for m, w in zip(RGB2XYZ, WHITE_D65, strict=True))

    def f(t: float) -> float:
        return t ** (1 / 3) if t > LAB_KNEE else LAB_SLOPE * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """CIE76 ΔE*ab. 두 색이 **얼마나 다른가**의 표준 거리."""
    la, aa, ba = lab(a)
    lb, ab, bb = lab(b)
    return math.sqrt((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


def selftest() -> int:
    """★ **양방향.** 아는 값과 맞는가, 그리고 틀린 입력에 우는가."""
    bad = []
    # ① 흰색·검정의 상대휘도는 1 과 0 이다 (WCAG 정의)
    if abs(luminance((255, 255, 255)) - 1.0) > 1e-9:
        bad.append(f"흰색 휘도가 1 이 아니다 — {luminance((255, 255, 255))}")
    if luminance((0, 0, 0)) != 0.0:
        bad.append(f"검정 휘도가 0 이 아니다 — {luminance((0, 0, 0))}")
    # ② 흰색 대 검정의 대비는 21:1 이다 — WCAG 가 그 수를 적는다
    if abs(lum_ratio((255, 255, 255), (0, 0, 0)) - 21.0) > 1e-9:
        bad.append(f"흰·검 대비가 21 이 아니다 — {lum_ratio((255,255,255),(0,0,0))}")
    # ③ 무릎 **양쪽**을 다 지나는가. 한쪽만 맞으면 분기가 죽어도 안 운다
    lo, hi = KNEE * 255 * 0.5, KNEE * 255 * 2
    if not (linear(lo) < linear(hi) and linear(lo) == (lo / 255) / SLOPE):
        bad.append("선형 구간이 안 듣는다")
    if linear(hi) != ((hi / 255 + OFFSET) / SCALE) ** GAMMA:
        bad.append("거듭제곱 구간이 안 듣는다")
    # ④ 흰색의 L* 은 100, a*·b* 은 0 **근처**다.
    #   ★ 왜 정확히 0 이 아닌가 — `RGB2XYZ` 가 표준의 **네 자리** 공표형이라
    #     세 행의 합이 D65 백색점과 소수 네째 자리에서 어긋난다. 실측 흰색이
    #     a* 0.005 · b* −0.010 이다. **그 어긋남이 자라면 운다**(0.02).
    #     「0 이어야 한다」로 적으면 이 판별식이 영원히 빨갛고, 사람이 끈다.
    L, A, B = lab((255, 255, 255))
    if abs(L - 100) > 1e-6 or abs(A) > 0.02 or abs(B) > 0.02:
        bad.append(f"흰색 Lab 가 (100,0,0) 근처가 아니다 — {L:.3f} {A:.3f} {B:.3f}")
    # ⑤ 같은 색의 ΔE 는 0 이고, 다른 색은 0 이 아니다 (양방향)
    if delta_e((1, 2, 3), (1, 2, 3)) != 0.0:
        bad.append("같은 색의 ΔE 가 0 이 아니다")
    if delta_e((0, 0, 0), (255, 255, 255)) < 99:
        bad.append("흑백 ΔE 가 100 근처가 아니다")
    # ⑥ 16진 읽기 — 맞는 것과 틀린 것 양쪽
    if hex_rgb("#1a9660") != (26, 150, 96) or hex_rgb("1a9660") != (26, 150, 96):
        bad.append(f"16진 읽기가 틀렸다 — {hex_rgb('#1a9660')}")
    for wrong in ("#12345", "", "#1234567"):
        try:
            hex_rgb(wrong)
        except ValueError:
            continue
        bad.append(f"여섯 자리가 아닌 {wrong!r} 을 받는다")
    # ⑦ 가중치 합이 1 이다 — 하나를 고치면서 다른 둘을 안 고치면 운다
    if abs(sum(LUM_WEIGHTS) - 1.0) > 1e-4:
        bad.append(f"휘도 가중치 합이 1 이 아니다 — {sum(LUM_WEIGHTS)}")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 휘도(흰1·검0·대비21) · 무릎 양쪽 · Lab 흰색 · ΔE · 16진")
    return 0


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.parse_args()           # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    sys.exit(selftest())
