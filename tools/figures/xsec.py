#!/usr/bin/env python3
"""
tools/figures/xsec.py — 도로폭 산출 — 법선 트랜섹트와 평면교차점 실형상 제외

정본 목록은 `tools/render_figures.FIGURES` 다.

IN    figures 공용(`__init__`)이 읽는 정본
OUT   SVG 문자열
PARAM 없음
밖    배치(넘침 · 겹침)는 `tools/svg_fit.py` 가 든다.
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
"""
from __future__ import annotations

import svg_fit

from figures import COLOR, _params


def fig_xsec() -> str:
    """도로폭 산출 — 법선 트랜섹트와 평면교차점 실형상 제외. 기획서 [그림 13].

    ★ 2026-09-24 (PLAN §12 #15). 기획서 [그림 13] 은 **반경 5m 원 하나만**
      그린다. 캡션은 2026-09-01 에 「평면교차점 실형상 제외」로 고쳐졌는데
      그림은 안 고쳐졌다 — 캡션과 그림이 서로 다른 모델을 말하는 채로
      석 주를 서 있었다. 캡션만 보는 검사(`docx_check`)로는 못 잡는다.

      실제 규칙은 `seg/width.py` 가 든다 — **평면교차점 폴리곤이 가까이
      있으면 폴리곤만 믿고**(`distance < XSEC_EXCL * 2`), 폴리곤이 아예
      없는 교차로에서만 노드 반경으로 폴백한다. 원은 **폴백**이지 규칙이
      아니다. 그림이 폴백만 그리면 읽는 사람은 규칙을 원으로 안다.

    ★ 원이 왜 폴백인가를 그림 자체가 말한다 — 위아래 두 줄이 **같은 길 ·
      같은 표본**인데 버려지는 표본 수가 다르다. 원은 작은 교차부를
      과하게 도려내고, 큰 교차부에서는 오염을 남긴다.

    ★ 교차부 모양과 표본 수는 **모식**이다. 실형상은 교차부마다 다르고 그
      정본은 `ngii1k_xsec_5186.gpkg`(A0080000)다 — 값이 아니라 **규칙**을
      그린다. 값 그림과 구조 그림을 가르는 것은 `fig_branch` 와 같다.
      반경과 표본 간격만 정본에서 온다.

    ★ 2026-09-24 2판. 1판은 8px/m 이라 32m 에 트랜섹트 39개가 서서 **울타리로
      보였고**, 노드가 표본 사이에 떨어져 두 줄의 버린 수가 **같았다**(4 대 4).
      그림이 아무 말도 못 하는 상태였다. 20px/m · 표본 15 · 노드를 표본 위상에
      맞춰 5 대 3 이 보이게 했다. 트랜섹트는 담에서 담까지 그리고 양끝에 점을
      찍는다 — 세로선이 아니라 **폭 1회 측정**으로 읽혀야 한다.
    """
    p = _params()
    # ★ **기본값을 안 둔다.** 다른 그림들은 `p.get(키, 사본)` 으로 적는데
    #   그 사본이 정본과 갈리면 그림이 조용히 옛 값을 그린다 — 이 그림이
    #   바로 그 병으로 났다. 없으면 우는 쪽이 낫다.
    if "XSEC_EXCL" not in p:
        raise SystemExit("★ params.py 에서 XSEC_EXCL 을 못 읽었다 — "
                         "이름이 바뀌었거나 표기가 바뀌었다. 그림을 지어내지 않는다.")
    r_m = p["XSEC_EXCL"]

    # ── 축척 ─────────────────────────────────────────────────
    # ★ 2026-09-24 2판. 1판은 8px/m 이라 32m 구간에 트랜섹트 39개가 서서
    #   **울타리로 보였다.** 교차부가 노면보다 작아 피처로 안 읽혔고,
    #   「버림 5 대 버림 3」 이라는 그림의 주장이 눈에 안 들어왔다.
    #   20px/m 으로 키우고 구간을 32m 로 줄였다 — 트랜섹트 17개.
    PX = 20.0                        # 1m = 20px
    STEP_M = 2.0                     # 표본 간격. `seg/width.py::widths` 의 np.arange 보폭
    ROAD_M, CROSS_M = 6.0, 6.0       # 노면 폭 · 교차 도로 폭 (모식)
    half, chalf = ROAD_M / 2 * PX, CROSS_M / 2 * PX
    x0, x1, cx = 40.0, 680.0, 360.0
    r = r_m * PX
    #: 실형상 가로 반폭(모식). 원보다 **작다** — 작은 교차부가 과하게
    #: 도려내지는 것이 `seg/width.py` 주석이 든 실제 현상이다.
    poly_half = 3.2 / 2 * PX + 32.0

    A_CY, B_CY = 175.0, 403.0

    def road(cy: float) -> str:
        """가로 노면 + 세로 노면. 담(경계)을 진하게 그려 「담~담 폭」이 읽히게."""
        return (f'<path d="M{x0} {cy - half} H{x1} V{cy + half} H{x0} Z" '
                f'fill="#f8fafc" stroke="none"/>'
                f'<path d="M{cx - chalf} {cy - half - 34} H{cx + chalf} '
                f'V{cy + half + 34} H{cx - chalf} Z" fill="#f8fafc" stroke="none"/>'
                f'<line x1="{x0}" y1="{cy - half}" x2="{cx - chalf}" y2="{cy - half}" '
                f'stroke="#475569" stroke-width="2"/>'
                f'<line x1="{cx + chalf}" y1="{cy - half}" x2="{x1}" y2="{cy - half}" '
                f'stroke="#475569" stroke-width="2"/>'
                f'<line x1="{x0}" y1="{cy + half}" x2="{cx - chalf}" y2="{cy + half}" '
                f'stroke="#475569" stroke-width="2"/>'
                f'<line x1="{cx + chalf}" y1="{cy + half}" x2="{x1}" y2="{cy + half}" '
                f'stroke="#475569" stroke-width="2"/>'
                f'<line x1="{cx - chalf}" y1="{cy - half - 34}" x2="{cx - chalf}" '
                f'y2="{cy - half}" stroke="#475569" stroke-width="2"/>'
                f'<line x1="{cx + chalf}" y1="{cy - half - 34}" x2="{cx + chalf}" '
                f'y2="{cy - half}" stroke="#475569" stroke-width="2"/>'
                f'<line x1="{cx - chalf}" y1="{cy + half}" x2="{cx - chalf}" '
                f'y2="{cy + half + 34}" stroke="#475569" stroke-width="2"/>'
                f'<line x1="{cx + chalf}" y1="{cy + half}" x2="{cx + chalf}" '
                f'y2="{cy + half + 34}" stroke="#475569" stroke-width="2"/>')

    def ticks(cy: float, drop) -> tuple[str, int, int]:
        """법선 트랜섹트. **담에서 담까지**가 한 번의 폭 측정이다.

        잰 것은 초록 실선 + 양끝 점, 버린 것은 회색 점선이고 점이 없다.
        """
        out, n, k = [], 0, 0
        # ★ 첫 표본을 교차 노드와 **같은 위상**에 둔다. 2m 간격에서 노드가 표본
        #   사이에 떨어지면 반경 5.0m 와 실형상 3.2m 가 **같은 수를 버려** 그림이
        #   아무 말도 못 한다. 실제 `widths()` 의 보폭도 2m 이고 위상은 구간마다
        #   다르다 — 여기서는 차이가 **보이는 위상**을 그린다(모식).
        t = cx - round((cx - (x0 + 20)) / (STEP_M * PX)) * STEP_M * PX
        while t < x0 + 20:          # 노면 끝에 붙은 첫 표본은 끝단 캡처럼 읽힌다
            t += STEP_M * PX
        while t <= x1 - 20:
            n += 1
            bad = drop(t)
            k += bad
            if bad:
                out.append(f'<line x1="{t:.0f}" y1="{cy - half:.0f}" '
                           f'x2="{t:.0f}" y2="{cy + half:.0f}" stroke="#cbd5e1" '
                           f'stroke-width="2" stroke-dasharray="4 4"/>')
            else:
                c = COLOR["clear"]
                out.append(f'<line x1="{t:.0f}" y1="{cy - half:.0f}" '
                           f'x2="{t:.0f}" y2="{cy + half:.0f}" stroke="{c}" '
                           f'stroke-width="2"/>'
                           f'<circle cx="{t:.0f}" cy="{cy - half:.0f}" r="2.5" fill="{c}"/>'
                           f'<circle cx="{t:.0f}" cy="{cy + half:.0f}" r="2.5" fill="{c}"/>')
            t += STEP_M * PX
        return "".join(out), n, k

    a_body, a_n, a_k = ticks(A_CY, lambda t: abs(t - cx) < r)
    b_body, b_n, b_k = ticks(B_CY, lambda t: abs(t - cx) < poly_half)

    # 실형상 모식 — 네 갈래가 만나는 자리라 사각형이 아니다
    pw, ph = poly_half, chalf + 10
    shape = (f'<path d="M{cx - pw:.0f} {B_CY - ph + 8:.0f} '
             f'L{cx - pw + 12:.0f} {B_CY - ph:.0f} L{cx + pw - 8:.0f} {B_CY - ph + 3:.0f} '
             f'L{cx + pw:.0f} {B_CY + 6:.0f} L{cx + pw - 12:.0f} {B_CY + ph:.0f} '
             f'L{cx - pw + 6:.0f} {B_CY + ph - 4:.0f} Z" '
             f'fill="#fed7aa" fill-opacity="0.85" stroke="{COLOR["needs_cv"]}" '
             f'stroke-width="2.5"/>')

    # ★ 그림 → 글자 순서로 쌓는다. SVG 는 뒤에 온 것이 위에 그려지고,
    #   `_fits()` 는 `<path>` 를 안 본다(도형은 `<rect>` · `<circle>` 만).
    sb_x, sb_m = 40.0, 10.0          # 축척 막대 — 10m
    art = [
        # 제외 도형을 **먼저** 깔고 트랜섹트를 그 위에 올린다 — 버린 표본이
        # 도형에 가리면 「무엇이 왜 버려졌나」가 안 보인다.
        road(A_CY),
        f'<circle cx="{cx:.0f}" cy="{A_CY:.0f}" r="{r:.0f}" fill="{COLOR["blocked"]}" '
        f'fill-opacity="0.08" stroke="{COLOR["blocked"]}" stroke-width="2.5" '
        f'stroke-dasharray="7 5"/>',
        a_body,
        road(B_CY), shape, b_body,
        # 축척 막대
        f'<line x1="{sb_x}" y1="520" x2="{sb_x + sb_m * PX}" y2="520" '
        f'stroke="#0f172a" stroke-width="2"/>'
        f'<line x1="{sb_x}" y1="515" x2="{sb_x}" y2="525" stroke="#0f172a" stroke-width="2"/>'
        f'<line x1="{sb_x + sb_m * PX}" y1="515" x2="{sb_x + sb_m * PX}" y2="525" '
        f'stroke="#0f172a" stroke-width="2"/>',
    ]
    txt = [
        '<text x="12" y="26" font-size="16" font-weight="700" fill="#0f172a">'
        '도로폭 산출 — 법선 트랜섹트와 평면교차점 실형상 제외</text>',
        '<text x="12" y="46" font-size="11" fill="#64748b">'
        '정본 src/firelane/seg/params.py · XSEC_EXCL — 제외 규칙은 seg/width.py</text>',

        f'<text x="{x0:.0f}" y="66" font-size="13" font-weight="700" fill="{COLOR["blocked"]}">'
        f'① 폴백 — 노드에서 {r_m:g}m. 실형상이 없는 교차로에서만</text>',
        f'<text x="700" y="66" font-size="13" fill="#0f172a" text-anchor="end">'
        f'표본 {a_n} · 버림 {a_k}</text>',

        f'<text x="{x0:.0f}" y="294" font-size="13" font-weight="700" '
        f'fill="{COLOR["needs_cv"]}">② 실형상 — 평면교차점 폴리곤 안만 버린다. '
        '이쪽이 규칙이다</text>',
        f'<text x="700" y="294" font-size="13" fill="#0f172a" text-anchor="end">'
        f'표본 {b_n} · 버림 {b_k}</text>',

        f'<text x="{sb_x + sb_m * PX + 10:.0f}" y="524" font-size="11" fill="#475569">'
        f'{sb_m:g}m · 노면 {ROAD_M:g}m · 표본 간격 {STEP_M:g}m · '
        '표본 수는 이 모식도의 것이다</text>',
        '<text x="12" y="554" font-size="12" fill="#475569">'
        '세로선 하나가 폭 1회 측정이다 — 담에서 담까지. 초록은 잰 것, '
        '회색 점선은 버린 것.</text>',
        f'<text x="12" y="574" font-size="12" fill="{COLOR["blocked"]}">'
        f'※ 원은 규칙이 아니라 폴백이다. 반경 {r_m:g}m 는 작은 교차부를 '
        '과하게 도려내고 큰 교차부에는 오염을 남긴다.</text>',
    ]
    return svg_fit.svg("".join(art + txt), h=592)


