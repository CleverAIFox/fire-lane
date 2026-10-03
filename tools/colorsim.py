#!/usr/bin/env python3
"""
colorsim.py — 판정 네 색이 **색각 이상에서도 서로 갈리는가**.

    uv run python tools/colorsim.py             대조
    uv run python tools/colorsim.py --matrix    쌍 × 시각 전체 표
    uv run python tools/colorsim.py --selftest  변환이 살아 있나

── 왜 생겼나 (DECISIONS §383) ──────────────────────────────────
`web/config.js` 의 머리말이 네 색을 고른 근거를 적는다 — 「배경을 #dfe3ea 로
낮춘 상태에서 네 색이 모두 **대비 2.4~3.5**」. 그 수는 **바탕 대비**
(figure-ground)다. 지면에서 떠 보이는가를 잰 것이고, **집합 안에서 서로
갈리는가**(within-set discriminability)는 안 쟀다.

둘은 다른 축이다. 네 색이 전부 배경에서 잘 떠도 서로 비슷하면 지도는
**한 색**이 된다. 판정이 넷인데 읽히는 것이 하나면 판정을 안 낸 것과 같다.

── 어떻게 재나 ─────────────────────────────────────────────────
① 색각 이상 셋을 **표준 변환**으로 시뮬레이션한다
     Viénot · Brettel · Mollon (1999) 의 LMS 투영. 적록 2종과 청황 1종.
② 쌍마다 **CIE76 ΔE*ab** 를 잰다. 넷이면 여섯 쌍, 시각 넷(정상 포함)이라
   스물넷 칸이다.
③ 그중 **최솟값**을 든다. 가장 안 갈리는 한 쌍이 그 지도의 한계다.

★ **문턱을 발명하지 않는다.** 래칫이 「지금 최솟값」이고 **올라가는 쪽**이다 —
  색을 바꿔 더 나빠지면 운다. 참고로 CIE76 의 겨우 알아볼 수 있는 차이(JND)가
  약 2.3 인데, 그것은 나란히 놓고 보는 색편 기준이라 **지도선에 그대로 쓰면
  안 된다.** 그래서 문턱으로 안 쓰고 표에만 적는다.

IN    web/config.js  (`verdict` 블록 — 파서는 `publish_navi` 가 정본이다)
OUT   없음 (검사)
PARAM COLOR_MIN_DE (래칫 · 올라가는 쪽)
밖    **색을 고르지 않는다.** 어떤 색이어야 하는지는 이 도구가 모른다 —
      드는 것은 「지금 것이 얼마나 갈리나」 하나다.
      **둘째 채널도 안 본다.** 선 패턴·굵기로 같은 정보를 두 번 싣는 것은
      화면 쪽 일이고, 그 배선은 `web/navi` 가 든다.
"""
from __future__ import annotations

import argparse
import itertools
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 지금 가장 안 갈리는 쌍의 ΔE. **올라가는 쪽** — 색을 바꿔 더 붙으면 운다.
COLOR_MIN_DE = 14
#: 가장 밝기가 붙은 쌍의 **휘도비 × 100**(WCAG 상대휘도). 1.00 이면 같은 밝기다.
#: 지도선은 얇고 멀어서 **밝기로 먼저 읽힌다** — 색상이 달라도 밝기가 같으면
#: 흑백 인쇄 · 저조도 · 작은 크기에서 한 색이 된다. 그래서 축을 둘로 든다.
COLOR_MIN_LUM = 100

RATCHETS = {"COLOR_MIN_DE": "up", "COLOR_MIN_LUM": "up"}

#: 선형 RGB → LMS. Viénot · Brettel · Mollon (1999), Hunt-Pointer-Estevez 계열.
_RGB2LMS = ((17.8824, 43.5161, 4.11935),
            (3.45565, 27.1554, 3.86714),
            (0.0299566, 0.184309, 1.46709))
#: 그 역변환.
_LMS2RGB = ((0.0809444479, -0.130504409, 0.116721066),
            (-0.0102485335, 0.0540193266, -0.113614708),
            (-0.000365296938, -0.00412161469, 0.693511405))
#: 색각 이상 셋의 LMS 투영. 정상(`normal`)은 항등이다.
VISION = {
    "normal": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "protan": ((0, 2.02344, -2.52581), (0, 1, 0), (0, 0, 1)),
    "deutan": ((1, 0, 0), (0.494207, 0, 1.24827), (0, 0, 1)),
    "tritan": ((1, 0, 0), (0, 1, 0), (-0.395913, 0.801109, 0)),
}


def _mul(m, v):
    return tuple(sum(r[i] * v[i] for i in range(3)) for r in m)


def simulate(rgb: tuple[float, float, float], vision: str) -> tuple[float, ...]:
    """0~255 sRGB 를 그 시각으로 옮긴다. 정상은 그대로 돌려준다."""
    lms = _mul(_RGB2LMS, rgb)
    out = _mul(_LMS2RGB, _mul(VISION[vision], lms))
    return tuple(min(255.0, max(0.0, c)) for c in out)


def _lab(rgb: tuple[float, ...]) -> tuple[float, float, float]:
    """sRGB → CIE L*a*b* (D65). 감마와 백색점은 표준값이다."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.00000
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def luminance(rgb: tuple[float, ...]) -> float:
    """WCAG 상대휘도. 0(검정) ~ 1(흰색)."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def lum_ratio(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """두 색의 휘도비(≥1). 1.00 이면 **밝기가 같다**."""
    la, lb = luminance(a) + 0.05, luminance(b) + 0.05
    return max(la, lb) / min(la, lb)


def delta_e(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """CIE76 ΔE*ab. 두 색이 **얼마나 다른가**의 표준 거리."""
    la, aa, ba = _lab(a)
    lb, ab, bb = _lab(b)
    return math.sqrt((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


def colors() -> dict[str, tuple[int, int, int]]:
    """`web/config.js` 의 판정 네 색. **파서는 `publish_navi` 가 정본이다.**

    두 번째 파서를 만들지 않는다 — 같은 블록을 두 규칙으로 읽으면 둘이 갈린다.
    """
    from firelane.publish_navi import _verdict_style
    out = {}
    for k, v in _verdict_style().items():
        m = re.findall(r"\d+", v["lightColor"])   # "rgb(224,53,38)"
        if len(m) != 3:
            raise RuntimeError(f"{k} 의 lightColor 를 못 읽었다 — {v['lightColor']}")
        out[k] = tuple(int(x) for x in m)
    return out


def matrix(cs: dict[str, tuple[int, int, int]]) -> list[dict]:
    """쌍 × 시각 전수. 넷이면 여섯 쌍 × 넷 = 스물넷 칸."""
    out = []
    for a, b in itertools.combinations(sorted(cs), 2):
        for vis in VISION:
            sa, sb = simulate(cs[a], vis), simulate(cs[b], vis)
            out.append({"pair": f"{a} ↔ {b}", "vision": vis,
                        "de": delta_e(sa, sb), "lum": lum_ratio(sa, sb)})
    out.sort(key=lambda d: d["de"])
    return out


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값(내림). **0 을 내지 않는다.**"""
    m = matrix(colors())
    if not m:
        raise RuntimeError("web/config.js 에서 판정 색을 못 읽었다")
    return {"COLOR_MIN_DE": int(m[0]["de"]),
            "COLOR_MIN_LUM": int(min(r["lum"] for r in m) * 100)}


def show(cs: dict, m: list[dict], full: bool) -> int:
    print(f"── 판정 색의 구별 가능성  색 {len(cs)} · 쌍 {len(m) // len(VISION)} "
          f"· 시각 {len(VISION)}")
    print("\n  색 (lightColor — 지도에 나가는 쪽)")
    for k, v in cs.items():
        print(f"    {k:<9} rgb{v}")
    print("\n  ΔE*ab (CIE76) — 작을수록 안 갈린다. 참고로 색편 JND 가 약 2.3")
    for row in (m if full else m[:8]):
        mark = "✗ " if row["de"] < COLOR_MIN_DE else "  "
        print(f"    {mark}{row['pair']:<24} {row['vision']:<7} "
              f"ΔE {row['de']:6.1f} · 휘도비 {row['lum']:4.2f}")
    if not full and len(m) > 8:
        print(f"    … 그 밖 {len(m) - 8}칸 (`--matrix` 로 전부)")

    lo = m[0]
    lw = min(m, key=lambda r: r["lum"])
    print(f"\n  색상이 가장 붙은 칸  **{lo['pair']} · {lo['vision']} · "
          f"ΔE {lo['de']:.1f}** · 래칫 {COLOR_MIN_DE}")
    print(f"  밝기가 가장 붙은 칸  **{lw['pair']} · {lw['vision']} · "
          f"휘도비 {lw['lum']:.2f}** · 래칫 {COLOR_MIN_LUM / 100:.2f}")
    print("  ★ 지도선은 얇고 멀어서 **밝기로 먼저 읽힌다.** 색상이 달라도")
    print("    밝기가 같으면 흑백 인쇄 · 저조도 · 작은 크기에서 한 색이 된다.")
    print("\n★ **색을 고르지 않는다.** 드는 것은 「지금 것이 얼마나 갈리나」다.")
    print("  둘째 채널(선 패턴)은 화면 쪽 일이고 이 도구가 안 본다.")

    gl = int(min(r["lum"] for r in m) * 100)
    if gl != COLOR_MIN_LUM:
        print(f"\n✗ 휘도비 최솟값 {gl / 100:.2f} ≠ 래칫 {COLOR_MIN_LUM / 100:.2f} "
              "— 그 수로 맞춰라")
        return 1
    got = int(lo["de"])
    if got < COLOR_MIN_DE:
        print(f"\n✗ 최솟값 {got} < 래칫 {COLOR_MIN_DE} — **색이 더 붙었다.**")
        print("  판정이 넷인데 읽히는 것이 셋이 된다.")
        return 1
    if got > COLOR_MIN_DE:
        print(f"\n✗ 최솟값 {got} > 래칫 {COLOR_MIN_DE} — "
              "**래칫을 그 수로 올려라.** 안 올리면 다시 붙는다.")
        return 1
    return 0


def selftest() -> int:
    """★ 변환이 **알려진 사실**을 내는가. 데이터 없이 문다."""
    bad = []
    red, green, blue = (255, 0, 0), (0, 255, 0), (0, 0, 255)

    # ① 정상 시각에서 빨강과 초록은 멀다.
    if delta_e(simulate(red, "normal"), simulate(green, "normal")) < 100:
        bad.append("정상 시각에서 빨강·초록이 안 멀다 — Lab 변환이 깨졌다")
    # ② 녹색맹에서 그 둘이 **붙는다.** 이것이 이 도구의 존재 이유다.
    d_norm = delta_e(simulate(red, "normal"), simulate(green, "normal"))
    d_deut = delta_e(simulate(red, "deutan"), simulate(green, "deutan"))
    if d_deut >= d_norm:
        bad.append(f"녹색맹에서 빨강·초록이 안 붙는다 ({d_norm:.0f} → {d_deut:.0f})")
    # ③ 적록 이상은 파랑을 거의 안 건드린다.
    if delta_e(simulate(blue, "normal"), simulate(blue, "deutan")) > 25:
        bad.append("녹색맹이 파랑을 크게 옮긴다 — 투영 행렬이 뒤바뀌었다")
    # ④ 청황 이상은 **파랑과 초록을 붙인다.** 파랑 자체는 그 혼동축의
    #   정점이라 거의 안 움직인다(실측 ΔE 0.0) — 그래서 「파랑이 옮겨지는가」로
    #   물으면 멀쩡한 변환을 틀렸다고 한다. 움직이는 것은 **쌍**이다.
    t_norm = delta_e(simulate(blue, "normal"), simulate(green, "normal"))
    t_trit = delta_e(simulate(blue, "tritan"), simulate(green, "tritan"))
    if t_trit >= t_norm * 0.5:
        bad.append(f"청황 이상에서 파랑·초록이 안 붙는다 ({t_norm:.0f} → {t_trit:.0f})")
    # ⑤ 같은 색의 거리는 0 이고, 정상 변환은 항등이다.
    if delta_e(simulate(red, "normal"), red) > 1e-6:
        bad.append("정상 변환이 항등이 아니다")
    if delta_e((10, 20, 30), (10, 20, 30)) != 0:
        bad.append("같은 색의 ΔE 가 0 이 아니다")
    # ⑥ 흰색과 검정은 어느 시각에서도 갈린다 — 명도 축은 안 죽는다.
    for v in VISION:
        if delta_e(simulate((255, 255, 255), v), simulate((0, 0, 0), v)) < 90:
            bad.append(f"{v} 에서 흑백이 붙는다 — 명도 축이 죽었다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 적록 붕괴 재현 · 청황 분리 · 항등 · 명도 축 "
          f"(시각 {len(VISION)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", action="store_true", help="스물넷 칸 전부")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cs = colors()
    return show(cs, matrix(cs), a.matrix)


if __name__ == "__main__":
    sys.exit(main())
